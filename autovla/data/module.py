"""AutoVLA 可配置 DataModule 生命周期。"""

from __future__ import annotations

import math
from abc import abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from typing import Protocol, cast

from autovla.config.schema import DataConfig, DatasetConfig
from autovla.core.types.training import TrainingBatch
from autovla.data.collators import BatchCollator, PaddedBatchCollator
from autovla.data.datasets import DatasetHandle
from autovla.data.mixing import BalanceGroup, BatchBalancer, DatasetMixer, WeightedDataset
from autovla.data.normalization import NormalizationStatistics
from autovla.data.registry import DataBackendRegistry, build_data_backend_registry
from autovla.data.sampling import PartitionContext
from autovla.data.transforms import TransformPipeline
from autovla.data.types import (
    CheckpointableDataLoaderProtocol,
    DataLoaderState,
    DataModuleState,
    DatasetManifest,
    DataStage,
    TrainingSample,
)


def _add_exception_note(
    error: BaseException,
    prefix: str,
    secondary_error: BaseException,
) -> None:
    """安全渲染并附加次要异常,任何失败都不遮蔽原始异常。"""

    try:
        original_args = error.args
    except BaseException:
        original_args = None
    try:
        try:
            rendered = repr(secondary_error)
        except BaseException:
            rendered = "<secondary exception representation unavailable>"
        try:
            note = f"{prefix}: {rendered}"
        except BaseException:
            note = "secondary exception unavailable"
        try:
            native = getattr(error, "add_note", None)
        except BaseException:
            native = None
        if callable(native):
            try:
                native(note)
                return
            except BaseException:
                pass
        try:
            notes = getattr(error, "__notes__", None)
        except BaseException:
            notes = None
        if not isinstance(notes, list):
            notes = []
            try:
                error.__dict__["__notes__"] = notes
            except BaseException:
                return
        try:
            notes.append(note)
        except BaseException:
            return
    finally:
        if original_args is not None:
            try:
                error.args = original_args
            except BaseException:
                pass


class NormalizationProvider(Protocol):
    """定义显式统计量引用解析边界。"""

    @abstractmethod
    def __call__(self, key: str, datasets: Sequence[DatasetConfig]) -> NormalizationStatistics:
        """解析本地已存在统计量,不执行隐藏计算或下载。"""
        raise NotImplementedError


class _BatchLoader(CheckpointableDataLoaderProtocol):
    """在框架中立句柄上执行确定性混合和整理。"""

    def __init__(
        self,
        *,
        datasets: Sequence[tuple[DatasetConfig, DatasetHandle]],
        data_config: DataConfig,
        partition: PartitionContext,
        collator: BatchCollator,
        transform_pipeline: TransformPipeline,
        dataset_fingerprint: str,
        statistics_fingerprint: str,
    ) -> None:
        """初始化每个 loader 私有的混合器、平衡器和游标。"""
        if not datasets:
            raise ValueError("loader datasets must not be empty")
        self._datasets = tuple(datasets)
        self._config = data_config
        self._partition = partition
        self._collator = collator
        self._transforms = transform_pipeline
        self._dataset_fingerprint = dataset_fingerprint
        self._statistics_fingerprint = statistics_fingerprint
        self._selection_epoch = 0
        self._next_batch_index = 0
        self._next_local_position = 0
        self._mixer = DatasetMixer(
            tuple(WeightedDataset(handle, config.weight) for config, handle in datasets),
            seed=data_config.mix.seed,
        )
        self._by_name = {handle.name: handle for _, handle in datasets}
        self._config_by_name = {handle.name: config for config, handle in datasets}
        self._cursors = {handle.name: 0 for _, handle in datasets}
        self._group_mixers: dict[str, DatasetMixer] = {}
        if data_config.mix.balance_by == "embodiment":
            missing = [config.name for config, _ in datasets if config.embodiment is None]
            if missing:
                raise ValueError(f"embodiment balancing requires metadata for datasets: {missing}")
            grouped: dict[str, list[WeightedDataset]] = {}
            for config, handle in datasets:
                if config.embodiment is None:
                    raise RuntimeError("validated embodiment unexpectedly missing")
                grouped.setdefault(config.embodiment, []).append(
                    WeightedDataset(handle, config.weight)
                )
            self._balancer = BatchBalancer(tuple(BalanceGroup(name) for name in grouped))
            self._group_mixers = {
                name: DatasetMixer(items, seed=data_config.mix.seed)
                for name, items in grouped.items()
            }
        else:
            self._balancer = BatchBalancer(
                tuple(BalanceGroup(handle.name, config.weight) for config, handle in datasets)
            )
        total_samples = sum(len(handle) for _, handle in datasets)
        partition_samples = math.ceil(total_samples / partition.partition_count)
        batch_size = data_config.loader.batch_size
        self._length = (
            partition_samples // batch_size
            if data_config.loader.drop_last
            else math.ceil(partition_samples / batch_size)
        )
        self._samples_per_epoch = (
            self._length * batch_size if data_config.loader.drop_last else partition_samples
        )

    def __len__(self) -> int:
        """返回当前选择 epoch 尚未读取的批次数。"""
        return self._length - self._next_batch_index

    def _prepare(self, sample: TrainingSample) -> TrainingSample:
        """应用通用变换并统一到 DataModule manifest 指纹。"""
        transformed = self._transforms(sample)
        return replace(
            transformed,
            dataset_fingerprint=self._dataset_fingerprint,
            transform_fingerprint=self._transforms.fingerprint,
            statistics_fingerprint=self._statistics_fingerprint,
        )

    def _balanced_samples(self, batch_index: int, count: int) -> list[TrainingSample]:
        """按稳定批平衡计划从各数据集循环读取。"""
        samples: list[TrainingSample] = []
        for group_name in self._balancer.plan(count, batch_index=batch_index):
            name = group_name
            if self._group_mixers:
                mixer = self._group_mixers[group_name]
                group_position = sum(self._cursors[item.dataset.name] for item in mixer.datasets)
                selected = mixer.select(
                    epoch=self._selection_epoch,
                    global_position=self._partition.global_position(group_position),
                )
                name = selected.dataset.name
            dataset = self._by_name[name]
            cursor = self._cursors[name]
            self._cursors[name] = cursor + 1
            dataset_index = self._partition.global_position(cursor) % len(dataset)
            samples.append(self._prepare(dataset.read(dataset_index)))
        return samples

    def _batch_sample_count(self, batch_index: int) -> int:
        """返回指定批次按 drop-last 和短尾批规则实际消费的样本数。"""

        if batch_index < 0 or batch_index >= self._length:
            raise ValueError("batch_index is outside the loader range")
        if not self._config.loader.drop_last and batch_index == self._length - 1:
            return self._samples_per_epoch - self._config.loader.batch_size * batch_index
        return self._config.loader.batch_size

    def _expected_cursor_state(
        self,
        *,
        selection_epoch: int,
        next_batch_index: int,
    ) -> tuple[dict[str, int], dict[str, int]]:
        """纯重放确定性已消费前缀并返回加权与平衡游标向量。"""

        mixer_cursors = {name: 0 for name in self._by_name}
        balanced_cursors = {name: 0 for name in self._by_name}
        for epoch in range(selection_epoch + 1):
            batch_limit = self._length if epoch < selection_epoch else next_batch_index
            for batch_index in range(batch_limit):
                count = self._batch_sample_count(batch_index)
                if self._config.mix.strategy == "weighted":
                    start = batch_index * self._config.loader.batch_size
                    for local_position in range(start, start + count):
                        selected = self._mixer.select(
                            epoch=epoch,
                            global_position=self._partition.global_position(local_position),
                        )
                        mixer_cursors[selected.dataset.name] += 1
                    continue

                for group_name in self._balancer.plan(count, batch_index=batch_index):
                    name = group_name
                    if self._group_mixers:
                        mixer = self._group_mixers[group_name]
                        group_position = sum(
                            balanced_cursors[item.dataset.name] for item in mixer.datasets
                        )
                        selected = mixer.select(
                            epoch=epoch,
                            global_position=self._partition.global_position(group_position),
                        )
                        name = selected.dataset.name
                    balanced_cursors[name] += 1
        return mixer_cursors, balanced_cursors

    def state_dict(self) -> Mapping[str, object]:
        """导出下一条未读批次及全部选择游标。"""

        return DataLoaderState(
            schema_version=DataLoaderState.SCHEMA_VERSION,
            manifest_fingerprint=self._dataset_fingerprint,
            mix_strategy=self._config.mix.strategy,
            selection_epoch=self._selection_epoch,
            next_batch_index=self._next_batch_index,
            next_local_position=self._next_local_position,
            rank=self._partition.rank,
            world_size=self._partition.world_size,
            worker_id=self._partition.worker_id,
            worker_count=self._partition.worker_count,
            mixer_cursors=self._mixer.cursor_state(),
            balanced_cursors=self._cursors,
        ).to_dict()

    def validate_state(self, state: Mapping[str, object]) -> DataLoaderState:
        """完整校验恢复值但不修改任何加载器字段。"""

        restored = DataLoaderState.from_dict(state)
        expected = {
            "manifest_fingerprint": (restored.manifest_fingerprint, self._dataset_fingerprint),
            "mix_strategy": (restored.mix_strategy, self._config.mix.strategy),
            "rank": (restored.rank, self._partition.rank),
            "world_size": (restored.world_size, self._partition.world_size),
            "worker_id": (restored.worker_id, self._partition.worker_id),
            "worker_count": (restored.worker_count, self._partition.worker_count),
        }
        mismatches = [name for name, values in expected.items() if values[0] != values[1]]
        if mismatches:
            raise ValueError(f"data loader resume mismatch: {mismatches}")
        names = set(self._by_name)
        if set(restored.mixer_cursors) != names or set(restored.balanced_cursors) != names:
            raise ValueError("data loader cursor dataset names do not match")
        if (self._length == 0 and restored.next_batch_index != 0) or (
            self._length > 0 and restored.next_batch_index >= self._length
        ):
            raise ValueError("next_batch_index is outside the loader range")
        if self._length == 0 and restored.selection_epoch != 0:
            raise ValueError("zero-length loader cannot have completed a selection epoch")

        current_epoch_samples = min(
            restored.next_batch_index * self._config.loader.batch_size,
            self._samples_per_epoch,
        )
        total_consumed = restored.selection_epoch * self._samples_per_epoch + current_epoch_samples
        mixer_total = sum(restored.mixer_cursors.values())
        balanced_total = sum(restored.balanced_cursors.values())
        if restored.mix_strategy == "weighted":
            if restored.next_local_position != current_epoch_samples:
                raise ValueError("weighted loader position does not match next batch")
            if mixer_total != total_consumed:
                raise ValueError("weighted mixer cursors do not match consumed samples")
            if balanced_total != 0:
                raise ValueError("weighted loader requires zero balanced cursors")
        else:
            if restored.next_local_position != 0 or mixer_total != 0:
                raise ValueError("balanced loader requires zero weighted position and cursors")
            if balanced_total != total_consumed:
                raise ValueError("balanced cursors do not match consumed samples")
        expected_mixer, expected_balanced = self._expected_cursor_state(
            selection_epoch=restored.selection_epoch,
            next_batch_index=restored.next_batch_index,
        )
        if dict(restored.mixer_cursors) != expected_mixer:
            raise ValueError("mixer cursor vector does not match deterministic consumed prefix")
        if dict(restored.balanced_cursors) != expected_balanced:
            raise ValueError("balanced cursor vector does not match deterministic consumed prefix")
        return restored

    def apply_state(self, state: DataLoaderState) -> None:
        """应用已经完整校验且不会失败的加载器状态。"""

        self._mixer.restore_cursors(state.mixer_cursors)
        self._cursors = dict(state.balanced_cursors)
        self._selection_epoch = state.selection_epoch
        self._next_batch_index = state.next_batch_index
        self._next_local_position = state.next_local_position

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """严格校验后原子恢复下一条未读批次。"""

        self.apply_state(self.validate_state(state))

    def __iter__(self) -> Iterator[TrainingBatch]:
        """从下一条未读批次开始迭代并在 yield 前提交游标。"""
        total_batches = self._length
        for batch_index in range(self._next_batch_index, total_batches):
            count = self._batch_sample_count(batch_index)
            mixer_before = self._mixer.cursor_state()
            balanced_before = dict(self._cursors)
            local_position = self._next_local_position
            try:
                if self._config.mix.strategy == "balanced":
                    samples = self._balanced_samples(batch_index, count)
                else:
                    samples = []
                    for _ in range(count):
                        sample = self._mixer.read(
                            local_position,
                            epoch=self._selection_epoch,
                            partition=self._partition,
                        )
                        samples.append(self._prepare(sample))
                        local_position += 1
                batch = self._collator(samples)
            except BaseException:
                self._mixer.restore_cursors(mixer_before)
                self._cursors = balanced_before
                raise

            # yield 前提交,确保检查点总是指向下一条未读数据。
            if batch_index + 1 == total_batches:
                self._selection_epoch += 1
                self._next_batch_index = 0
                self._next_local_position = 0
            else:
                self._next_batch_index = batch_index + 1
                if self._config.mix.strategy == "weighted":
                    self._next_local_position = local_position
            yield batch


class DataModule:
    """拥有本地数据后端、加载器、统计量、manifest 和关闭生命周期。"""

    def __init__(
        self,
        config: DataConfig,
        *,
        backend_registry: DataBackendRegistry | None = None,
        collator: BatchCollator | None = None,
        transform_pipeline: TransformPipeline | None = None,
        normalization_provider: NormalizationProvider | None = None,
        partition: PartitionContext | None = None,
    ) -> None:
        """记录配置,构造阶段之前不打开数据集或可选后端。"""
        self._config = config
        self._backend_registry = backend_registry or build_data_backend_registry()
        self._collator = collator or PaddedBatchCollator()
        self._transforms = transform_pipeline or TransformPipeline()
        self._normalization_provider = normalization_provider
        self._partition = partition or PartitionContext()
        self._handles: list[tuple[DatasetConfig, DatasetHandle]] = []
        self._train_loader: _BatchLoader | None = None
        self._validation_loader: _BatchLoader | None = None
        self._statistics: NormalizationStatistics | None = None
        self._manifest: DatasetManifest | None = None
        self._stage: DataStage | None = None
        self._closed = False

    def bind_partition(self, partition: PartitionContext) -> None:
        """在 setup 前绑定策略解析出的真实 rank/worker 分区。"""

        if self._closed:
            raise RuntimeError("DataModule is closed")
        if self._stage is not None:
            raise RuntimeError("data partition cannot change after DataModule.setup")
        self._partition = partition

    def _dataset_configs(self) -> tuple[DatasetConfig, ...]:
        """解析生产数据集列表,并保留旧单后端字段的窄兼容路径。"""
        if self._config.datasets:
            return self._config.datasets
        if self._config.backend is None:
            raise ValueError("DataConfig must select at least one explicit dataset backend")
        return (
            DatasetConfig(
                name=self._config.name,
                backend=self._config.backend,
                root=self._config.root,
                image_keys=self._config.required_modalities,
            ),
        )

    def setup(self, stage: DataStage) -> None:
        """事务化解析后端、manifest、统计量和 loader。"""
        if self._closed:
            raise RuntimeError("DataModule is closed")
        if self._stage is not None:
            if self._stage == stage:
                return
            raise RuntimeError(f"DataModule is already set up for stage {self._stage.value}")
        configs = self._dataset_configs()
        opened: list[tuple[DatasetConfig, DatasetHandle]] = []
        try:
            for dataset_config in configs:
                registration = self._backend_registry.get(dataset_config.backend)
                backend = registration.factory.create()
                opened.append((dataset_config, backend.open_dataset(dataset_config, stage)))
            statistics: NormalizationStatistics | None = None
            if self._config.normalization is not None:
                if self._normalization_provider is None:
                    raise ValueError(
                        "data.normalization selects statistics but no explicit "
                        "provider was supplied"
                    )
                statistics = self._normalization_provider(
                    self._config.normalization,
                    configs,
                )
            statistics_fingerprint = "identity" if statistics is None else statistics.fingerprint
            manifest = DatasetManifest(
                datasets=tuple(config.name for config, _ in opened),
                backends=tuple(
                    self._backend_registry.resolve_key(config.backend) for config, _ in opened
                ),
                splits=tuple(config.split for config, _ in opened),
                sample_counts=tuple(len(handle) for _, handle in opened),
                weights=tuple(config.weight for config, _ in opened),
                embodiments=tuple(config.embodiment for config, _ in opened),
                mix_strategy=self._config.mix.strategy,
                mix_seed=self._config.mix.seed,
                balance_by=self._config.mix.balance_by,
                loader_batch_size=self._config.loader.batch_size,
                loader_drop_last=self._config.loader.drop_last,
                transform_fingerprint=self._transforms.fingerprint,
                statistics_fingerprint=statistics_fingerprint,
                metadata={"backend_decision": "NO_BACKEND_WINNER"},
            )
            train = tuple(item for item in opened if item[0].split == "train")
            validation = tuple(
                item for item in opened if item[0].split in {"validation", "validate", "val"}
            )
            if stage in {DataStage.FIT, DataStage.TRAIN} and not train:
                raise ValueError("training setup requires at least one train split")
            train_loader = None if not train else self._build_loader(train, manifest=manifest)
            validation_loader = (
                None if not validation else self._build_loader(validation, manifest=manifest)
            )
        except Exception as exc:
            cleanup_errors = self._close_opened_handles(opened)
            self._clear_setup_state()
            for cleanup_error in cleanup_errors:
                _add_exception_note(exc, "dataset handle cleanup failed", cleanup_error)
            raise

        # 所有可能失败的派生步骤完成后一次性提交实例状态。
        self._handles = opened
        self._statistics = statistics
        self._manifest = manifest
        self._train_loader = train_loader
        self._validation_loader = validation_loader
        self._stage = stage

    def _build_loader(
        self,
        datasets: Sequence[tuple[DatasetConfig, DatasetHandle]],
        *,
        manifest: DatasetManifest,
    ) -> _BatchLoader:
        """使用同一 manifest 和分区策略构造框架中立 loader。"""
        return _BatchLoader(
            datasets=datasets,
            data_config=self._config,
            partition=self._partition,
            collator=self._collator,
            transform_pipeline=self._transforms,
            dataset_fingerprint=manifest.fingerprint,
            statistics_fingerprint=manifest.statistics_fingerprint,
        )

    @staticmethod
    def _close_opened_handles(
        handles: Sequence[tuple[DatasetConfig, DatasetHandle]],
    ) -> list[Exception]:
        """逆序关闭全部已打开句柄并收集清理错误。"""
        errors: list[Exception] = []
        for _, handle in reversed(handles):
            try:
                handle.close()
            except Exception as exc:
                errors.append(exc)
        return errors

    def _clear_setup_state(self) -> None:
        """清除可重试 setup 的全部部分状态,不改变关闭标记。"""
        self._handles = []
        self._train_loader = None
        self._validation_loader = None
        self._statistics = None
        self._manifest = None
        self._stage = None

    def train_dataloader(self) -> object:
        """返回已建立的训练 loader。"""
        if self._train_loader is None:
            raise RuntimeError("train loader is unavailable; call setup for fit or train")
        return self._train_loader

    def validation_dataloader(self) -> object | None:
        """返回可选验证 loader。"""
        return self._validation_loader

    def normalization_statistics(self) -> NormalizationStatistics | None:
        """返回解析后的类型化统计量。"""
        return self._statistics

    def dataset_manifest(self) -> DatasetManifest:
        """返回 setup 后的数据集 manifest。"""
        if self._manifest is None:
            raise RuntimeError("dataset manifest is unavailable before setup")
        return self._manifest

    def state_dict(self) -> Mapping[str, object]:
        """在 setup 后导出模块与加载器下一条未读状态。"""

        if self._stage is None or self._manifest is None:
            raise RuntimeError("DataModule state is unavailable before setup")
        state = DataModuleState(
            schema_version=DataModuleState.SCHEMA_VERSION,
            stage=self._stage,
            manifest_fingerprint=self._manifest.fingerprint,
            train_loader=(
                None
                if self._train_loader is None
                else DataLoaderState.from_dict(self._train_loader.state_dict())
            ),
            validation_loader=(
                None
                if self._validation_loader is None
                else DataLoaderState.from_dict(self._validation_loader.state_dict())
            ),
        )
        return state.to_dict()

    def _validate_state(
        self, state: Mapping[str, object]
    ) -> tuple[DataModuleState, DataLoaderState | None, DataLoaderState | None]:
        """完整校验模块及两个加载器而不改变实例状态。"""

        if self._stage is None or self._manifest is None:
            raise RuntimeError("DataModule state cannot be restored before setup")
        restored = DataModuleState.from_dict(state)
        if restored.stage is not self._stage:
            raise ValueError("data module stage does not match checkpoint")
        if restored.manifest_fingerprint != self._manifest.fingerprint:
            raise ValueError("data module manifest fingerprint does not match checkpoint")
        if (restored.train_loader is None) != (self._train_loader is None):
            raise ValueError("checkpoint train loader presence does not match DataModule")
        if (restored.validation_loader is None) != (self._validation_loader is None):
            raise ValueError("checkpoint validation loader presence does not match DataModule")
        train = (
            None
            if restored.train_loader is None or self._train_loader is None
            else self._train_loader.validate_state(restored.train_loader.to_dict())
        )
        validation = (
            None
            if restored.validation_loader is None or self._validation_loader is None
            else self._validation_loader.validate_state(restored.validation_loader.to_dict())
        )
        return restored, train, validation

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """先校验全部模块状态,再无失败窗口地应用两个加载器。"""

        _, train, validation = self._validate_state(state)
        if train is not None and self._train_loader is not None:
            self._train_loader.apply_state(train)
        if validation is not None and self._validation_loader is not None:
            self._validation_loader.apply_state(validation)

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """只校验完整恢复状态,不修改加载器游标。"""

        self._validate_state(state)

    def close(self) -> None:
        """幂等关闭所有后端句柄并释放 loader 引用。"""
        if self._closed:
            return
        handles = tuple(self._handles)
        self._clear_setup_state()
        self._closed = True
        errors = self._close_opened_handles(handles)
        if errors:
            raise RuntimeError(f"failed to close {len(errors)} dataset handle(s)") from errors[0]


def create_data_module(config: DataConfig, **kwargs: object) -> DataModule:
    """构造规范 DataModule,供懒工厂注册表调用。"""
    allowed = {
        "backend_registry",
        "collator",
        "transform_pipeline",
        "normalization_provider",
        "partition",
    }
    unknown = set(kwargs) - allowed
    if unknown:
        raise TypeError(f"unknown DataModule factory arguments: {', '.join(sorted(unknown))}")
    return DataModule(
        config,
        backend_registry=cast(DataBackendRegistry | None, kwargs.get("backend_registry")),
        collator=cast(BatchCollator | None, kwargs.get("collator")),
        transform_pipeline=cast(TransformPipeline | None, kwargs.get("transform_pipeline")),
        normalization_provider=cast(
            NormalizationProvider | None, kwargs.get("normalization_provider")
        ),
        partition=cast(PartitionContext | None, kwargs.get("partition")),
    )


__all__ = ["DataModule", "NormalizationProvider", "create_data_module"]
