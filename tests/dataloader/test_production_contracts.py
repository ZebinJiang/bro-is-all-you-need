"""生产数据核心的契约、构造、状态和 pickle 测试。"""

from __future__ import annotations

import importlib.util
import inspect
import io
import json
import multiprocessing
import os
import pickle
import subprocess
import sys
import tarfile
import threading
import time
from collections.abc import Mapping, Sequence
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol, TypeGuard, cast

import numpy as np
import pytest

import autovla.data.loader as loader_module
from autovla.config.schema import (
    DataConfig,
    DataLoaderConfig,
    DatasetConfig,
    TemporalQueryConfig,
)
from autovla.core.registry import ImportStringFactory
from autovla.core.types.training import TrainingSample as CoreTrainingSample
from autovla.data.backends.base import (
    DataBackend,
    DataBackendCapabilities,
    DataBackendSpec,
    MapDataSource,
    StreamingDataSource,
)
from autovla.data.collators import PaddedBatchCollator
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    PartitionPlan,
    SamplingPlan,
    StreamMode,
    StreamPartitionState,
    WorkerContext,
    derive_worker_seed,
    stable_fingerprint,
)
from autovla.data.loader import (
    AutoVLAMapDataset,
    AutoVLAStreamingDataset,
    EpochSnapshot,
    PlannedBatchSampler,
    ProductionCollator,
    RuntimeTopology,
    SharedEpochDescriptor,
    SourceFactory,
    TrainingDataLoader,
    WorkerEpochState,
    WorkerInitializer,
)
from autovla.data.module import DataModule
from autovla.data.registry import DataBackendRegistration, DataBackendRegistry
from autovla.data.sampling import PartitionContext
from autovla.data.transforms import TransformPipeline
from autovla.data.types import DataLoaderState, DataStage, TrainingSample


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄动态 loader 状态映射。"""
    return isinstance(value, Mapping)


class _ProcessHandle(Protocol):
    """描述跨 Python typing 版本使用的最小进程句柄。"""

    exitcode: int | None

    def start(self) -> None:
        """启动子进程。"""

        ...

    def join(self, timeout: float | None = None) -> None:
        """有界等待子进程。"""

        ...

    def is_alive(self) -> bool:
        """返回子进程是否仍存活。"""

        ...

    def terminate(self) -> None:
        """仅在测试超时时终止当前测试拥有的子进程。"""

        ...


class _PausingSharedArray:
    """在指定共享写入完成后暂停 writer,用于确定性 publication 竞态测试。"""

    def __init__(self, raw: object, pause_after_write: int) -> None:
        self._raw = cast(Any, raw)
        self._pause_after_write = pause_after_write
        self._write_count = 0
        self.paused = threading.Event()
        self.release = threading.Event()

    def __getitem__(self, index: int) -> int:
        """读取底层 RawArray 字。"""

        return int(self._raw[index])

    def __setitem__(self, index: int, value: int) -> None:
        """写入底层字,并在目标 publication point 等待测试释放。"""

        self._raw[index] = value
        self._write_count += 1
        if self._write_count == self._pause_after_write:
            self.paused.set()
            if not self.release.wait(timeout=2.0):
                raise RuntimeError("test did not release paused epoch-state writer")


def _assert_epoch_state_after_parent_advance(
    state: WorkerEpochState,
    initial: EpochSnapshot,
    expected: EpochSnapshot,
) -> None:
    """在子进程内有界等待父更新,并拒绝任意混合字段快照。"""

    for _ in range(100_000):
        snapshot = state.snapshot()
        if snapshot not in (initial, expected):
            raise AssertionError(f"worker observed mixed epoch snapshot {snapshot!r}")
        if snapshot == expected:
            return
    raise AssertionError(f"worker did not observe parent snapshot {expected!r}")


def _string_mapping(value: object) -> Mapping[str, object]:
    """校验 loader 状态使用字符串键。"""
    if not _is_object_mapping(value):
        raise TypeError("expected loader state mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("loader state keys must be strings")
        result[key] = item
    return result


def _is_object_pair(value: object) -> TypeGuard[tuple[object, object]]:
    """收窄流式分配二元组。"""
    return _is_object_tuple(value) and len(value) == 2


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """收窄动态 loader 元组。"""
    return isinstance(value, tuple)


def _stream_assignment(values: Sequence[object]) -> tuple[str, ...]:
    """验证并提取计划中的流式单元。"""
    result: list[str] = []
    for value in values:
        if not _is_object_pair(value):
            raise TypeError("stream assignment must be a pair")
        source_id, unit_id = value
        if not isinstance(source_id, int) or isinstance(source_id, bool):
            raise TypeError("stream assignment source must be an integer")
        if not isinstance(unit_id, str):
            raise TypeError("stream assignment unit must be text")
        result.append(unit_id)
    return tuple(result)


class _TemporalTransportBackend:
    """提供不打开数据的 backend-neutral temporal transport 探针。"""

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """返回固定源身份并声明支持 temporal query。"""
        del stage
        return DataSourceSpec(
            dataset_key=config.name,
            backend_key="temporal_transport_probe",
            split=config.split,
            access_mode=DataAccessMode.MAP,
            source_fingerprint="temporal-probe-source",
            schema_fingerprint="temporal-probe-schema",
            finite=True,
            sample_count=config.sample_count or 4,
            supports_batch_read=True,
            supports_temporal_query=True,
            supports_media=False,
            supports_exact_resume=True,
        )


def create_temporal_transport_backend() -> _TemporalTransportBackend:
    """通过无参数懒工厂构造 transport 探针。"""
    return _TemporalTransportBackend()


def _invalid_source_description(
    _backend: object,
    _config: DatasetConfig,
    _stage: DataStage,
) -> object:
    """返回违反动态后端契约的对象。"""

    return object()


def _temporal_transport_registry() -> DataBackendRegistry:
    """构造只含 backend-neutral transport 探针的本地注册表。"""
    registry = DataBackendRegistry("temporal-transport-test")
    spec = DataBackendSpec(
        key="temporal_transport_probe",
        aliases=(),
        capabilities=DataBackendCapabilities(
            sequential_streaming=False,
            random_access=True,
            persistent_index=False,
            grouped_reads=True,
            deterministic_partition=True,
            prototype_only=False,
            native_compatible=False,
        ),
        factory_path=f"{__name__}:create_temporal_transport_backend",
    )
    registry.register(
        spec.key,
        DataBackendRegistration(
            spec=spec,
            factory=ImportStringFactory(spec.factory_path),
        ),
    )
    return registry


def _map_spec() -> DataSourceSpec:
    """返回无外部依赖的确定性 map 源规格。"""
    return DataSourceSpec(
        dataset_key="tiny",
        backend_key="robodm_container",
        split="train",
        access_mode=DataAccessMode.MAP,
        source_fingerprint="source-fingerprint",
        schema_fingerprint="schema-fingerprint",
        finite=True,
        sample_count=4,
        supports_batch_read=True,
        supports_temporal_query=False,
        supports_media=False,
        supports_exact_resume=True,
    )


def _topology() -> RuntimeTopology:
    """返回零 worker 主进程拓扑。"""
    return RuntimeTopology(0, 0, 1, 7, "train", "none")


def _stream_spec() -> DataSourceSpec:
    """返回包含真实后端 shard 身份的 streaming 源规格。"""
    return DataSourceSpec(
        dataset_key="stream",
        backend_key="webdataset",
        split="train",
        access_mode=DataAccessMode.STREAMING,
        source_fingerprint="stream-source-fingerprint",
        schema_fingerprint="stream-schema-fingerprint",
        finite=True,
        sample_count=None,
        supports_batch_read=False,
        supports_temporal_query=False,
        supports_media=True,
        supports_exact_resume=True,
        partition_units=tuple(f"shard-{index}" for index in range(8)),
        stream_mode=StreamMode.FINITE_EPOCH,
        nominal_epoch_size=8,
    )


def _stream_loader() -> tuple[TrainingDataLoader, PartitionPlan]:
    """构造不打开后端、不导入 Torch 的 streaming loader。"""
    spec = _stream_spec()
    config = DatasetConfig(
        "stream",
        "webdataset",
        "datasets/working/webdataset",
        access_mode="streaming",
        stream_mode="finite_epoch",
        nominal_epoch_size=8,
    )
    units = tuple((0, unit_id) for unit_id in spec.partition_units)
    plan = PartitionPlan.for_streaming(
        units,
        global_rank=0,
        world_size=1,
        logical_worker_count=1,
        seed=7,
        epoch=0,
        shuffle=True,
    )
    sampling = SamplingPlan(
        DataAccessMode.STREAMING,
        2,
        False,
        7,
        stream_shard_shuffle=True,
        nominal_epoch_size=8,
        exact_resume=True,
    )
    factory = SourceFactory(
        "autovla.data.backends.webdataset:create_backend",
        config,
        DataStage.TRAIN,
        spec,
    )
    loader = TrainingDataLoader(
        factories=(factory,),
        source_specs=(spec,),
        partition_plan=plan,
        sampling_plan=sampling,
        config=DataLoaderConfig(batch_size=2, stream_shard_shuffle=True),
        topology=_topology(),
        collator=ProductionCollator(
            PaddedBatchCollator(),
            TransformPipeline(),
            "manifest-fingerprint",
            "statistics-fingerprint",
            (("stream", spec.source_fingerprint, spec.schema_fingerprint),),
        ),
        manifest_fingerprint="manifest-fingerprint",
        mix_strategy="weighted",
        mix_balance_by="dataset",
        mix_weights=(1.0,),
        base_stream_units=units,
    )
    return loader, plan


def test_contract_import_remains_torch_lazy_and_complete() -> None:
    """验证导入契约不导入 Torch 且关键字段完整。"""
    assert {item.name for item in fields(WorkerContext)} == {
        "global_rank",
        "local_rank",
        "world_size",
        "worker_id",
        "logical_worker_count",
        "actual_worker_process_count",
        "base_seed",
        "derived_worker_seed",
        "epoch",
        "split",
        "multiprocessing_start_method",
        "node_id",
        "is_main_process",
    }
    assert {
        "dataset_key",
        "backend_key",
        "split",
        "access_mode",
        "source_fingerprint",
        "schema_fingerprint",
        "finite",
        "sample_count",
        "supports_batch_read",
        "supports_temporal_query",
        "supports_media",
        "supports_exact_resume",
        "partition_units",
    }.issubset({item.name for item in fields(DataSourceSpec)})
    assert tuple(inspect.signature(MapDataSource.read_many).parameters) == (
        "self",
        "indices",
    )
    assert tuple(inspect.signature(StreamingDataSource.iter_samples).parameters) == (
        "self",
        "context",
        "state",
    )
    assert tuple(inspect.signature(DataBackend.describe_stream_partition_units).parameters) == (
        "self",
        "config",
        "stage",
    )
    assert CoreTrainingSample is TrainingSample


def test_data_contract_and_module_setup_remain_torch_lazy_in_fresh_process() -> None:
    """在全新解释器中证明数据契约导入和零 worker setup 不加载 Torch。"""
    script = """
import sys
from autovla.config.schema import DataConfig, DatasetConfig
from autovla.data.module import DataModule
from autovla.data.types import DataStage

module = DataModule(DataConfig(datasets=(DatasetConfig(
    "tiny", "robodm_container", "unused", sample_count=4
),)))
module.setup(DataStage.TRAIN)
assert module.train_dataloader().torch_loader_created is False
assert "torch" not in sys.modules, sorted(name for name in sys.modules if name.startswith("torch"))
module.close()
print("PASS_TORCH_LAZY_DATA_SETUP")
"""
    result = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[2],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "PASS_TORCH_LAZY_DATA_SETUP"


def test_partition_plans_split_map_by_rank_and_stream_by_worker_once() -> None:
    """验证 map 不做 worker 二次切分,stream 先 rank 后 worker。"""
    map_plan = PartitionPlan.for_map(
        tuple((0, index) for index in range(12)),
        global_rank=1,
        world_size=2,
        batch_size=2,
        seed=7,
        epoch=0,
        shuffle=False,
        policy="exact_no_pad",
    )
    stream_plan = PartitionPlan.for_streaming(
        tuple((0, value) for value in ("a", "b", "c", "d", "e", "f")),
        global_rank=1,
        world_size=2,
        logical_worker_count=2,
        seed=7,
        epoch=0,
        shuffle=False,
    )

    assert map_plan.rank_sequence == tuple((0, index) for index in (1, 3, 5, 7, 9, 11))
    assert map_plan.worker_assignments == ()
    assert stream_plan.rank_sequence == ((0, "b"), (0, "d"), (0, "f"))
    assert stream_plan.worker_assignments == (
        ((0, "b"), (0, "f")),
        ((0, "d"),),
    )
    assert len(stream_plan.worker_assignment_digests) == 2
    next_epoch = PartitionPlan.for_streaming(
        tuple((0, value) for value in ("a", "b", "c", "d", "e", "f")),
        global_rank=1,
        world_size=2,
        logical_worker_count=2,
        seed=7,
        epoch=1,
        shuffle=False,
    )
    assert next_epoch.permutation_seed != stream_plan.permutation_seed
    assert next_epoch.sequence_digest != stream_plan.sequence_digest
    assert next_epoch.worker_assignment_digests != stream_plan.worker_assignment_digests


def test_config_rejects_worker_and_cross_mode_misconfiguration() -> None:
    """验证 worker-only、fork 和 map/stream 混用都 fail closed。"""
    with pytest.raises(ValueError, match="prefetch_factor requires"):
        DataLoaderConfig(prefetch_factor=2)
    with pytest.raises(ValueError, match="timeout_seconds requires"):
        DataLoaderConfig(timeout_seconds=1.0)
    with pytest.raises(ValueError, match="canonical NumPy-backed TrainingBatch"):
        DataLoaderConfig(pin_memory=True)
    with pytest.raises(ValueError, match=r"one of.*spawn.*forkserver"):
        DataLoaderConfig(num_workers=1, multiprocessing_context="fork")
    with pytest.raises(ValueError, match="map data cannot"):
        DataConfig(loader=DataLoaderConfig(stream_shard_shuffle=True))
    with pytest.raises(ValueError, match="mixed map and streaming"):
        DataConfig(
            datasets=(
                DatasetConfig("map", "robodm_container", "map", sample_count=1),
                DatasetConfig(
                    "stream",
                    "webdataset",
                    "stream",
                    access_mode="streaming",
                    stream_mode="finite_epoch",
                    nominal_epoch_size=1,
                ),
            )
        )


@pytest.mark.parametrize("temporal_query", (object(), "invalid"))
def test_dataset_config_rejects_invalid_temporal_query_runtime_values(
    temporal_query: TemporalQueryConfig,
) -> None:
    """公开构造器拒绝绕过静态注解的时间查询值。"""

    with pytest.raises(TypeError, match="temporal_query must be TemporalQueryConfig or None"):
        DatasetConfig("invalid-query", "robodm_container", "unused", temporal_query=temporal_query)


@pytest.mark.parametrize("access_mode", ("invalid", object()))
def test_data_source_spec_rejects_invalid_runtime_access_mode(
    access_mode: DataAccessMode,
) -> None:
    """源规格只接受精确 DataAccessMode 枚举。"""

    with pytest.raises(TypeError, match="access_mode must be DataAccessMode"):
        replace(_map_spec(), access_mode=access_mode)


@pytest.mark.parametrize("partition_units", (("",), (object(),)))
def test_data_source_spec_rejects_invalid_partition_units_before_strip(
    partition_units: tuple[str, ...],
) -> None:
    """流式源在调用文本方法前拒绝空项和非字符串项。"""

    with pytest.raises(ValueError, match="partition_units"):
        replace(_stream_spec(), partition_units=partition_units)


@pytest.mark.parametrize("assigned_units", (("",), (object(),)))
def test_stream_state_rejects_invalid_assigned_units_before_strip(
    assigned_units: tuple[str, ...],
) -> None:
    """流状态在调用文本方法前拒绝空项和非字符串项。"""

    with pytest.raises(ValueError, match="assigned_units"):
        StreamPartitionState(
            worker_id=0,
            epoch=0,
            assignment_owner="autovla_loader",
            assigned_units=assigned_units,
            upstream_partitioning_disabled=True,
            assignment_digest="assignment",
            shard_order_digest="order",
        )


@pytest.mark.parametrize("handler_counts", ({1: 0}, {"decode": True}, {"decode": -1}))
def test_stream_state_rejects_invalid_handler_count_keys_and_values(
    handler_counts: Mapping[str, int],
) -> None:
    """handler 计数拒绝非文本键、bool 和负整数。"""

    with pytest.raises(ValueError, match="handler_counts must map names"):
        StreamPartitionState(
            worker_id=0,
            epoch=0,
            assignment_owner="autovla_loader",
            assigned_units=("shard-0",),
            upstream_partitioning_disabled=True,
            assignment_digest="assignment",
            shard_order_digest="order",
            handler_counts=handler_counts,
        )


def test_data_module_rejects_invalid_dynamic_source_description(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """动态后端返回值必须在解引用前通过 DataSourceSpec 校验。"""

    monkeypatch.setattr(_TemporalTransportBackend, "describe_source", _invalid_source_description)
    module = DataModule(
        DataConfig(
            datasets=(
                DatasetConfig(
                    "invalid-description",
                    "temporal_transport_probe",
                    "unused",
                    sample_count=4,
                ),
            )
        ),
        backend_registry=_temporal_transport_registry(),
    )
    try:
        with pytest.raises(TypeError, match="describe_source must return DataSourceSpec"):
            module.setup(DataStage.TRAIN)
    finally:
        module.close()


def test_data_module_constructs_source_driven_loader_without_opening_sources() -> None:
    """验证 setup 只建描述,没有同步 batch executor 或 Torch/runtime handle。"""
    config = DataConfig(
        datasets=(
            DatasetConfig(
                name="tiny",
                backend="robodm_container",
                root="unused",
                sample_count=4,
            ),
        ),
        loader=DataLoaderConfig(batch_size=2),
    )
    module = DataModule(config)
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()

    assert isinstance(loader, TrainingDataLoader)
    assert loader.source_specs[0].dataset_key == "tiny"
    manifest = module.dataset_manifest()
    assert manifest.source_fingerprints == (loader.source_specs[0].source_fingerprint,)
    assert manifest.schema_fingerprints == (loader.source_specs[0].schema_fingerprint,)
    assert (
        replace(
            manifest,
            source_fingerprints=("changed-source-fingerprint",),
        ).fingerprint
        != manifest.fingerprint
    )
    assert (
        replace(
            manifest,
            schema_fingerprints=("changed-schema-fingerprint",),
        ).fingerprint
        != manifest.fingerprint
    )
    assert loader.torch_loader_created is False
    assert "_BatchLoader" not in inspect.getsource(sys.modules[DataModule.__module__])
    assert loader.state_dict()["committed_batch_cursor"] == 0
    module.close()


def test_data_module_preserves_bound_local_rank_as_runtime_fact() -> None:
    """验证 DataModule 不再伪造 local_rank=0。"""
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),)
    )
    module = DataModule(config, partition=PartitionContext(rank=3, local_rank=1, world_size=4))
    module.setup(DataStage.TRAIN)

    assert module.train_dataloader().runtime_topology.local_rank == 1
    module.close()


def test_temporal_query_survives_data_module_factory_pickle_and_resume_guard() -> None:
    """验证查询经规范工厂链传输并在恢复前拒绝漂移。"""
    query = TemporalQueryConfig(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        anchor_semantics="sample",
        boundary_policy="pad",
        action_horizon=3,
    )
    dataset = DatasetConfig(
        "temporal-source",
        "temporal_transport_probe",
        "unused",
        sample_count=4,
        temporal_query=query,
    )
    module = DataModule(
        DataConfig(datasets=(dataset,)),
        backend_registry=_temporal_transport_registry(),
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    factory = loader.source_factories[0]
    state = loader.state_dict()
    temporal_state = state["temporal_query_state"]

    assert not inspect.signature(create_temporal_transport_backend).parameters
    assert factory.config.temporal_query is query
    assert pickle.loads(pickle.dumps(factory)).config.temporal_query == query
    assert module.dataset_manifest().temporal_query_fingerprints == (query.fingerprint,)
    assert isinstance(temporal_state, dict)
    assert temporal_state == {
        "sources": [
            {
                "dataset_key": "temporal-source",
                "query_fingerprint": query.fingerprint,
                "query": query.to_dict(),
            }
        ]
    }

    changed_query = replace(query, frame_offsets=(0, 1, 2))
    changed_module = DataModule(
        DataConfig(datasets=(replace(dataset, temporal_query=changed_query),)),
        backend_registry=_temporal_transport_registry(),
    )
    changed_module.setup(DataStage.TRAIN)
    changed_loader = changed_module.train_dataloader()
    unchanged_state = changed_loader.state_dict()

    with pytest.raises(ValueError, match="temporal_query_fingerprint"):
        changed_loader.load_state_dict(state)
    assert changed_loader.state_dict() == unchanged_state
    changed_module.close()
    module.close()


def test_loader_state_is_complete_strict_and_rejects_compatibility_drift() -> None:
    """验证 v2 状态无占位身份并在应用前拒绝运行契约漂移。"""
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),),
        loader=DataLoaderConfig(batch_size=2),
    )
    module = DataModule(config)
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    state = dict(loader.state_dict())
    restored = DataLoaderState.from_dict(state)

    assert restored.schema_version == "autovla.data_loader_state.v2"
    assert restored.source_fingerprints == (loader.source_specs[0].source_fingerprint,)
    assert "manifest-owned" not in repr(state)
    assert restored.map_sampler_state["rank_assignment_digest"]
    for field_name in ("source_fingerprints", "schema_fingerprints"):
        bad_identity = dict(state)
        bad_identity[field_name] = [f"changed-{field_name}"]
        with pytest.raises(ValueError, match="resume mismatch"):
            loader.load_state_dict(bad_identity)
        assert loader.state_dict() == state
    bad_batch = dict(state)
    bad_batch["batch_size"] = 3
    with pytest.raises(ValueError, match="resume mismatch"):
        loader.validate_state(bad_batch)
    assert loader.state_dict() == state
    with pytest.raises(ValueError, match="fields mismatch"):
        DataLoaderState.from_dict({"schema_version": DataLoaderState.SCHEMA_VERSION})
    module.close()


def test_top_level_dataset_collator_initializer_and_factory_are_pickle_safe() -> None:
    """验证 spawn/forkserver 会传递的对象可由标准 pickle 往返。"""
    descriptor = SharedEpochDescriptor(0, 7)
    topology = _topology()
    source_factory = SourceFactory(
        "autovla.data.backends.robodm:create_backend",
        DatasetConfig("tiny", "robodm_container", "unused", sample_count=4),
        DataStage.TRAIN,
        _map_spec(),
    )
    stream_spec = _stream_spec()
    stream_factory = SourceFactory(
        "autovla.data.backends.webdataset:create_backend",
        DatasetConfig(
            "stream",
            "webdataset",
            "datasets/working/webdataset",
            access_mode="streaming",
            stream_mode="finite_epoch",
            nominal_epoch_size=8,
        ),
        DataStage.TRAIN,
        stream_spec,
    )
    objects = (
        source_factory,
        AutoVLAMapDataset((source_factory,), topology, descriptor),
        ProductionCollator(
            PaddedBatchCollator(),
            TransformPipeline(),
            "manifest-fingerprint",
            "statistics-fingerprint",
            (("tiny", _map_spec().source_fingerprint, _map_spec().schema_fingerprint),),
        ),
        WorkerInitializer(topology, descriptor),
        PlannedBatchSampler(((0, 0), (0, 1)), 2, False),
        AutoVLAStreamingDataset(
            (stream_factory,),
            topology,
            descriptor,
            tuple((0, unit_id) for unit_id in stream_spec.partition_units),
            SamplingPlan(
                DataAccessMode.STREAMING,
                2,
                False,
                7,
                nominal_epoch_size=8,
            ),
        ),
    )

    for value in objects:
        restored = pickle.loads(pickle.dumps(value))
        assert type(restored) is type(value)


def test_worker_epoch_state_zero_worker_contract_and_compatibility_export() -> None:
    """零 worker 与兼容导出共享唯一实现和一致代次语义。"""

    assert SharedEpochDescriptor is WorkerEpochState
    state = WorkerEpochState(3, 17)
    assert state.snapshot() == EpochSnapshot(3, 17, 0)
    updated = state.advance(epoch=4, base_seed=19)
    assert updated == EpochSnapshot(4, 19, 1)
    assert state.read() == (4, 19, 1)
    state.close()
    state.close()
    with pytest.raises(RuntimeError, match="closed"):
        state.snapshot()
    with pytest.raises(RuntimeError, match="closed"):
        state.advance(epoch=5, base_seed=23)


def test_worker_epoch_state_uses_context_owned_public_primitives() -> None:
    """多 worker 状态用同一 spawn 上下文发布一致三元快照。"""

    context = multiprocessing.get_context("spawn")
    state = WorkerEpochState.create(context, epoch=0, base_seed=23)
    try:
        assert state.advance(epoch=1, base_seed=29) == EpochSnapshot(1, 29, 1)
        assert state.snapshot() == EpochSnapshot(1, 29, 1)
        with pytest.raises(ValueError, match="exact uint64"):
            state.advance(epoch=-1, base_seed=29)
        assert state.snapshot() == EpochSnapshot(1, 29, 1)
    finally:
        state.close()


@pytest.mark.parametrize("field", ("epoch", "base_seed", "generation"))
@pytest.mark.parametrize("invalid", (True, 1.0, "1", -1, 2**64))
def test_worker_epoch_state_constructor_and_create_require_exact_uint64(
    field: str,
    invalid: object,
) -> None:
    """本地构造和共享 create 都拒绝非精确 uint64 初始字段。"""

    values: dict[str, object] = {"epoch": 0, "base_seed": 1, "generation": 0}
    values[field] = invalid
    context = multiprocessing.get_context("spawn")
    for shared in (False, True):
        with pytest.raises(ValueError, match="exact uint64"):
            if shared:
                WorkerEpochState.create(
                    context,
                    epoch=cast(Any, values["epoch"]),
                    base_seed=cast(Any, values["base_seed"]),
                    generation=cast(Any, values["generation"]),
                )
            else:
                WorkerEpochState(
                    cast(Any, values["epoch"]),
                    cast(Any, values["base_seed"]),
                    cast(Any, values["generation"]),
                )


@pytest.mark.parametrize("shared", (False, True))
def test_worker_epoch_state_accepts_uint64_boundaries_and_generation_overflow(
    shared: bool,
) -> None:
    """0 和 uint64 上界有效,但 logical generation 不允许溢出。"""

    context = multiprocessing.get_context("spawn")
    state = (
        WorkerEpochState.create(
            context,
            epoch=0,
            base_seed=2**64 - 1,
            generation=2**64 - 1,
        )
        if shared
        else WorkerEpochState(0, 2**64 - 1, 2**64 - 1)
    )
    try:
        assert state.snapshot() == EpochSnapshot(0, 2**64 - 1, 2**64 - 1)
        with pytest.raises(RuntimeError, match="logical generation overflow"):
            state.advance(epoch=1, base_seed=2)
    finally:
        state.close()


@pytest.mark.parametrize("field", ("epoch", "base_seed"))
@pytest.mark.parametrize("invalid", (True, 1.0, "1", -1, 2**64))
def test_worker_epoch_state_advance_rejects_invalid_uint64_without_mutation(
    field: str,
    invalid: object,
) -> None:
    """advance 在 publication 前拒绝无效字段,且保留旧 committed snapshot。"""

    state = WorkerEpochState(3, 17)
    values: dict[str, object] = {"epoch": 4, "base_seed": 19}
    values[field] = invalid
    try:
        with pytest.raises(ValueError, match="exact uint64"):
            state.advance(
                epoch=cast(Any, values["epoch"]),
                base_seed=cast(Any, values["base_seed"]),
            )
        assert state.snapshot() == EpochSnapshot(3, 17, 0)
    finally:
        state.close()


def test_worker_epoch_state_continuous_snapshots_are_coherent_and_rank_local() -> None:
    """连续父写保持逻辑代次,并且两个 rank 状态彼此独立。"""

    context = multiprocessing.get_context("spawn")
    rank_zero = WorkerEpochState.create(context, epoch=0, base_seed=5)
    rank_one = WorkerEpochState.create(context, epoch=0, base_seed=7)
    try:
        for generation in range(1, 257):
            expected = EpochSnapshot(generation, generation * 17 + 5, generation)
            assert (
                rank_zero.advance(
                    epoch=expected.epoch,
                    base_seed=expected.base_seed,
                )
                == expected
            )
            assert rank_zero.snapshot() == expected
        assert rank_one.snapshot() == EpochSnapshot(0, 7, 0)
    finally:
        rank_zero.close()
        rank_one.close()


def test_worker_epoch_state_coherent_fast_path_does_not_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """正常 committed snapshot 不读取时钟、不 yield 也不 sleep。"""

    context = multiprocessing.get_context("spawn")
    state = WorkerEpochState.create(context, epoch=3, base_seed=17)

    def fail_wait_call(*_args: object, **_kwargs: object) -> float:
        """禁止 coherent fast path 调用等待原语。"""

        raise AssertionError("coherent snapshot entered slow wait path")

    try:
        with monkeypatch.context() as patch:
            patch.setattr(time, "monotonic", fail_wait_call)
            patch.setattr(time, "sleep", fail_wait_call)
            assert state.snapshot() == EpochSnapshot(3, 17, 0)
    finally:
        state.close()


@pytest.mark.parametrize("pause_after_write", range(1, 8))
def test_worker_epoch_state_reader_survives_each_inflight_publication_point(
    pause_after_write: int,
) -> None:
    """writer 在七个写点被抢占时,reader 等待并最终读取完整提交。"""

    context = multiprocessing.get_context("spawn")
    state = WorkerEpochState.create(context, epoch=0, base_seed=11)
    pausing = _PausingSharedArray(cast(Any, state)._shared, pause_after_write)
    cast(Any, state)._shared = pausing
    expected = EpochSnapshot(1, 29, 1)
    writer_errors: list[BaseException] = []
    reader_errors: list[BaseException] = []
    reader_results: list[EpochSnapshot] = []
    reader_started = threading.Event()
    reader_done = threading.Event()

    def publish() -> None:
        """在测试 writer thread 发布下一代。"""

        try:
            state.advance(epoch=expected.epoch, base_seed=expected.base_seed)
        except BaseException as exc:
            writer_errors.append(exc)

    def read() -> None:
        """在测试 reader thread 读取 publication 结果。"""

        reader_started.set()
        try:
            reader_results.append(state.snapshot())
        except BaseException as exc:
            reader_errors.append(exc)
        finally:
            reader_done.set()

    writer = threading.Thread(target=publish, name=f"epoch-writer-{pause_after_write}")
    reader = threading.Thread(target=read, name=f"epoch-reader-{pause_after_write}")
    try:
        writer.start()
        assert pausing.paused.wait(timeout=1.0)
        reader.start()
        assert reader_started.wait(timeout=1.0)
        if pause_after_write < 7:
            assert not reader_done.wait(timeout=0.030)
        else:
            assert reader_done.wait(timeout=0.100)
    finally:
        pausing.release.set()
        writer.join(timeout=2.0)
        reader.join(timeout=2.0)
        state.close()
    assert not writer.is_alive()
    assert not reader.is_alive()
    assert writer_errors == []
    assert reader_errors == []
    assert reader_results == [expected]


@pytest.mark.parametrize(
    "start_method",
    [
        method
        for method in ("spawn", "forkserver")
        if method in multiprocessing.get_all_start_methods()
    ],
)
def test_worker_epoch_state_is_pickle_safe_and_observes_parent_advance(
    start_method: str,
) -> None:
    """spawn/forkserver 子进程反序列化后可读取父进程的新代次。"""

    context = multiprocessing.get_context(start_method)
    state = WorkerEpochState.create(context, epoch=0, base_seed=11)
    initial = EpochSnapshot(0, 11, 0)
    expected = EpochSnapshot(1, 29, 1)
    process = cast(
        _ProcessHandle,
        cast(Any, context).Process(
            target=_assert_epoch_state_after_parent_advance,
            args=(state, initial, expected),
        ),
    )
    timed_out = False
    try:
        process.start()
        assert state.advance(epoch=1, base_seed=29) == expected
        process.join(timeout=10.0)
        timed_out = process.is_alive()
        if timed_out:
            process.terminate()
            process.join(timeout=5.0)
        assert not timed_out
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(timeout=5.0)
        state.close()


@pytest.mark.parametrize(("head", "tail"), ((1, 1), (0, 2)))
def test_worker_epoch_state_version_protocol_stall_fails_after_deadline(
    head: int,
    tail: int,
) -> None:
    """永久 odd 或稳定版本分裂在 scheduler-scale deadline 后失败关闭。"""

    context = multiprocessing.get_context("spawn")
    state = WorkerEpochState.create(context, epoch=0, base_seed=13)
    shared = cast(Any, state)._shared
    shared[0] = head
    shared[4] = tail
    started = time.monotonic()
    try:
        with pytest.raises(RuntimeError, match=r"version protocol.*0\.250 seconds"):
            state.snapshot()
        elapsed = time.monotonic() - started
        assert elapsed >= 0.225
        assert elapsed < 1.0
    finally:
        state.close()
        state.close()


def test_worker_epoch_state_has_no_named_shared_memory_dependency() -> None:
    """生产 epoch 状态不得依赖命名段或 resource tracker 绕过。"""

    source = inspect.getsource(WorkerEpochState)
    assert "shared_memory" not in source
    assert "resource_tracker" not in source
    assert "unregister" not in source
    assert "context.RawArray" in source
    assert "context.Array" not in source
    assert "get_lock" not in source


def test_state_apply_replaces_worker_epoch_runtime() -> None:
    """恢复提交状态时必须关闭旧状态并创建独立的新运行时。"""

    loader, _ = _stream_loader()
    old_state: object = getattr(loader, "_descriptor", None)
    if not isinstance(old_state, WorkerEpochState):
        raise TypeError("training loader descriptor must be WorkerEpochState")
    restored = loader.validate_state(loader.state_dict())
    loader.apply_state(restored)
    new_state: object = getattr(loader, "_descriptor", None)
    if not isinstance(new_state, WorkerEpochState):
        raise TypeError("restored loader descriptor must be WorkerEpochState")
    assert new_state is not old_state
    assert new_state.snapshot() == EpochSnapshot(restored.epoch, 7, 0)
    with pytest.raises(RuntimeError, match="closed"):
        old_state.snapshot()
    loader.close()


def _write_spawn_robodm_fixture(root: Path, *, sample_count: int = 4) -> None:
    """写入跨两个 worker 可确定性遍历的最小 RoboDM fixture。"""
    container = root / "containers" / "tiny.tar"
    container.parent.mkdir(parents=True)
    index_rows: list[dict[str, object]] = []
    with tarfile.open(container, "w") as archive:
        for index in range(sample_count):
            prefix = f"sample-{index}"
            payload = {
                "language": "pick the block",
                "action": [[float(index), float(index + 1)]],
                "action_mask": [[True, True]],
                "state": [float(index), 1.0],
                "sample_id": f"sample-{index:06d}",
            }
            camera_buffer = io.BytesIO()
            np.save(
                camera_buffer,
                np.full((2, 2, 3), index, dtype=np.uint8),
                allow_pickle=False,
            )
            for name, content in (
                (f"{prefix}/payload.json", json.dumps(payload).encode("utf-8")),
                (f"{prefix}/camera_0.npy", camera_buffer.getvalue()),
            ):
                member = tarfile.TarInfo(name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
            index_rows.append({"container": "containers/tiny.tar", "member_prefix": prefix})
    (root / "sample_index.jsonl").write_text(
        "".join(json.dumps(row) + "\n" for row in index_rows),
        encoding="utf-8",
    )


def _assert_persistent_workers_reused_and_closed(
    tmp_path: Path,
    *,
    start_method: str,
) -> None:
    """验证指定安全上下文跨 epoch 复用 worker,并在关闭后回收。"""

    root = tmp_path / f"robodm-{start_method}"
    _write_spawn_robodm_fixture(root)
    module = DataModule(
        DataConfig(
            datasets=(
                DatasetConfig(
                    "tiny",
                    "robodm_container",
                    str(root),
                    sample_count=4,
                ),
            ),
            loader=DataLoaderConfig(
                batch_size=1,
                num_workers=2,
                persistent_workers=True,
                prefetch_factor=2,
                multiprocessing_context=start_method,
            ),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    first_pids: tuple[int, ...] = ()
    ownership: Any | None = None
    try:
        first = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        first_telemetry = dict(loader.runtime_telemetry)
        first_pids = cast(tuple[int, ...], first_telemetry["observed_worker_pids"])
        ownership = getattr(loader, "_process_context", None)
        assert ownership is not None
        assert ownership.retained_counts == (3, 1, 2)
        assert not ownership.closed
        second = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        second_telemetry = dict(loader.runtime_telemetry)
        assert first == second == [f"sample-{index:06d}" for index in range(4)]
        assert len(set(first)) == 4
        assert first_telemetry["observed_worker_ids"] == (0, 1)
        assert len(first_pids) == 2
        assert second_telemetry["observed_worker_pids"] == first_pids
        backend_states = cast(
            Mapping[str, Mapping[str, object]],
            second_telemetry["backend_states"],
        )
        backend_state = backend_states["tiny"]
        handle_counters = cast(Mapping[str, int], backend_state["handle_counters"])
        assert handle_counters["opens"] >= 1
        assert handle_counters["cache_hits"] >= 1
        assert ownership.retained_counts == (3, 1, 2)
        assert not ownership.closed
    finally:
        module.close()
    assert ownership is not None
    assert ownership.closed
    assert ownership.retained_counts == (0, 0, 0)
    deadline = time.monotonic() + 5.0
    alive = set(first_pids)
    while alive and time.monotonic() < deadline:
        alive &= {child.pid for child in multiprocessing.active_children()}
        if alive:
            time.sleep(0.05)
    assert not alive


def test_dataloader_process_ownership_uses_only_public_context_surface() -> None:
    """父进程所有权与静默期不得引入私有清理或拓扑变更。"""

    context_type = vars(loader_module)["_DataLoaderProcessContext"]
    detach_method = vars(TrainingDataLoader)["_shutdown_and_detach_runtime"]
    ownership_source = inspect.getsource(context_type)
    detach_source = inspect.getsource(detach_method)
    close_source = inspect.getsource(TrainingDataLoader.close_runtime)
    iteration_source = inspect.getsource(TrainingDataLoader.__iter__)
    for source in (ownership_source, detach_source, close_source):
        assert "resource_tracker" not in source
        assert "sem_unlink" not in source
        assert "_multiprocessing" not in source
        assert "set_start_method" not in source
        assert "set_sharing_strategy" not in source
        assert "SharedMemory" not in source
        assert "sleep(" not in source
        assert "except FileNotFoundError" not in source
    assert close_source.count("gc.collect()") == 1
    assert "_shutdown_and_detach_runtime" in close_source
    assert "gc.collect" not in iteration_source
    assert "self._torch_loader = None" in detach_source
    assert "self._runtime_iterator = None" in detach_source
    assert "self._process_context = None" in detach_source


def _run_concurrent_spawn_parent(root_text: str, connection: Any) -> None:
    """在独立 rank-like 父进程内完成两轮真实 persistent worker 生命周期。"""

    try:
        _assert_persistent_workers_reused_and_closed(
            Path(root_text),
            start_method="spawn",
        )
    except BaseException as exc:
        connection.send(("error", type(exc).__name__, str(exc)))
        raise
    else:
        connection.send(("ok",))
    finally:
        connection.close()


def _join_test_process(process: _ProcessHandle, *, timeout: float = 40.0) -> None:
    """有界等待测试拥有的父进程,超时后只终止该测试进程。"""

    process.join(timeout)
    if process.is_alive():
        process.terminate()
        process.join(5.0)
        raise AssertionError("spawn lifecycle test parent did not exit within timeout")


def _assert_no_new_active_children(before: set[int | None]) -> None:
    """有界确认测试新增的全部进程均已退出。"""

    deadline = time.monotonic() + 5.0
    unexpected = {child.pid for child in multiprocessing.active_children()} - before
    while unexpected and time.monotonic() < deadline:
        time.sleep(0.05)
        unexpected = {child.pid for child in multiprocessing.active_children()} - before
    assert not unexpected


_FRESH_PROCESS_QUIESCENCE_SCRIPT = r"""
import gc
import json
import multiprocessing
import sys
import weakref
from pathlib import Path
from types import SimpleNamespace

import autovla.data.loader as loader_module
from autovla.config.schema import DataConfig, DataLoaderConfig, DatasetConfig
from autovla.data.module import DataModule
from autovla.data.types import DataStage


def main() -> None:
    '''在独立解释器中重复验证真实 worker 资源图静默期。'''

    root = Path(sys.argv[1])
    start_method = sys.argv[2]
    repetitions = int(sys.argv[3])
    gc.disable()
    real_gc = gc
    collect_count = [0]
    graph_refs = []
    ipc_refs = []

    def collect() -> int:
        '''记录生产 close 触发并委托真实标准库收集。'''

        collect_count[0] += 1
        return real_gc.collect()

    loader_module.gc = SimpleNamespace(collect=collect)
    context_type = vars(loader_module)["_DataLoaderProcessContext"]
    original_context_close = context_type.close
    original_detach = loader_module.TrainingDataLoader._shutdown_and_detach_runtime

    def observe_context_close(context) -> None:
        '''在所有权根清空前仅记录公开对象 weakref。'''

        values = (*context._queues, *context._events, *context._processes)
        ipc_refs.append([weakref.ref(value) for value in values])
        original_context_close(context)

    def observe_detach(loader) -> bool:
        '''在 helper 入口仅记录 Torch 资源图 weakref。'''

        torch_loader = loader._torch_loader
        values = (
            torch_loader,
            loader._runtime_iterator,
            loader._iterator,
            loader._process_context,
            None if torch_loader is None else getattr(torch_loader, "dataset", None),
        )
        references = [weakref.ref(value) for value in values if value is not None]
        if references:
            graph_refs.append(references)
        return original_detach(loader)

    context_type.close = observe_context_close
    loader_module.TrainingDataLoader._shutdown_and_detach_runtime = observe_detach
    expected = [f"sample-{index:06d}" for index in range(4)]
    for iteration in range(repetitions):
        module = DataModule(DataConfig(
            datasets=(DatasetConfig(
                "tiny",
                "robodm_container",
                str(root),
                sample_count=4,
            ),),
            loader=DataLoaderConfig(
                batch_size=1,
                num_workers=2,
                persistent_workers=True,
                prefetch_factor=2,
                multiprocessing_context=start_method,
            ),
        ))
        module.setup(DataStage.TRAIN)
        loader = module.train_dataloader()
        first = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        second = [str(batch.sample_source[0]["sample_id"]) for batch in loader]
        if first != expected or second != expected:
            raise AssertionError((first, second))
        if collect_count[0] != iteration:
            raise AssertionError("training iteration invoked quiescence collection")
        module.close()
        if collect_count[0] != iteration + 1:
            raise AssertionError("resource close did not collect exactly once")
        if any(reference() is not None for refs in graph_refs for reference in refs):
            raise AssertionError("Torch DataLoader resource graph remains strongly referenced")
        if any(reference() is not None for refs in ipc_refs for reference in refs):
            raise AssertionError("multiprocessing resource remains strongly referenced")
        if multiprocessing.active_children():
            raise AssertionError("fresh process retained active children")
        loader.close_runtime()
        module.close()
        if collect_count[0] != iteration + 1:
            raise AssertionError("repeated close invoked quiescence collection")
    print(json.dumps({
        "active_children": [child.pid for child in multiprocessing.active_children()],
        "collect_count": collect_count[0],
        "gc_enabled": gc.isenabled(),
        "graph_observation_count": len(graph_refs),
        "ipc_observation_count": len(ipc_refs),
        "repetitions": repetitions,
        "start_method": start_method,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
"""


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; fresh-process quiescence proof requires the selected runtime",
)
@pytest.mark.parametrize("start_method", ("spawn", "forkserver"))
def test_fresh_process_close_quiesces_public_worker_graph(
    tmp_path: Path,
    start_method: str,
) -> None:
    """关闭时在禁用 ambient GC 的新进程中释放完整公开资源图。"""

    if start_method not in multiprocessing.get_all_start_methods():
        pytest.skip(f"multiprocessing start method {start_method!r} is unavailable")
    root = tmp_path / f"quiescence-{start_method}"
    _write_spawn_robodm_fixture(root)
    environment = dict(os.environ)
    environment.update(PYTHONDONTWRITEBYTECODE="1", TMPDIR="/tmp")
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            _FRESH_PROCESS_QUIESCENCE_SCRIPT,
            str(root),
            start_method,
            "3",
        ],
        cwd=Path.cwd(),
        env=environment,
        text=True,
        capture_output=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload == {
        "active_children": [],
        "collect_count": 3,
        "gc_enabled": False,
        "graph_observation_count": 3,
        "ipc_observation_count": 3,
        "repetitions": 3,
        "start_method": start_method,
    }
    for forbidden in (
        "Finalize object",
        "FileNotFoundError",
        "leaked semaphore",
        "resource_tracker",
        "sem_unlink",
    ):
        assert forbidden not in result.stderr


def test_quiescence_collects_once_only_after_real_zero_worker_runtime_close(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """零 worker 仅在真实 Torch 资源图关闭时收集一次。"""

    root = tmp_path / "quiescence-zero-worker"
    _write_spawn_robodm_fixture(root)
    module = DataModule(
        DataConfig(
            datasets=(DatasetConfig("tiny", "robodm_container", str(root), sample_count=4),),
            loader=DataLoaderConfig(batch_size=1, num_workers=0),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    collect_calls: list[str] = []

    def collect() -> int:
        """记录静默期调用而不触发测试进程全局收集。"""

        collect_calls.append("collect")
        return 0

    monkeypatch.setattr(loader_module, "gc", SimpleNamespace(collect=collect))
    loader.close_runtime()
    assert collect_calls == []
    assert len(list(loader)) == 4
    assert collect_calls == []
    loader.close_runtime()
    loader.close_runtime()
    loader.close()
    module.close()
    assert collect_calls == ["collect"]


def test_engine_closes_loader_quiescence_before_strategy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 DataModule 静默期必须在 TrainingEngine strategy.close 前完成。"""

    from autovla.training.engine import TrainingEngine

    root = tmp_path / "quiescence-engine-order"
    _write_spawn_robodm_fixture(root)
    module = DataModule(
        DataConfig(
            datasets=(DatasetConfig("tiny", "robodm_container", str(root), sample_count=4),),
            loader=DataLoaderConfig(batch_size=1, num_workers=0),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    assert len(list(loader)) == 4
    events: list[str] = []

    def collect() -> int:
        """在收集入口验证 helper 已完成所有 self detach。"""

        assert getattr(loader, "_torch_loader", None) is None
        assert getattr(loader, "_runtime_iterator", None) is None
        assert getattr(loader, "_process_context", None) is None
        events.append("collect")
        return 0

    class CloseRecorder:
        """记录公开 close 顺序并可委托真实关闭。"""

        def __init__(self, name: str, action: Any | None = None) -> None:
            self.name = name
            self.action = action

        def close(self) -> None:
            """执行可选真实关闭后记录事件。"""

            if callable(self.action):
                self.action()
            events.append(self.name)

    monkeypatch.setattr(loader_module, "gc", SimpleNamespace(collect=collect))
    context = SimpleNamespace(
        metric_logger=CloseRecorder("metric"),
        data_module=CloseRecorder("data", module.close),
        strategy=CloseRecorder("strategy"),
    )
    engine = TrainingEngine(cast(Any, context))
    engine.close()
    engine.close()
    assert events == ["metric", "collect", "data", "strategy"]


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; actual spawned DataLoader proof requires the selected runtime",
)
def test_spawn_workers_persist_across_epochs_and_close_without_children(tmp_path: Path) -> None:
    """真实 spawn worker=2 完成两 epoch、复用 PID 并在关闭后全部退出。"""
    _assert_persistent_workers_reused_and_closed(tmp_path, start_method="spawn")


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; concurrent spawned DataLoader proof requires the selected runtime",
)
def test_two_concurrent_spawn_parents_retain_worker_resources(
    tmp_path: Path,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """两个并发父进程各持有两个 persistent worker 并完成两轮。"""

    before = {child.pid for child in multiprocessing.active_children()}
    context = multiprocessing.get_context("spawn")
    receivers: list[Any] = []
    processes: list[_ProcessHandle] = []
    for rank in range(2):
        receiver, sender = context.Pipe(duplex=False)
        process = cast(
            _ProcessHandle,
            context.Process(
                target=_run_concurrent_spawn_parent,
                args=(str(tmp_path / f"rank-{rank}"), sender),
            ),
        )
        receivers.append(receiver)
        processes.append(process)
    for process in processes:
        process.start()
    for process in processes:
        _join_test_process(process)
    outcomes = [receiver.recv() for receiver in receivers]
    for receiver in receivers:
        receiver.close()
    assert outcomes == [("ok",), ("ok",)]
    assert [process.exitcode for process in processes] == [0, 0]
    _assert_no_new_active_children(before)
    captured = capfd.readouterr()
    assert "resource_tracker" not in captured.err
    assert "leaked semaphore" not in captured.err


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None
    or "forkserver" not in multiprocessing.get_all_start_methods(),
    reason="Torch or forkserver unavailable in the selected runtime",
)
def test_forkserver_workers_persist_across_epochs_and_close_without_children(
    tmp_path: Path,
) -> None:
    """支持 forkserver 时,同样验证 worker=2 两 epoch 生命周期。"""

    _assert_persistent_workers_reused_and_closed(tmp_path, start_method="forkserver")


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; worker exception teardown requires the selected runtime",
)
def test_worker_epoch_state_exception_path_closes_spawn_children(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """worker 初始化遇到版本协议停滞时失败关闭,且异常路径不遗留子进程。"""

    root = tmp_path / "robodm-spawn-version-stall"
    _write_spawn_robodm_fixture(root)
    original_create = WorkerEpochState.create

    def create_stalled_state(
        context: object,
        *,
        epoch: int,
        base_seed: int,
        generation: int = 0,
    ) -> WorkerEpochState:
        """构造仅供异常测试使用的永久奇数版本。"""

        state = original_create(
            cast(Any, context),
            epoch=epoch,
            base_seed=base_seed,
            generation=generation,
        )
        shared = cast(Any, state)._shared
        shared[0] = 1
        shared[4] = 1
        return state

    monkeypatch.setattr(
        WorkerEpochState,
        "create",
        staticmethod(create_stalled_state),
    )
    before = {child.pid for child in multiprocessing.active_children()}
    module = DataModule(
        DataConfig(
            datasets=(
                DatasetConfig(
                    "tiny",
                    "robodm_container",
                    str(root),
                    sample_count=4,
                ),
            ),
            loader=DataLoaderConfig(
                batch_size=1,
                num_workers=2,
                persistent_workers=True,
                multiprocessing_context="spawn",
            ),
        )
    )
    try:
        module.setup(DataStage.TRAIN)
        with pytest.raises(RuntimeError, match=r"version protocol.*0\.250 seconds"):
            next(iter(module.train_dataloader()))
    finally:
        module.close()
    deadline = time.monotonic() + 5.0
    unexpected = {child.pid for child in multiprocessing.active_children()} - before
    while unexpected and time.monotonic() < deadline:
        time.sleep(0.05)
        unexpected = {child.pid for child in multiprocessing.active_children()} - before
    assert not unexpected


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; partial worker-start proof requires the selected runtime",
)
@pytest.mark.filterwarnings(
    "ignore:Exception ignored in.*_MultiProcessingDataLoaderIter.__del__"
    ":pytest.PytestUnraisableExceptionWarning"
)
def test_partial_spawn_worker_start_releases_parent_ownership(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capfd: pytest.CaptureFixture[str],
) -> None:
    """第二个 worker 启动失败时回收首个 worker 与父进程同步对象。"""

    root = tmp_path / "robodm-partial-worker-start"
    _write_spawn_robodm_fixture(root)
    context_type = vars(loader_module)["_DataLoaderProcessContext"]
    original_close = context_type.close
    closed_ownership: list[Any] = []
    retained_before_close: list[tuple[int, int, int]] = []
    collect_calls: list[str] = []

    def record_close(ownership: Any) -> None:
        """记录异常路径实际关闭的父进程所有权根。"""

        retained_before_close.append(ownership.retained_counts)
        original_close(ownership)
        closed_ownership.append(ownership)

    monkeypatch.setattr(context_type, "close", record_close)
    monkeypatch.setattr(
        loader_module,
        "gc",
        SimpleNamespace(collect=lambda: collect_calls.append("collect") or 0),
    )
    process_type = type(multiprocessing.get_context("spawn").Process())
    original_start = cast(Any, process_type.start)
    start_calls = 0

    def fail_second_start(process: Any) -> None:
        """只在第二个 DataLoader worker start 前注入确定性异常。"""

        nonlocal start_calls
        start_calls += 1
        if start_calls == 2:
            raise RuntimeError("injected second worker start failure")
        original_start(process)

    monkeypatch.setattr(process_type, "start", fail_second_start)
    before = {child.pid for child in multiprocessing.active_children()}
    module = DataModule(
        DataConfig(
            datasets=(
                DatasetConfig(
                    "tiny",
                    "robodm_container",
                    str(root),
                    sample_count=4,
                ),
            ),
            loader=DataLoaderConfig(
                batch_size=1,
                num_workers=2,
                persistent_workers=True,
                multiprocessing_context="spawn",
            ),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    try:
        with pytest.raises(RuntimeError, match="injected second worker start failure"):
            next(iter(loader))
    finally:
        module.close()
    assert start_calls == 2
    assert len(closed_ownership) == 1
    assert retained_before_close == [(3, 1, 2)]
    ownership = closed_ownership[0]
    assert ownership.closed
    assert ownership.retained_counts == (0, 0, 0)
    assert getattr(loader, "_torch_loader", None) is None
    assert getattr(loader, "_runtime_iterator", None) is None
    assert getattr(loader, "_process_context", None) is None
    assert collect_calls == ["collect"]
    _assert_no_new_active_children(before)
    captured = capfd.readouterr()
    assert "resource_tracker" not in captured.err
    assert "leaked semaphore" not in captured.err


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable; fresh-process DataLoader resume proof requires the selected runtime",
)
def test_fresh_process_resume_delivers_exact_next_sample(tmp_path: Path) -> None:
    """独立解释器保存游标后恢复,首个交付身份必须是精确下一样本。"""
    root = tmp_path / "robodm-resume"
    state_path = tmp_path / "data-state.json"
    _write_spawn_robodm_fixture(root)
    script = """
import json
import sys
from pathlib import Path
from autovla.config.schema import DataConfig, DataLoaderConfig, DatasetConfig
from autovla.data.module import DataModule
from autovla.data.types import DataStage

mode, root_text, state_text = sys.argv[1:]
module = DataModule(DataConfig(
    datasets=(DatasetConfig("tiny", "robodm_container", root_text, sample_count=4),),
    loader=DataLoaderConfig(batch_size=1),
))
module.setup(DataStage.TRAIN)
if mode == "resume":
    module.load_state_dict(json.loads(Path(state_text).read_text(encoding="utf-8")))
batch = next(iter(module.train_dataloader()))
print(batch.sample_source[0]["sample_id"])
if mode == "save":
    Path(state_text).write_text(json.dumps(module.state_dict()), encoding="utf-8")
module.close()
"""

    def run(mode: str) -> subprocess.CompletedProcess[str]:
        """执行一个全新解释器阶段。"""
        return subprocess.run(
            [sys.executable, "-c", script, mode, str(root), str(state_path)],
            cwd=Path(__file__).resolve().parents[2],
            check=False,
            capture_output=True,
            text=True,
        )

    saved = run("save")
    assert saved.returncode == 0, saved.stderr
    assert saved.stdout.strip() == "sample-000000"
    resumed = run("resume")
    assert resumed.returncode == 0, resumed.stderr
    assert resumed.stdout.strip() == "sample-000001"


@pytest.mark.skipif(
    importlib.util.find_spec("torch") is None,
    reason="Torch unavailable in AC3 writer environment; actual DataLoader runtime deferred",
)
def test_real_torch_loader_is_constructed_only_when_iteration_starts(
    tmp_path: Path,
) -> None:
    """在可用环境中验证 production facade 延迟构造标准 Torch loader。"""
    root = tmp_path / "robodm"
    container = root / "containers" / "tiny.tar"
    container.parent.mkdir(parents=True)
    payload = {
        "language": "pick the block",
        "action": [[0.25, -0.5]],
        "action_mask": [[True, True]],
        "state": [0.0, 1.0],
        "sample_id": "tiny-0",
    }
    camera_buffer = io.BytesIO()
    np.save(camera_buffer, np.zeros((2, 2, 3), dtype=np.uint8), allow_pickle=False)
    with tarfile.open(container, "w") as archive:
        for name, content in (
            ("sample-0/payload.json", json.dumps(payload).encode("utf-8")),
            ("sample-0/camera_0.npy", camera_buffer.getvalue()),
        ):
            member = tarfile.TarInfo(name)
            member.size = len(content)
            archive.addfile(member, io.BytesIO(content))
    (root / "sample_index.jsonl").write_text(
        json.dumps({"container": "containers/tiny.tar", "member_prefix": "sample-0"}) + "\n",
        encoding="utf-8",
    )
    config = DataConfig(
        datasets=(DatasetConfig("tiny", "robodm_container", str(root), sample_count=1),),
        loader=DataLoaderConfig(batch_size=1, num_workers=0),
    )
    module = DataModule(config)
    try:
        module.setup(DataStage.TRAIN)
        loader = module.train_dataloader()

        assert loader.torch_loader_created is False
        iterator = iter(loader)
        batch = next(iterator)
        assert loader.torch_loader_created is True
        assert batch.language == ("pick the block",)
        assert batch.actions.shape == (1, 1, 2)
        assert batch.sample_source[0]["sample_id"] == "tiny-0"
    finally:
        module.close()


def test_sampling_plan_requires_serialized_stream_shuffle_state() -> None:
    """验证 exact stream resume 不接受未序列化 sample buffer。"""
    with pytest.raises(ValueError, match="stream_sample_shuffle_buffer=0"):
        SamplingPlan(
            DataAccessMode.STREAMING,
            2,
            False,
            7,
            stream_sample_shuffle_buffer=4,
            nominal_epoch_size=8,
            exact_resume=True,
        )
    spec = DataSourceSpec(
        dataset_key="stream",
        backend_key="webdataset",
        split="train",
        access_mode=DataAccessMode.STREAMING,
        source_fingerprint="source",
        schema_fingerprint="schema",
        finite=False,
        sample_count=None,
        supports_batch_read=False,
        supports_temporal_query=False,
        supports_media=True,
        supports_exact_resume=True,
        partition_units=("shard-0",),
        stream_mode=StreamMode.RESAMPLED,
        nominal_epoch_size=8,
    )
    assert spec.stream_mode is StreamMode.RESAMPLED


def test_production_collation_preserves_ordered_source_and_physical_provenance() -> None:
    """验证混合数据的 store/source/schema 和物理来源按样本顺序保留。"""

    def sample(
        dataset_key: str,
        store_fingerprint: str,
        container: str,
        member: str,
        frame_index: int,
    ) -> TrainingSample:
        """构造携带 backend 物理与逻辑来源的最小样本。"""
        return TrainingSample(
            images={"front": np.full((2, 2, 3), frame_index, dtype=np.uint8)},
            language=f"sample-{frame_index}",
            actions=np.asarray([[frame_index, frame_index + 1]], dtype=np.float32),
            action_mask=np.ones((1, 2), dtype=np.bool_),
            sample_source={
                "dataset": dataset_key,
                "physical": {"container": container, "member": member},
                "logical": {"frame_index": frame_index},
            },
            dataset_fingerprint=store_fingerprint,
            transform_fingerprint="backend-transform",
            statistics_fingerprint="backend-statistics",
        )

    collator = ProductionCollator(
        PaddedBatchCollator(),
        TransformPipeline(),
        "dataset-manifest-fingerprint",
        "resolved-statistics-fingerprint",
        (
            ("source-a", "source-fingerprint-a", "schema-fingerprint-a"),
            ("source-b", "source-fingerprint-b", "schema-fingerprint-b"),
        ),
    )
    batch = collator(
        (
            sample("source-b", "store-fingerprint-b", "b.tar", "2.json", 2),
            sample("source-a", "store-fingerprint-a", "a.tar", "1.json", 1),
        )
    )

    assert batch.dataset_fingerprint == "dataset-manifest-fingerprint"
    assert batch.dataset_manifest_fingerprint == "dataset-manifest-fingerprint"
    assert batch.store_fingerprints == (
        "store-fingerprint-b",
        "store-fingerprint-a",
    )
    assert batch.source_fingerprints == (
        "source-fingerprint-b",
        "source-fingerprint-a",
    )
    assert batch.schema_fingerprints == (
        "schema-fingerprint-b",
        "schema-fingerprint-a",
    )
    assert batch.sample_source[0]["physical"] == {
        "container": "b.tar",
        "member": "2.json",
    }
    assert batch.sample_source[1]["physical"] == {
        "container": "a.tar",
        "member": "1.json",
    }
    assert batch.sample_source[0]["logical"] == {"frame_index": 2}
    assert batch.sample_source[1]["logical"] == {"frame_index": 1}


def test_stream_resume_state_binds_assignment_rng_and_backend_state() -> None:
    """验证恢复状态保留后端载荷并绑定当前 epoch 的 worker assignment。"""
    loader, plan = _stream_loader()
    assignment = _stream_assignment(plan.worker_assignments[0])
    worker_state = StreamPartitionState(
        worker_id=0,
        epoch=0,
        assignment_owner="autovla_loader",
        assigned_units=assignment,
        upstream_partitioning_disabled=True,
        assignment_digest=stable_fingerprint({"epoch": 0, "assigned_units": assignment}),
        shard_order_digest=plan.sequence_digest,
        current_shard=assignment[0],
        shard_rng_state={"seed": plan.permutation_seed, "shuffle": True},
        sample_rng_state={
            "seed": derive_worker_seed(
                base_seed=7,
                epoch=0,
                global_rank=0,
                split="train",
                worker_id=0,
            )
        },
        source_state={"backend_cursor": "member-3"},
    )
    state = dict(loader.state_dict())
    state["stream_partition_states"] = {"stream:0": worker_state.to_dict()}
    state["stream_rng_state"] = {
        "stream:0": {
            "shard_rng_state": dict(worker_state.shard_rng_state),
            "sample_rng_state": dict(worker_state.sample_rng_state),
        }
    }

    restored = loader.validate_state(state)
    restored_worker = StreamPartitionState.from_dict(
        _string_mapping(restored.stream_partition_states["stream:0"])
    )
    assert restored.sample_shuffle_resume_policy == "disabled_for_exact_resume"
    assert restored.sample_shuffle_buffer_state == {
        "policy": "disabled_for_exact_resume",
        "buffer_size": 0,
        "serialized": True,
    }
    assert restored_worker.source_state == {"backend_cursor": "member-3"}

    bad = dict(state)
    bad_generator = dict(_string_mapping(state["generator_state"]))
    bad_generator["epoch"] = 1
    bad["generator_state"] = bad_generator
    with pytest.raises(ValueError, match="generator state differs"):
        loader.validate_state(bad)
    loader.close()
