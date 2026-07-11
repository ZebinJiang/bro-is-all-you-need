"""真实 Torch DataLoader 数据集、worker 工厂和提交状态外观。"""

from __future__ import annotations

import atexit
import importlib
import os
import random
import struct
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from multiprocessing import shared_memory
from typing import Any, cast

import numpy as np

from autovla.config.schema import DataLoaderConfig, DatasetConfig
from autovla.core.types.training import TrainingBatch, TrainingSample
from autovla.data.backends.base import MapDataSource, StreamingDataSource
from autovla.data.collators import BatchCollator
from autovla.data.contracts import (
    DataAccessMode,
    DataLifecycleError,
    DataSourceSpec,
    IncompatibleDataStateError,
    MapIndex,
    PartitionPlan,
    SamplingPlan,
    StreamAssignmentUnit,
    StreamPartitionState,
    WorkerContext,
    WorkerInitializationError,
    derive_worker_seed,
    stable_fingerprint,
)
from autovla.data.transforms import TransformPipeline
from autovla.data.types import DataLoaderState, DataStage

_ACTIVE_WORKER_CONTEXT: WorkerContext | None = None
_EPOCH_STRUCT = struct.Struct("!QQQ")


def _torch_data() -> tuple[Any, Any]:
    """仅在构造或运行生产加载器时导入可选 Torch。"""
    try:
        import torch
        from torch.utils import data
    except ImportError as exc:
        raise RuntimeError(
            "TrainingDataLoader requires optional dependency 'torch'; install autovla[training]"
        ) from exc
    return torch, data


@dataclass(frozen=True, slots=True)
class RuntimeTopology:
    """保存 rank 事实和 worker 上下文构造输入。"""

    global_rank: int
    local_rank: int
    world_size: int
    base_seed: int
    split: str
    multiprocessing_start_method: str
    node_id: str | None = None


@dataclass
class SharedEpochDescriptor:
    """通过标准共享内存向持久 worker 发布 epoch、seed 和 generation。"""

    name: str | None
    initial_epoch: int
    initial_seed: int
    initial_generation: int = 0
    owner: bool = False

    @classmethod
    def create(cls, *, epoch: int, seed: int) -> "SharedEpochDescriptor":
        """创建可由 spawn/forkserver worker 按名称附加的共享描述符。"""
        memory = shared_memory.SharedMemory(create=True, size=_EPOCH_STRUCT.size)
        try:
            memory.buf[: _EPOCH_STRUCT.size] = _EPOCH_STRUCT.pack(epoch, seed, 0)
            return cls(memory.name, epoch, seed, 0, True)
        finally:
            memory.close()

    def __getstate__(self) -> dict[str, object]:
        """worker 副本只附加共享内存,不拥有 unlink 权限。"""
        state = dict(self.__dict__)
        state["owner"] = False
        return state

    def read(self) -> tuple[int, int, int]:
        """读取当前 epoch、seed 和 generation。"""
        if self.name is None:
            return self.initial_epoch, self.initial_seed, self.initial_generation
        memory = shared_memory.SharedMemory(name=self.name)
        try:
            return cast(
                tuple[int, int, int],
                _EPOCH_STRUCT.unpack(bytes(memory.buf[: _EPOCH_STRUCT.size])),
            )
        finally:
            memory.close()

    def update(self, *, epoch: int, seed: int) -> None:
        """由主进程原子发布下一 epoch。"""
        _, _, generation = self.read()
        self.initial_epoch = epoch
        self.initial_seed = seed
        self.initial_generation = generation + 1
        if self.name is None:
            return
        memory = shared_memory.SharedMemory(name=self.name)
        try:
            memory.buf[: _EPOCH_STRUCT.size] = _EPOCH_STRUCT.pack(epoch, seed, generation + 1)
        finally:
            memory.close()

    def close(self) -> None:
        """仅由创建者关闭并 unlink 共享描述符。"""
        if not self.owner or self.name is None:
            return
        try:
            memory = shared_memory.SharedMemory(name=self.name)
        except FileNotFoundError:
            self.owner = False
            return
        try:
            try:
                memory.unlink()
            except FileNotFoundError:
                pass
        finally:
            memory.close()
        self.owner = False


def _worker_context(
    topology: RuntimeTopology,
    descriptor: SharedEpochDescriptor,
) -> WorkerContext:
    """从真实 Torch worker_info 或零 worker 主进程构造上下文。"""
    _, data = _torch_data()
    epoch, seed, _ = descriptor.read()
    info = data.get_worker_info()
    if info is None:
        return WorkerContext.create(
            global_rank=topology.global_rank,
            local_rank=topology.local_rank,
            world_size=topology.world_size,
            worker_id=0,
            logical_worker_count=1,
            actual_worker_process_count=0,
            base_seed=seed,
            epoch=epoch,
            split=topology.split,
            multiprocessing_start_method="none",
            node_id=topology.node_id,
            is_main_process=True,
        )
    return WorkerContext.create(
        global_rank=topology.global_rank,
        local_rank=topology.local_rank,
        world_size=topology.world_size,
        worker_id=int(info.id),
        logical_worker_count=int(info.num_workers),
        actual_worker_process_count=1,
        base_seed=seed,
        epoch=epoch,
        split=topology.split,
        multiprocessing_start_method=topology.multiprocessing_start_method,
        node_id=topology.node_id,
        is_main_process=False,
    )


def _install_worker_context(context: WorkerContext) -> None:
    """在首次使用或 epoch 变化时安装上下文并重置 worker RNG。"""
    global _ACTIVE_WORKER_CONTEXT
    if _ACTIVE_WORKER_CONTEXT == context:
        return
    random.seed(context.derived_worker_seed)
    np.random.seed(context.derived_worker_seed % (2**32))
    torch, _ = _torch_data()
    torch.manual_seed(context.derived_worker_seed)
    _ACTIVE_WORKER_CONTEXT = context


def _sample_shuffle_resume_policy(plan: SamplingPlan) -> str:
    """返回明确区分精确恢复和非精确缓冲的策略名。"""
    if plan.stream_sample_shuffle_buffer > 0:
        return "non_exact_unserialized"
    if plan.exact_resume:
        return "disabled_for_exact_resume"
    return "disabled_non_exact"


def _stream_assignment_digest(epoch: int, assigned_units: Sequence[str]) -> str:
    """把 epoch 和源单元共同绑定到 worker assignment 摘要。"""
    return stable_fingerprint({"epoch": epoch, "assigned_units": tuple(assigned_units)})


@dataclass(frozen=True, slots=True)
class WorkerInitializer:
    """安装上下文并确定性初始化 Python、NumPy 和 Torch RNG。"""

    topology: RuntimeTopology
    descriptor: SharedEpochDescriptor

    def __call__(self, worker_id: int) -> None:
        """验证 Torch worker id 后安装进程全局上下文。"""
        del worker_id
        try:
            context = _worker_context(self.topology, self.descriptor)
            _install_worker_context(context)
        except Exception as exc:
            raise WorkerInitializationError("failed to initialize AutoVLA data worker") from exc


class _LegacyMapSource:
    """在 worker 内把旧句柄临时适配到唯一 map 源契约。"""

    def __init__(self, spec: DataSourceSpec, handle: object) -> None:
        self.spec = spec
        self._handle = handle

    def __len__(self) -> int:
        """返回句柄长度。"""
        return len(self._handle)  # type: ignore[arg-type]

    def initialize_worker(self, context: WorkerContext) -> None:
        """旧句柄已在同一 worker 中构造,仅记录上下文。"""
        self._context = context

    def read(self, index: int) -> TrainingSample:
        """委托旧句柄读取一条样本。"""
        return self._handle.read(index)  # type: ignore[no-any-return,union-attr]

    def read_many(self, indices: Sequence[int]) -> Sequence[TrainingSample]:
        """保持请求顺序的窄兼容批读取。"""
        return tuple(self.read(index) for index in indices)

    def state_dict(self) -> Mapping[str, object]:
        """旧 map 句柄不拥有主进程提交游标。"""
        return {}

    def close(self) -> None:
        """关闭 worker-local 旧句柄。"""
        self._handle.close()  # type: ignore[union-attr]


class _LegacyStreamingSource:
    """在 worker 内把有限旧句柄顺序适配为 streaming 源。"""

    def __init__(self, spec: DataSourceSpec, handle: object) -> None:
        self.spec = spec
        self._handle = handle
        self._offset = 0

    def initialize_worker(self, context: WorkerContext) -> None:
        """记录拥有该句柄的 worker 上下文。"""
        self._context = context

    def iter_samples(
        self, context: WorkerContext, state: StreamPartitionState
    ) -> Iterator[TrainingSample]:
        """从已提交 offset 顺序读取,不暴露随机访问接口。"""
        del context
        start = state.consumed_sample_offset
        count = len(self._handle)  # type: ignore[arg-type]
        for index in range(start, count):
            sample = self._handle.read(index)  # type: ignore[union-attr]
            self._offset = index + 1
            yield sample

    def state_dict(self) -> Mapping[str, object]:
        """返回下一条未读兼容 offset。"""
        return {"consumed_sample_offset": self._offset}

    def close(self) -> None:
        """关闭 worker-local 旧句柄。"""
        self._handle.close()  # type: ignore[union-attr]


@dataclass
class SourceFactory:
    """保存 pickle-safe 后端描述并仅在消费进程打开源。"""

    factory_path: str
    config: DatasetConfig
    stage: DataStage
    spec: DataSourceSpec
    _source: MapDataSource | StreamingDataSource | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _context: WorkerContext | None = field(default=None, init=False, repr=False, compare=False)

    def __getstate__(self) -> dict[str, object]:
        """排除所有 live backend/文件/媒体句柄。"""
        state = dict(self.__dict__)
        state["_source"] = None
        state["_context"] = None
        return state

    def _create_backend(self) -> object:
        """解析无参数后端工厂。"""
        module_name, separator, attribute = self.factory_path.partition(":")
        if not separator:
            raise WorkerInitializationError("backend factory path is invalid")
        target = getattr(importlib.import_module(module_name), attribute)
        return target()

    def initialize(self, context: WorkerContext) -> MapDataSource | StreamingDataSource:
        """在当前进程打开一次类型化源并安装上下文。"""
        if self._source is not None:
            assert self._context is not None
            previous_identity = (
                self._context.global_rank,
                self._context.worker_id,
                self._context.logical_worker_count,
                self._context.actual_worker_process_count,
            )
            current_identity = (
                context.global_rank,
                context.worker_id,
                context.logical_worker_count,
                context.actual_worker_process_count,
            )
            if previous_identity != current_identity:
                raise DataLifecycleError("source cannot change owning worker identity")
            if self._context != context:
                self._source.initialize_worker(context)
                self._context = context
            return self._source
        backend = self._create_backend()
        open_source = getattr(backend, "open_source", None)
        if callable(open_source):
            source = open_source(self.config, self.stage, context)
        else:
            open_dataset = getattr(backend, "open_dataset", None)
            if not callable(open_dataset):
                raise WorkerInitializationError("backend lacks open_source compatibility")
            handle = open_dataset(self.config, self.stage)
            source = (
                _LegacyMapSource(self.spec, handle)
                if self.spec.access_mode is DataAccessMode.MAP
                else _LegacyStreamingSource(self.spec, handle)
            )
        if getattr(source, "spec", None) != self.spec:
            raise WorkerInitializationError("opened source spec differs from described source")
        source.initialize_worker(context)
        self._source = source
        self._context = context
        atexit.register(self.close)
        return source

    def close(self) -> None:
        """幂等关闭当前进程拥有的源。"""
        source, self._source = self._source, None
        self._context = None
        if source is not None:
            source.close()


def _with_worker_provenance(
    sample: TrainingSample,
    context: WorkerContext,
    dataset_key: str,
    source_state: Mapping[str, object] | None = None,
) -> TrainingSample:
    """把实际 worker/pid 和可选 stream 状态附加到样本来源。"""
    provenance = dict(sample.sample_source)
    provenance["autovla_worker"] = {
        "global_rank": context.global_rank,
        "worker_id": context.worker_id,
        "pid": os.getpid(),
        "actual_worker_process_count": context.actual_worker_process_count,
    }
    provenance["autovla_source_key"] = dataset_key
    if source_state is not None:
        backend_state = dict(source_state)
        provenance["autovla_backend_state"] = backend_state
        if "assigned_units" in backend_state:
            provenance["autovla_stream_state"] = backend_state
    return replace(sample, sample_source=provenance)


@dataclass
class AutoVLAMapDataset:
    """让 Torch worker 直接 materialize map 样本并使用批读取快路径。"""

    factories: tuple[SourceFactory, ...]
    topology: RuntimeTopology
    descriptor: SharedEpochDescriptor

    def __len__(self) -> int:
        """返回所有 map 源逻辑索引总数。"""
        return sum(cast(int, factory.spec.sample_count) for factory in self.factories)

    def _context(self) -> WorkerContext:
        """返回 worker_init 安装的上下文或零 worker 主进程上下文。"""
        context = _worker_context(self.topology, self.descriptor)
        _install_worker_context(context)
        return context

    def __getitem__(self, key: MapIndex) -> TrainingSample:
        """在消费进程打开源并读取一条样本。"""
        source_id, index = key
        context = self._context()
        source = cast(MapDataSource, self.factories[source_id].initialize(context))
        return _with_worker_provenance(
            source.read(index),
            context,
            self.factories[source_id].spec.dataset_key,
            source.state_dict(),
        )

    def __getitems__(self, keys: Sequence[MapIndex]) -> list[TrainingSample]:
        """按源分组调用 read_many,再恢复原请求顺序。"""
        context = self._context()
        grouped: dict[int, list[tuple[int, int]]] = {}
        for position, (source_id, index) in enumerate(keys):
            grouped.setdefault(source_id, []).append((position, index))
        output: list[TrainingSample | None] = [None] * len(keys)
        for source_id, requests in grouped.items():
            source = cast(MapDataSource, self.factories[source_id].initialize(context))
            samples = tuple(source.read_many(tuple(index for _, index in requests)))
            if len(samples) != len(requests):
                raise RuntimeError("read_many must preserve request cardinality")
            for (position, _), sample in zip(requests, samples, strict=True):
                output[position] = _with_worker_provenance(
                    sample,
                    context,
                    self.factories[source_id].spec.dataset_key,
                    source.state_dict(),
                )
        if any(sample is None for sample in output):
            raise RuntimeError("read_many left an unresolved output position")
        return cast(list[TrainingSample], output)

    def close(self) -> None:
        """关闭当前进程已打开的全部源。"""
        for factory in self.factories:
            factory.close()


@dataclass
class AutoVLAStreamingDataset:
    """让 Torch IterableDataset worker 直接调用类型化 iter_samples。"""

    factories: tuple[SourceFactory, ...]
    topology: RuntimeTopology
    descriptor: SharedEpochDescriptor
    base_stream_units: tuple[StreamAssignmentUnit, ...]
    sampling_plan: SamplingPlan
    initial_states: Mapping[str, Mapping[str, object]] = field(default_factory=dict)

    def _context(self) -> WorkerContext:
        """返回当前实际 worker 上下文。"""
        context = _worker_context(self.topology, self.descriptor)
        _install_worker_context(context)
        return context

    def __iter__(self) -> Iterator[TrainingSample]:
        """按 worker 分配调用 source.iter_samples,不提供伪随机访问。"""
        context = self._context()
        plan = PartitionPlan.for_streaming(
            self.base_stream_units,
            global_rank=context.global_rank,
            world_size=context.world_size,
            logical_worker_count=context.logical_worker_count,
            seed=self.sampling_plan.base_seed,
            epoch=context.epoch,
            shuffle=self.sampling_plan.stream_shard_shuffle,
        )
        assignment = cast(
            tuple[StreamAssignmentUnit, ...], plan.worker_assignments[context.worker_id]
        )
        resume_policy = _sample_shuffle_resume_policy(self.sampling_plan)
        for source_id, factory in enumerate(self.factories):
            assigned_units = tuple(
                unit_id for assigned_source, unit_id in assignment if assigned_source == source_id
            )
            if not assigned_units:
                continue
            source = cast(StreamingDataSource, factory.initialize(context))
            key = f"{factory.spec.dataset_key}:{context.worker_id}"
            raw = self.initial_states.get(key, {})
            assignment_digest = _stream_assignment_digest(context.epoch, assigned_units)
            if raw:
                state = StreamPartitionState.from_dict(raw)
                if state.epoch > context.epoch:
                    raise IncompatibleDataStateError("stream state epoch is ahead of worker epoch")
                if state.epoch == context.epoch:
                    if (
                        state.worker_id != context.worker_id
                        or state.assigned_units != assigned_units
                        or state.assignment_digest != assignment_digest
                        or state.shard_order_digest != plan.sequence_digest
                        or state.sample_shuffle_resume_policy != resume_policy
                    ):
                        raise IncompatibleDataStateError(
                            "stream worker assignment differs from committed state"
                        )
                else:
                    raw = {}
            if not raw:
                state = StreamPartitionState(
                    worker_id=context.worker_id,
                    epoch=context.epoch,
                    assignment_owner="autovla_loader",
                    assigned_units=assigned_units,
                    upstream_partitioning_disabled=True,
                    assignment_digest=assignment_digest,
                    shard_order_digest=plan.sequence_digest,
                    shard_rng_state={
                        "seed": plan.permutation_seed,
                        "shuffle": self.sampling_plan.stream_shard_shuffle,
                    },
                    sample_rng_state={"seed": context.derived_worker_seed},
                    sample_shuffle_resume_policy=resume_policy,
                )
            samples = source.iter_samples(context, state)

            def capture_state(
                source_instance: StreamingDataSource = source,
            ) -> StreamPartitionState:
                """合并 backend 状态并保留 loader 拥有的 assignment。"""
                nonlocal state
                observed = dict(source_instance.state_dict())
                state = replace(
                    state,
                    current_shard=cast(str | None, observed.get("current_shard")),
                    shard_index=int(observed.get("shard_index", state.shard_index)),
                    consumed_sample_offset=int(
                        observed.get(
                            "consumed_sample_offset",
                            state.consumed_sample_offset + 1,
                        )
                    ),
                    shard_rng_state=cast(
                        Mapping[str, object],
                        observed.get("shard_rng_state", state.shard_rng_state),
                    ),
                    sample_rng_state=cast(
                        Mapping[str, object],
                        observed.get("sample_rng_state", state.sample_rng_state),
                    ),
                    handler_counts=cast(
                        Mapping[str, int],
                        observed.get("handler_counts", state.handler_counts),
                    ),
                    source_state=observed,
                )
                return state

            buffer_size = self.sampling_plan.stream_sample_shuffle_buffer
            if buffer_size == 0:
                for sample in samples:
                    yield _with_worker_provenance(
                        sample,
                        context,
                        factory.spec.dataset_key,
                        capture_state().to_dict(),
                    )
                continue
            rng = random.Random(context.derived_worker_seed ^ 0xA5A5A5A5)
            buffer: list[TrainingSample] = []
            for sample in samples:
                if len(buffer) < buffer_size:
                    buffer.append(sample)
                    continue
                selected = rng.randrange(len(buffer))
                output, buffer[selected] = buffer[selected], sample
                yield _with_worker_provenance(
                    output,
                    context,
                    factory.spec.dataset_key,
                    capture_state().to_dict(),
                )
            while buffer:
                selected = rng.randrange(len(buffer))
                output = buffer.pop(selected)
                yield _with_worker_provenance(
                    output,
                    context,
                    factory.spec.dataset_key,
                    capture_state().to_dict(),
                )

    def close(self) -> None:
        """关闭当前进程已打开的全部 streaming 源。"""
        for factory in self.factories:
            factory.close()


@dataclass(frozen=True, slots=True)
class ProductionCollator:
    """在 worker 内执行通用变换并生成 storage-neutral TrainingBatch。"""

    collator: BatchCollator
    transforms: TransformPipeline
    manifest_fingerprint: str
    statistics_fingerprint: str
    source_identities: tuple[tuple[str, str, str], ...] = ()

    def __post_init__(self) -> None:
        """校验每个数据集键只绑定一个 source/schema 身份。"""
        identities = tuple(self.source_identities)
        keys: list[str] = []
        for identity in identities:
            if len(identity) != 3 or any(
                not isinstance(value, str) or not value.strip() for value in identity
            ):
                raise ValueError("source identity must contain three non-empty strings")
            keys.append(identity[0])
        if len(set(keys)) != len(keys):
            raise ValueError("source identity dataset keys must be unique")
        object.__setattr__(self, "source_identities", identities)

    def __call__(self, samples: Sequence[TrainingSample]) -> TrainingBatch:
        """保留 backend 身份和来源,同时附加 manifest/处理指纹。"""
        identities = {
            dataset_key: (source_fingerprint, schema_fingerprint)
            for dataset_key, source_fingerprint, schema_fingerprint in self.source_identities
        }
        prepared: list[TrainingSample] = []
        for sample in samples:
            transformed = self.transforms(sample)
            source_key = transformed.sample_source.get(
                "autovla_source_key",
                transformed.sample_source.get("dataset"),
            )
            if not isinstance(source_key, str) or source_key not in identities:
                raise ValueError("sample source key has no declared source identity")
            source_fingerprint, schema_fingerprint = identities[source_key]
            prepared.append(
                replace(
                    transformed,
                    sample_source={
                        **dict(transformed.sample_source),
                        **dict(sample.sample_source),
                    },
                    dataset_fingerprint=sample.dataset_fingerprint,
                    source_fingerprint=source_fingerprint,
                    schema_fingerprint=schema_fingerprint,
                    dataset_manifest_fingerprint=self.manifest_fingerprint,
                    transform_fingerprint=self.transforms.fingerprint,
                    statistics_fingerprint=self.statistics_fingerprint,
                )
            )
        return self.collator(tuple(prepared))


@dataclass
class PlannedBatchSampler:
    """在主进程从已提交样本游标生成确定性 map index batches。"""

    sequence: tuple[MapIndex, ...]
    batch_size: int
    drop_last: bool
    start_sample_cursor: int = 0

    def set_plan(self, sequence: Sequence[MapIndex], start_sample_cursor: int) -> None:
        """在新 epoch 或恢复前替换不可变计划。"""
        self.sequence = tuple(sequence)
        self.start_sample_cursor = start_sample_cursor

    def __iter__(self) -> Iterator[list[MapIndex]]:
        """从主进程已提交边界输出批索引。"""
        for start in range(self.start_sample_cursor, len(self.sequence), self.batch_size):
            batch = list(self.sequence[start : start + self.batch_size])
            if len(batch) < self.batch_size and self.drop_last:
                break
            yield batch

    def __len__(self) -> int:
        """返回剩余批次数。"""
        remaining = max(0, len(self.sequence) - self.start_sample_cursor)
        return (
            remaining // self.batch_size
            if self.drop_last
            else (remaining + self.batch_size - 1) // self.batch_size
        )


def _register_streaming_dataset(data: Any) -> None:
    """把顶层 pickle-safe 类注册为所选 Torch IterableDataset 虚拟子类。"""
    register = getattr(data.IterableDataset, "register", None)
    if not callable(register):
        raise RuntimeError("selected Torch IterableDataset lacks virtual subclass registration")
    register(AutoVLAStreamingDataset)


def _shutdown_iterator(iterator: object, torch_version: str) -> None:
    """隔离 Torch 2.5/2.6 无公共 API 时的 worker 关闭边界。"""
    if iterator is None:
        return
    public = getattr(iterator, "shutdown", None)
    if callable(public):
        public()
        return
    if torch_version.startswith(("2.5.", "2.6.")):
        private = getattr(iterator, "_shutdown_workers", None)
        if callable(private):
            private()
            return
    if getattr(iterator, "_workers", None):
        raise RuntimeError(f"no verified DataLoader worker shutdown for Torch {torch_version}")


class TrainingDataLoader:
    """拥有真实 Torch loader、主进程提交状态和确定性关闭。"""

    def __init__(
        self,
        *,
        factories: Sequence[SourceFactory],
        source_specs: Sequence[DataSourceSpec],
        partition_plan: PartitionPlan,
        sampling_plan: SamplingPlan,
        config: DataLoaderConfig,
        topology: RuntimeTopology,
        collator: ProductionCollator,
        manifest_fingerprint: str,
        mix_strategy: str,
        mix_balance_by: str,
        mix_weights: Sequence[float],
        base_map_sequence: Sequence[MapIndex] = (),
        base_stream_units: Sequence[StreamAssignmentUnit] = (),
    ) -> None:
        """记录纯描述和主进程状态,不导入 Torch 或打开源。"""
        if not factories or len(factories) != len(source_specs):
            raise ValueError("loader factories and source_specs must have equal non-zero length")
        modes = {spec.access_mode for spec in source_specs}
        splits = {spec.split for spec in source_specs}
        if len(modes) != 1 or len(splits) != 1:
            raise ValueError("one TrainingDataLoader requires one access mode and split")
        self._factories = tuple(factories)
        self._specs = tuple(source_specs)
        self._plan = partition_plan
        self._sampling = sampling_plan
        self._config = config
        self._topology = topology
        self._collator = collator
        self._manifest_fingerprint = manifest_fingerprint
        expected_source_identities = tuple(
            (
                spec.dataset_key,
                spec.source_fingerprint,
                spec.schema_fingerprint,
            )
            for spec in self._specs
        )
        if self._collator.source_identities != expected_source_identities:
            raise ValueError("production collator source identities differ from loader specs")
        self._mix_strategy = mix_strategy
        self._mix_balance_by = mix_balance_by
        self._mix_weights = tuple(float(weight) for weight in mix_weights)
        if len(self._mix_weights) != len(self._specs) or any(
            weight <= 0 for weight in self._mix_weights
        ):
            raise ValueError("mix weights must be positive and match source count")
        if self._mix_balance_by not in {"dataset", "embodiment"}:
            raise ValueError("mix_balance_by must be dataset or embodiment")
        self._base_map_sequence = tuple(base_map_sequence)
        self._base_stream_units = tuple(base_stream_units)
        if sampling_plan.access_mode is DataAccessMode.MAP and not self._base_map_sequence:
            raise ValueError("map loader requires base_map_sequence")
        if sampling_plan.access_mode is DataAccessMode.STREAMING and not self._base_stream_units:
            raise ValueError("streaming loader requires backend-declared assignment units")
        self._epoch = 0
        self._committed_sample_cursor = 0
        self._global_batches_consumed = 0
        self._global_samples_consumed = 0
        self._observed_worker_pids: set[int] = set()
        self._observed_worker_ids: set[int] = set()
        self._observed_actual_worker_count = 0
        self._observed_backend_states: dict[str, dict[str, object]] = {}
        self._committed_source_draw_counts = {spec.dataset_key: 0 for spec in self._specs}
        self._stream_partition_states: dict[str, object] = {}
        self._torch_loader: object | None = None
        self._iterator: object | None = None
        self._torch_version: str | None = None
        self._closed = False
        self._descriptor = SharedEpochDescriptor(None, self._epoch, self._sampling.base_seed)
        self._batch_sampler = PlannedBatchSampler(
            (
                cast(tuple[MapIndex, ...], self._plan.rank_sequence)
                if sampling_plan.access_mode is DataAccessMode.MAP
                else ()
            ),
            config.batch_size,
            config.drop_last,
        )
        self._compatibility_fingerprint = self._expected_compatibility_fingerprint()

    @property
    def source_specs(self) -> tuple[DataSourceSpec, ...]:
        """返回生产 loader 实际消费的源规格。"""
        return self._specs

    @property
    def source_factories(self) -> tuple[SourceFactory, ...]:
        """返回仅含可序列化配置和工厂路径的源工厂。"""
        return self._factories

    @property
    def runtime_topology(self) -> RuntimeTopology:
        """返回 TrainingStrategy/DataModule 已绑定的 rank 事实。"""
        return self._topology

    @property
    def runtime_telemetry(self) -> Mapping[str, object]:
        """返回 worker 事实和后端已有状态契约可观测的有界证据。"""
        return {
            "configured_worker_count": self._config.num_workers,
            "actual_loader_worker_count": self._observed_actual_worker_count,
            "observed_worker_ids": tuple(sorted(self._observed_worker_ids)),
            "observed_worker_pids": tuple(sorted(self._observed_worker_pids)),
            "backend_states": {
                key: dict(value) for key, value in sorted(self._observed_backend_states.items())
            },
        }

    @property
    def torch_loader_created(self) -> bool:
        """返回是否已实际构造 Torch DataLoader。"""
        return self._torch_loader is not None

    def _expected_compatibility_fingerprint(self) -> str:
        """计算恢复前必须完全匹配的运行契约指纹。"""
        return stable_fingerprint(
            {
                "source_specs": tuple(spec.compatibility_fingerprint for spec in self._specs),
                "sampling": self._sampling.compatibility_fingerprint,
                "partition_policy": self._config.partition_policy,
                "world_size": self._topology.world_size,
                "global_rank": self._topology.global_rank,
                "configured_worker_count": self._config.num_workers,
                "worker_seed_policy": self._config.worker_seed_policy,
                "multiprocessing_start_method": self._topology.multiprocessing_start_method,
                "mix_strategy": self._mix_strategy,
                "mix_balance_by": self._mix_balance_by,
                "mix_weights": self._mix_weights,
                "manifest_fingerprint": self._manifest_fingerprint,
                "normalization_fingerprint": self._collator.statistics_fingerprint,
                "temporal_query_state": self._temporal_query_state(),
            }
        )

    def _temporal_query_state(self) -> dict[str, object]:
        """返回按源排序且包含查询字段和指纹的可序列化状态。"""
        sources: list[dict[str, object]] = []
        for factory, spec in zip(self._factories, self._specs, strict=True):
            query = factory.config.temporal_query
            query_fingerprint = (
                stable_fingerprint({"temporal_query": None}) if query is None else query.fingerprint
            )
            sources.append(
                {
                    "dataset_key": spec.dataset_key,
                    "query_fingerprint": query_fingerprint,
                    "query": None if query is None else query.to_dict(),
                }
            )
        return {"sources": sources}

    def _plan_for_epoch(self, epoch: int) -> PartitionPlan:
        """按 epoch 重建 map 序列或真实 stream assignment。"""
        if self._sampling.access_mode is DataAccessMode.STREAMING:
            return PartitionPlan.for_streaming(
                self._base_stream_units,
                global_rank=self._topology.global_rank,
                world_size=self._topology.world_size,
                logical_worker_count=max(self._config.num_workers, 1),
                seed=self._sampling.base_seed,
                epoch=epoch,
                shuffle=self._config.stream_shard_shuffle,
            )
        return PartitionPlan.for_map(
            self._base_map_sequence,
            global_rank=self._topology.global_rank,
            world_size=self._topology.world_size,
            batch_size=self._config.batch_size,
            seed=self._sampling.base_seed,
            epoch=epoch,
            shuffle=self._config.map_shuffle,
            policy=self._config.partition_policy,
        )

    def _mixer_state(
        self,
        *,
        epoch: int,
        global_draw_count: int,
        draw_counts: Mapping[str, int],
    ) -> dict[str, object]:
        """返回由真实提交计数和固定混合契约构成的状态。"""
        weight_sum = sum(self._mix_weights)
        normalized_weights = tuple(weight / weight_sum for weight in self._mix_weights)
        compatibility = {
            "strategy": self._mix_strategy,
            "balance_by": self._mix_balance_by,
            "weights": list(self._mix_weights),
            "source_fingerprints": [spec.source_fingerprint for spec in self._specs],
            "replacement": self._sampling.replacement,
            "base_seed": self._sampling.base_seed,
        }
        return {
            **compatibility,
            "normalized_weights": list(normalized_weights),
            "epoch": epoch,
            "global_draw_count": global_draw_count,
            "draw_counts": dict(draw_counts),
            "compatibility_fingerprint": stable_fingerprint(compatibility),
        }

    def _balancer_state(
        self,
        *,
        epoch: int,
        draw_counts: Mapping[str, int],
    ) -> dict[str, object]:
        """返回与混合器使用同一已提交计数的平衡器状态。"""
        compatibility = {
            "enabled": self._mix_strategy == "balanced",
            "balance_by": self._mix_balance_by,
            "source_keys": [spec.dataset_key for spec in self._specs],
        }
        return {
            **compatibility,
            "epoch": epoch,
            "source_draw_counts": dict(draw_counts),
            "compatibility_fingerprint": stable_fingerprint(compatibility),
        }

    def _generator_state(self, *, epoch: int, plan: PartitionPlan) -> dict[str, object]:
        """返回可完整重建 worker 与分区 RNG 的确定性输入。"""
        return {
            "policy": self._config.worker_seed_policy,
            "base_seed": self._sampling.base_seed,
            "epoch": epoch,
            "permutation_seed": plan.permutation_seed,
            "global_rank": self._topology.global_rank,
            "split": self._topology.split,
            "multiprocessing_start_method": self._topology.multiprocessing_start_method,
        }

    def _sample_shuffle_state(self) -> dict[str, object]:
        """如实声明 sample buffer 是否被禁用或不支持精确恢复。"""
        policy = _sample_shuffle_resume_policy(self._sampling)
        return {
            "policy": policy,
            "buffer_size": self._sampling.stream_sample_shuffle_buffer,
            "serialized": self._sampling.stream_sample_shuffle_buffer == 0,
        }

    def _stream_assignments(self, plan: PartitionPlan) -> dict[str, tuple[int, tuple[str, ...]]]:
        """把 rank 内 worker 计划按源键展开为唯一恢复 assignment。"""
        output: dict[str, tuple[int, tuple[str, ...]]] = {}
        for worker_id, raw_assignment in enumerate(plan.worker_assignments):
            assignment = cast(tuple[StreamAssignmentUnit, ...], raw_assignment)
            for source_id, spec in enumerate(self._specs):
                units = tuple(
                    unit_id
                    for assigned_source, unit_id in assignment
                    if assigned_source == source_id
                )
                if units:
                    output[f"{spec.dataset_key}:{worker_id}"] = (worker_id, units)
        return output

    @staticmethod
    def _stream_rng_state(
        states: Mapping[str, object],
    ) -> dict[str, object]:
        """从结构化 worker 状态提取不重复的 shard/sample RNG 状态。"""
        output: dict[str, object] = {}
        for key, raw in states.items():
            if not isinstance(raw, Mapping):
                raise IncompatibleDataStateError("stream worker state must be a mapping")
            state = StreamPartitionState.from_dict(raw)
            output[key] = {
                "shard_rng_state": dict(state.shard_rng_state),
                "sample_rng_state": dict(state.sample_rng_state),
            }
        return output

    def _build(self) -> object:
        """按访问模式和每个配置字段构造标准 Torch DataLoader。"""
        torch, data = _torch_data()
        self._torch_version = str(torch.__version__)
        if self._descriptor.name is None:
            self._descriptor = SharedEpochDescriptor.create(
                epoch=self._epoch, seed=self._sampling.base_seed
            )
        kwargs: dict[str, object] = {
            "num_workers": self._config.num_workers,
            "pin_memory": self._config.pin_memory,
            "timeout": self._config.timeout_seconds,
            "worker_init_fn": WorkerInitializer(self._topology, self._descriptor),
            "generator": torch.Generator().manual_seed(self._sampling.base_seed),
        }
        if self._config.num_workers > 0:
            kwargs["persistent_workers"] = self._config.persistent_workers
            if self._config.prefetch_factor is not None:
                kwargs["prefetch_factor"] = self._config.prefetch_factor
            kwargs["multiprocessing_context"] = self._config.multiprocessing_context or "spawn"
        if self._sampling.access_mode is DataAccessMode.MAP:
            dataset = AutoVLAMapDataset(self._factories, self._topology, self._descriptor)
            kwargs.update(
                dataset=dataset,
                batch_sampler=self._batch_sampler,
                collate_fn=self._collator,
            )
        else:
            _register_streaming_dataset(data)
            dataset = AutoVLAStreamingDataset(
                self._factories,
                self._topology,
                self._descriptor,
                self._base_stream_units,
                self._sampling,
                cast(Mapping[str, Mapping[str, object]], self._stream_partition_states),
            )
            kwargs.update(
                dataset=dataset,
                batch_size=self._config.batch_size,
                drop_last=self._config.drop_last,
                collate_fn=self._collator,
            )
        try:
            return data.DataLoader(**kwargs)
        except BaseException:
            self._descriptor.close()
            self._descriptor = SharedEpochDescriptor(
                None,
                self._epoch,
                self._sampling.base_seed,
            )
            raise

    def __len__(self) -> int:
        """返回当前 epoch 从已提交边界剩余的批次数。"""
        if self._sampling.access_mode is DataAccessMode.MAP:
            return len(self._batch_sampler)
        nominal = cast(int, self._sampling.nominal_epoch_size)
        remaining = max(0, nominal - self._committed_sample_cursor)
        return (
            remaining // self._config.batch_size
            if self._config.drop_last
            else (remaining + self._config.batch_size - 1) // self._config.batch_size
        )

    def _observe_and_commit(self, batch: TrainingBatch) -> None:
        """仅在主进程收到完整批后提交游标和 worker/source 事实。"""
        for source in batch.sample_source:
            worker = source.get("autovla_worker")
            source_key = source.get("autovla_source_key")
            if isinstance(source_key, str) and source_key in self._committed_source_draw_counts:
                self._committed_source_draw_counts[source_key] += 1
            if isinstance(worker, Mapping):
                worker_state = cast(Mapping[str, object], worker)
                pid = worker_state.get("pid")
                worker_id = worker_state.get("worker_id")
                actual = worker_state.get("actual_worker_process_count")
                if type(pid) is int and type(actual) is int and actual > 0:
                    self._observed_worker_pids.add(pid)
                if type(worker_id) is int:
                    self._observed_worker_ids.add(worker_id)
                self._observed_actual_worker_count = len(self._observed_worker_pids)
            stream_state = source.get("autovla_stream_state")
            backend_state = source.get("autovla_backend_state")
            if isinstance(source_key, str) and isinstance(backend_state, Mapping):
                backend_mapping = cast(Mapping[str, object], backend_state)
                self._observed_backend_states[source_key] = dict(backend_mapping)
                if stream_state is None:
                    candidate_stream_state = backend_mapping
                    if "assigned_units" in candidate_stream_state:
                        stream_state = candidate_stream_state
            if isinstance(stream_state, Mapping) and isinstance(worker, Mapping):
                stream_mapping = cast(Mapping[str, object], stream_state)
                worker_state = cast(Mapping[str, object], worker)
                if not isinstance(source_key, str) or source_key not in (
                    self._committed_source_draw_counts
                ):
                    raise DataLifecycleError("stream sample lacks canonical source provenance")
                key = f"{source_key}:{worker_state.get('worker_id', 'unknown')}"
                self._stream_partition_states[key] = dict(stream_mapping)
        self._global_batches_consumed += 1
        self._global_samples_consumed += batch.batch_size
        self._committed_sample_cursor += batch.batch_size

    def _finish_epoch_if_complete(self) -> None:
        """耗尽计划后推进 epoch,保留全局计数并重置局部提交游标。"""
        expected = (
            len(self._plan_for_epoch(self._epoch).rank_sequence)
            if self._sampling.access_mode is DataAccessMode.MAP
            else cast(int, self._sampling.nominal_epoch_size)
        )
        if self._sampling.access_mode is DataAccessMode.MAP and self._config.drop_last:
            expected -= expected % self._config.batch_size
        if self._committed_sample_cursor < expected:
            return
        self._epoch += 1
        self._committed_sample_cursor = 0
        self._descriptor.update(epoch=self._epoch, seed=self._sampling.base_seed)
        self._plan = self._plan_for_epoch(self._epoch)
        if self._sampling.access_mode is DataAccessMode.MAP:
            self._batch_sampler.set_plan(cast(tuple[MapIndex, ...], self._plan.rank_sequence), 0)
        else:
            self._stream_partition_states.clear()

    def __iter__(self) -> Iterator[TrainingBatch]:
        """从 committed cursor 迭代,预取结果仅在本方法交付时提交。"""
        if self._closed:
            raise DataLifecycleError("TrainingDataLoader is closed")
        self._finish_epoch_if_complete()
        if self._sampling.access_mode is DataAccessMode.MAP:
            self._batch_sampler.set_plan(
                cast(tuple[MapIndex, ...], self._plan.rank_sequence),
                self._committed_sample_cursor,
            )
        if self._torch_loader is None:
            self._torch_loader = self._build()
        try:
            iterator = iter(self._torch_loader)  # type: ignore[arg-type]
        except BaseException:
            self.close_runtime()
            raise
        self._iterator = iterator
        exhausted = False
        try:
            for batch in iterator:
                if not isinstance(batch, TrainingBatch):
                    raise TypeError("production DataLoader must yield TrainingBatch")
                self._observe_and_commit(batch)
                yield batch
                if (
                    self._sampling.access_mode is DataAccessMode.STREAMING
                    and self._committed_sample_cursor
                    >= cast(int, self._sampling.nominal_epoch_size)
                ):
                    exhausted = True
                    self._finish_epoch_if_complete()
                    return
            exhausted = True
            self._finish_epoch_if_complete()
        finally:
            if not exhausted and self._torch_version is not None:
                _shutdown_iterator(iterator, self._torch_version)
                self._torch_loader = None
            self._iterator = None

    def _state(self) -> DataLoaderState:
        """从主进程事实构造完整不可变状态。"""
        plan = self._plan_for_epoch(self._epoch)
        assignment_digests: dict[str, object] = {
            "global_sequence": plan.sequence_digest,
            "rank": plan.rank_assignment_digest,
            "workers": list(plan.worker_assignment_digests),
        }
        stream_mode = self._specs[0].stream_mode
        temporal_state = self._temporal_query_state()
        temporal_fingerprint = stable_fingerprint(temporal_state)
        sample_shuffle_policy = _sample_shuffle_resume_policy(self._sampling)
        return DataLoaderState(
            schema_version=DataLoaderState.SCHEMA_VERSION,
            manifest_fingerprint=self._manifest_fingerprint,
            backend_keys=tuple(spec.backend_key for spec in self._specs),
            source_keys=tuple(spec.dataset_key for spec in self._specs),
            source_fingerprints=tuple(spec.source_fingerprint for spec in self._specs),
            schema_fingerprints=tuple(spec.schema_fingerprint for spec in self._specs),
            split=self._specs[0].split,
            access_mode=self._sampling.access_mode.value,
            epoch=self._epoch,
            global_batches_consumed=self._global_batches_consumed,
            global_samples_consumed=self._global_samples_consumed,
            sequence_seed=self._sampling.base_seed,
            permutation_seed=plan.permutation_seed,
            committed_batch_cursor=self._committed_sample_cursor,
            global_rank=self._topology.global_rank,
            world_size=self._topology.world_size,
            configured_worker_count=self._config.num_workers,
            actual_loader_worker_count=self._observed_actual_worker_count,
            partition_policy=self._config.partition_policy,
            batch_size=self._config.batch_size,
            drop_last=self._config.drop_last,
            stream_mode=None if stream_mode is None else stream_mode.value,
            map_shuffle=self._config.map_shuffle,
            stream_shard_shuffle=self._config.stream_shard_shuffle,
            stream_sample_shuffle_buffer=self._config.stream_sample_shuffle_buffer,
            sample_shuffle_resume_policy=sample_shuffle_policy,
            assignment_digests=assignment_digests,
            stream_partition_states=self._stream_partition_states,
            stream_rng_state=self._stream_rng_state(self._stream_partition_states),
            sample_shuffle_buffer_state=self._sample_shuffle_state(),
            map_sampler_state=(
                {
                    "sequence_digest": plan.sequence_digest,
                    "rank_assignment_digest": plan.rank_assignment_digest,
                    "committed_sample_cursor": self._committed_sample_cursor,
                    "dropped_count": plan.dropped_count,
                    "repeated_count": plan.repeated_count,
                }
                if self._sampling.access_mode is DataAccessMode.MAP
                else {}
            ),
            mixer_state=self._mixer_state(
                epoch=self._epoch,
                global_draw_count=self._global_samples_consumed,
                draw_counts=self._committed_source_draw_counts,
            ),
            balancer_state=self._balancer_state(
                epoch=self._epoch,
                draw_counts=self._committed_source_draw_counts,
            ),
            temporal_query_fingerprint=temporal_fingerprint,
            temporal_query_state=temporal_state,
            normalization_fingerprint=self._collator.statistics_fingerprint,
            generator_state=self._generator_state(epoch=self._epoch, plan=plan),
            compatibility_fingerprint=self._compatibility_fingerprint,
        )

    def state_dict(self) -> Mapping[str, object]:
        """导出主进程 committed cursor,不读取 worker 预取游标。"""
        return self._state().to_dict()

    def validate_state(self, state: Mapping[str, object]) -> DataLoaderState:
        """完整验证恢复兼容性且不修改 live loader。"""
        restored = DataLoaderState.from_dict(state)
        current = self._state()
        fields = (
            "manifest_fingerprint",
            "backend_keys",
            "source_keys",
            "source_fingerprints",
            "schema_fingerprints",
            "split",
            "access_mode",
            "world_size",
            "global_rank",
            "configured_worker_count",
            "partition_policy",
            "batch_size",
            "drop_last",
            "stream_mode",
            "map_shuffle",
            "stream_shard_shuffle",
            "stream_sample_shuffle_buffer",
            "sample_shuffle_resume_policy",
            "sequence_seed",
            "temporal_query_fingerprint",
            "normalization_fingerprint",
            "compatibility_fingerprint",
        )
        mismatches = [name for name in fields if getattr(restored, name) != getattr(current, name)]
        if mismatches:
            raise IncompatibleDataStateError(f"data loader resume mismatch: {mismatches}")
        if restored.actual_loader_worker_count > restored.configured_worker_count:
            raise IncompatibleDataStateError("observed worker count exceeds configured workers")
        plan = self._plan_for_epoch(restored.epoch)
        expected_assignment_digests = {
            "global_sequence": plan.sequence_digest,
            "rank": plan.rank_assignment_digest,
            "workers": list(plan.worker_assignment_digests),
        }
        if dict(restored.assignment_digests) != expected_assignment_digests:
            raise IncompatibleDataStateError("partition assignment digests differ on resume")
        if restored.permutation_seed != plan.permutation_seed:
            raise IncompatibleDataStateError("partition permutation seed differs on resume")
        if dict(restored.sample_shuffle_buffer_state) != self._sample_shuffle_state():
            raise IncompatibleDataStateError("sample shuffle resume policy differs on resume")

        raw_draw_counts = restored.mixer_state.get("draw_counts")
        if not isinstance(raw_draw_counts, Mapping):
            raise IncompatibleDataStateError("mixer draw_counts must be a mapping")
        draw_counts: dict[str, int] = {}
        for key, value in raw_draw_counts.items():
            if not isinstance(key, str) or type(value) is not int or value < 0:
                raise IncompatibleDataStateError("mixer draw_counts are invalid")
            draw_counts[key] = value
        if set(draw_counts) != set(restored.source_keys):
            raise IncompatibleDataStateError("mixer source keys differ on resume")
        if sum(draw_counts.values()) != restored.global_samples_consumed:
            raise IncompatibleDataStateError("mixer draw counts differ from committed samples")
        expected_mixer = self._mixer_state(
            epoch=restored.epoch,
            global_draw_count=restored.global_samples_consumed,
            draw_counts=draw_counts,
        )
        if dict(restored.mixer_state) != expected_mixer:
            raise IncompatibleDataStateError("mixer state differs on resume")
        expected_balancer = self._balancer_state(
            epoch=restored.epoch,
            draw_counts=draw_counts,
        )
        if dict(restored.balancer_state) != expected_balancer:
            raise IncompatibleDataStateError("balancer state differs on resume")
        if dict(restored.generator_state) != self._generator_state(epoch=restored.epoch, plan=plan):
            raise IncompatibleDataStateError("generator state differs on resume")
        if dict(restored.temporal_query_state) != dict(current.temporal_query_state):
            raise IncompatibleDataStateError("temporal query state differs on resume")

        if self._sampling.access_mode is DataAccessMode.MAP:
            limit = len(plan.rank_sequence)
            if self._config.drop_last:
                limit -= limit % self._config.batch_size
            if restored.committed_batch_cursor > limit:
                raise IncompatibleDataStateError("committed cursor exceeds rank sequence")
            expected_map_state = {
                "sequence_digest": plan.sequence_digest,
                "rank_assignment_digest": plan.rank_assignment_digest,
                "committed_sample_cursor": restored.committed_batch_cursor,
                "dropped_count": plan.dropped_count,
                "repeated_count": plan.repeated_count,
            }
            if dict(restored.map_sampler_state) != expected_map_state:
                raise IncompatibleDataStateError("map sampler state differs on resume")
            if restored.stream_partition_states or restored.stream_rng_state:
                raise IncompatibleDataStateError("map state cannot carry streaming state")
        else:
            if restored.committed_batch_cursor > cast(int, self._sampling.nominal_epoch_size):
                raise IncompatibleDataStateError("stream cursor exceeds nominal epoch size")
            if restored.map_sampler_state:
                raise IncompatibleDataStateError("stream state cannot carry a map sampler")
            expected_assignments = self._stream_assignments(plan)
            parsed_states: dict[str, StreamPartitionState] = {}
            for key, raw in restored.stream_partition_states.items():
                if not isinstance(raw, Mapping):
                    raise IncompatibleDataStateError("stream worker state must be a mapping")
                if key not in expected_assignments:
                    raise IncompatibleDataStateError(
                        "stream state has an unknown worker assignment"
                    )
                state_value = StreamPartitionState.from_dict(raw)
                worker_id, assigned_units = expected_assignments[key]
                if (
                    state_value.worker_id != worker_id
                    or state_value.epoch != restored.epoch
                    or state_value.assigned_units != assigned_units
                    or state_value.assignment_digest
                    != _stream_assignment_digest(restored.epoch, assigned_units)
                    or state_value.shard_order_digest != plan.sequence_digest
                    or state_value.sample_shuffle_resume_policy
                    != restored.sample_shuffle_resume_policy
                ):
                    raise IncompatibleDataStateError(
                        "stream worker state differs from reconstructed assignment"
                    )
                if (
                    state_value.current_shard is not None
                    and state_value.current_shard not in assigned_units
                ):
                    raise IncompatibleDataStateError("stream current shard is not assigned")
                if state_value.shard_index > len(assigned_units):
                    raise IncompatibleDataStateError("stream shard index exceeds assignment")
                if state_value.shard_rng_state.get("seed") != plan.permutation_seed or (
                    state_value.shard_rng_state.get("shuffle")
                    != self._sampling.stream_shard_shuffle
                ):
                    raise IncompatibleDataStateError("stream shard RNG derivation differs")
                expected_sample_seed = derive_worker_seed(
                    base_seed=self._sampling.base_seed,
                    epoch=restored.epoch,
                    global_rank=self._topology.global_rank,
                    split=self._topology.split,
                    worker_id=worker_id,
                )
                if state_value.sample_rng_state.get("seed") != expected_sample_seed:
                    raise IncompatibleDataStateError("stream sample RNG derivation differs")
                if state_value.sample_shuffle_buffer_state:
                    raise IncompatibleDataStateError(
                        "this loader does not serialize streaming sample buffers"
                    )
                parsed_states[key] = state_value
            if (
                self._sampling.exact_resume
                and restored.committed_batch_cursor > 0
                and not parsed_states
            ):
                raise IncompatibleDataStateError(
                    "exact streaming resume requires committed worker source state"
                )
            expected_rng_state = self._stream_rng_state(restored.stream_partition_states)
            if dict(restored.stream_rng_state) != expected_rng_state:
                raise IncompatibleDataStateError("stream RNG state differs from worker states")
        return restored

    def apply_state(self, state: DataLoaderState) -> None:
        """应用已验证状态并丢弃所有旧预取队列。"""
        self.close_runtime()
        self._closed = False
        self._epoch = state.epoch
        self._global_batches_consumed = state.global_batches_consumed
        self._global_samples_consumed = state.global_samples_consumed
        self._committed_sample_cursor = state.committed_batch_cursor
        self._committed_source_draw_counts = {
            key: cast(int, value)
            for key, value in cast(Mapping[str, object], state.mixer_state["draw_counts"]).items()
        }
        self._stream_partition_states = dict(state.stream_partition_states)
        self._observed_worker_pids.clear()
        self._observed_worker_ids.clear()
        self._observed_actual_worker_count = 0
        self._observed_backend_states.clear()
        self._plan = self._plan_for_epoch(self._epoch)
        self._batch_sampler.set_plan(
            cast(tuple[MapIndex, ...], self._plan.rank_sequence),
            self._committed_sample_cursor,
        )
        self._descriptor = SharedEpochDescriptor(None, self._epoch, self._sampling.base_seed)

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """先完整验证,再原子应用并丢弃历史预取。"""
        if self._iterator is not None:
            raise DataLifecycleError("cannot restore while loader iteration is active")
        self.apply_state(self.validate_state(state))

    def close_runtime(self) -> None:
        """关闭 active iterator、worker、dataset 源和共享 epoch。"""
        loader = self._torch_loader
        iterator = self._iterator or getattr(loader, "_iterator", None)
        dataset = getattr(loader, "dataset", None)
        close_dataset = getattr(dataset, "close", None)
        errors: list[BaseException] = []
        try:
            if iterator is not None and self._torch_version is not None:
                _shutdown_iterator(iterator, self._torch_version)
        except BaseException as exc:
            errors.append(exc)
        try:
            if callable(close_dataset):
                close_dataset()
        except BaseException as exc:
            errors.append(exc)
        finally:
            self._iterator = None
            self._torch_loader = None
            try:
                self._descriptor.close()
            except BaseException as exc:
                errors.append(exc)
        if errors:
            details = ", ".join(repr(extra) for extra in errors[1:])
            message = f"failed to close {len(errors)} DataLoader runtime resource(s)"
            if details:
                message = f"{message}; additional errors: {details}"
            error = RuntimeError(message)
            raise error from errors[0]

    def close(self) -> None:
        """幂等关闭生产运行时并禁止后续迭代。"""
        if self._closed:
            return
        self.close_runtime()
        self._closed = True


__all__ = [
    "AutoVLAMapDataset",
    "AutoVLAStreamingDataset",
    "PlannedBatchSampler",
    "ProductionCollator",
    "RuntimeTopology",
    "SharedEpochDescriptor",
    "SourceFactory",
    "TrainingDataLoader",
    "WorkerInitializer",
]
