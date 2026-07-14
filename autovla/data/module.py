"""AutoVLA source-driven DataModule 生命周期和状态聚合。"""

from __future__ import annotations

import importlib
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

from autovla.config.schema import DataConfig, DatasetConfig
from autovla.data.backends.base import dataset_config_fingerprint, local_sample_count
from autovla.data.collators import BatchCollator, PaddedBatchCollator
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    PartitionPlan,
    SamplingPlan,
    StreamMode,
    stable_fingerprint,
)
from autovla.data.loader import (
    ProductionCollator,
    RuntimeTopology,
    SourceFactory,
    TrainingDataLoader,
)
from autovla.data.normalization import NormalizationStatistics
from autovla.data.registry import DataBackendRegistry, build_data_backend_registry
from autovla.data.sampling import PartitionContext
from autovla.data.transforms import TransformPipeline
from autovla.data.types import DataLoaderState, DataModuleState, DatasetManifest, DataStage


class NormalizationProvider(Protocol):
    """定义显式统计量引用解析边界。"""

    @abstractmethod
    def __call__(self, key: str, datasets: Sequence[DatasetConfig]) -> NormalizationStatistics:
        """解析本地已存在统计量,不执行隐藏计算或下载。"""
        raise NotImplementedError


@runtime_checkable
class _StreamPartitionDescriber(Protocol):
    """约束流式后端的分区单元描述接口。"""

    def describe_stream_partition_units(
        self, config: DatasetConfig, stage: DataStage
    ) -> Sequence[str]: ...


@runtime_checkable
class _SourceDescriber(Protocol):
    """约束后端的轻量源规格描述接口。"""

    def describe_source(self, config: DatasetConfig, stage: DataStage) -> object: ...


class DataModule:
    """拥有纯源描述、真实 DataLoader、统计量和关闭生命周期。"""

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
        """记录配置;setup 前不导入可选后端或打开任何数据句柄。"""
        self._config = config
        self._backend_registry = backend_registry or build_data_backend_registry()
        self._collator = collator or PaddedBatchCollator()
        self._transforms = transform_pipeline or TransformPipeline()
        self._normalization_provider = normalization_provider
        self._partition = partition or PartitionContext()
        self._train_loader: TrainingDataLoader | None = None
        self._validation_loader: TrainingDataLoader | None = None
        self._statistics: NormalizationStatistics | None = None
        self._manifest: DatasetManifest | None = None
        self._stage: DataStage | None = None
        self._closed = False

    def bind_partition(self, partition: PartitionContext) -> None:
        """在 setup 前绑定 TrainingStrategy 解析出的 rank/world-size。"""
        if self._closed:
            raise RuntimeError("DataModule is closed")
        if self._stage is not None:
            raise RuntimeError("data partition cannot change after DataModule.setup")
        self._partition = partition

    def _dataset_configs(self) -> tuple[DatasetConfig, ...]:
        """解析规范数据集列表并保留旧单后端配置入口。"""
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

    @staticmethod
    def _fallback_count(config: DatasetConfig) -> int:
        """只读取轻量本地索引计数,不打开后端 live handle。"""
        return local_sample_count(Path(config.root), config.sample_count)

    @staticmethod
    def _temporal_query_fingerprint(config: DatasetConfig) -> str:
        """返回查询配置或显式未配置状态的稳定指纹。"""
        if config.temporal_query is None:
            return stable_fingerprint({"temporal_query": None})
        return config.temporal_query.fingerprint

    def _source_spec(self, config: DatasetConfig, stage: DataStage) -> tuple[DataSourceSpec, str]:
        """从注册能力和本地轻量元数据构造 worker 打开前规格。"""
        registration = self._backend_registry.get(config.backend)
        backend_key = self._backend_registry.resolve_key(config.backend)
        mode = DataAccessMode(config.access_mode)
        if not registration.spec.capabilities.supports(mode):
            raise ValueError(f"backend {backend_key!r} does not support {mode.value}")
        module_name, _, attribute = registration.factory.factory_path.partition(":")
        backend_factory = getattr(importlib.import_module(module_name), attribute)
        if not callable(backend_factory):
            raise TypeError(f"backend factory is not callable: {registration.factory.factory_path}")
        backend: object = backend_factory()
        partition_units: tuple[str, ...] = ()
        if mode is DataAccessMode.STREAMING:
            if not isinstance(backend, _StreamPartitionDescriber):
                raise ValueError(
                    f"streaming backend {backend_key!r} must implement "
                    "describe_stream_partition_units before AC4 integration"
                )
            partition_units = tuple(backend.describe_stream_partition_units(config, stage))
            if not partition_units or len(set(partition_units)) != len(partition_units):
                raise ValueError("stream partition units must be non-empty and unique")
        if isinstance(backend, _SourceDescriber):
            raw_description: object = backend.describe_source(config, stage)
            if not isinstance(raw_description, DataSourceSpec):
                raise TypeError("backend describe_source must return DataSourceSpec")
            described = raw_description
            if described.backend_key != backend_key or described.access_mode is not mode:
                raise ValueError("backend source description conflicts with registry/config")
            if described.partition_units != partition_units:
                raise ValueError("source spec partition_units differ from backend declaration")
            if config.temporal_query is not None and not described.supports_temporal_query:
                raise ValueError("selected data source does not support temporal_query")
            return described, registration.factory.factory_path
        sample_count = self._fallback_count(config)
        source_fingerprint = stable_fingerprint(
            {
                "dataset_config": dataset_config_fingerprint(config),
                "sample_count": sample_count,
                "split": config.split,
                "backend_key": backend_key,
            }
        )
        schema_fingerprint = stable_fingerprint(
            {
                "action_key": config.action_key,
                "action_mask_key": config.action_mask_key,
                "image_keys": config.image_keys,
                "language_key": config.language_key,
                "state_key": config.state_key,
            }
        )
        stream_mode = None if config.stream_mode is None else StreamMode(config.stream_mode)
        spec = DataSourceSpec(
            dataset_key=config.name,
            backend_key=backend_key,
            split=config.split,
            access_mode=mode,
            source_fingerprint=source_fingerprint,
            schema_fingerprint=schema_fingerprint,
            finite=stream_mode is not StreamMode.RESAMPLED,
            sample_count=sample_count if mode is DataAccessMode.MAP else None,
            supports_batch_read=registration.spec.capabilities.grouped_reads,
            supports_temporal_query=False,
            supports_media=True,
            supports_exact_resume=registration.spec.capabilities.deterministic_partition,
            partition_units=partition_units,
            stream_mode=stream_mode,
            nominal_epoch_size=(
                None if mode is DataAccessMode.MAP else config.nominal_epoch_size or sample_count
            ),
            local_only=registration.spec.capabilities.local_only,
            compatibility_metadata={
                "factory_path": registration.factory.factory_path,
                "native_compatible": registration.spec.capabilities.native_compatible,
                "prototype_only": registration.spec.capabilities.prototype_only,
            },
        )
        if config.temporal_query is not None and not spec.supports_temporal_query:
            raise ValueError("selected data source does not support temporal_query")
        return spec, registration.factory.factory_path

    def _build_loader(
        self,
        datasets: Sequence[DatasetConfig],
        *,
        manifest: DatasetManifest,
        stage: DataStage,
        specs_and_paths: Sequence[tuple[DataSourceSpec, str]],
    ) -> TrainingDataLoader:
        """构造纯描述源和真实 Torch DataLoader 外观,不打开后端。"""
        specs_and_paths = tuple(specs_and_paths)
        if len(specs_and_paths) != len(datasets):
            raise ValueError("source spec snapshot must match loader dataset count")
        specs = tuple(item[0] for item in specs_and_paths)
        modes = {spec.access_mode for spec in specs}
        if len(modes) != 1:
            raise ValueError("one loader cannot mix map and streaming sources")
        mode = modes.pop()
        if stage in {DataStage.VALIDATE, DataStage.PREDICT} and any(
            spec.stream_mode is StreamMode.RESAMPLED for spec in specs
        ):
            raise ValueError("resampled streaming is forbidden for validation or prediction")
        factories = tuple(
            SourceFactory(path, config, stage, spec)
            for config, (spec, path) in zip(datasets, specs_and_paths, strict=True)
        )
        logical_workers = max(self._config.loader.num_workers, 1)
        sequence: tuple[tuple[int, int], ...] = ()
        source_units: tuple[tuple[int, str], ...] = ()
        if mode is DataAccessMode.MAP:
            counts = [cast(int, spec.sample_count) for spec in specs]
            sequence_list: list[tuple[int, int]] = []
            consumed = [0 for _ in specs]
            while any(consumed[index] < count for index, count in enumerate(counts)):
                candidates = [
                    source_id
                    for source_id, count in enumerate(counts)
                    if consumed[source_id] < count
                ]
                if self._config.mix.strategy == "balanced":
                    source_id = min(candidates, key=lambda item: (consumed[item], item))
                else:
                    source_id = min(
                        candidates,
                        key=lambda item: (
                            consumed[item] / datasets[item].weight,
                            item,
                        ),
                    )
                sequence_list.append((source_id, consumed[source_id]))
                consumed[source_id] += 1
            sequence = tuple(sequence_list)
            partition_plan = PartitionPlan.for_map(
                sequence,
                global_rank=self._partition.rank,
                world_size=self._partition.world_size,
                batch_size=self._config.loader.batch_size,
                seed=self._config.mix.seed,
                epoch=0,
                shuffle=self._config.loader.map_shuffle,
                policy=self._config.loader.partition_policy,
            )
            nominal_epoch_size = len(partition_plan.rank_sequence)
        else:
            source_units = tuple(
                (source_id, unit_id)
                for source_id, spec in enumerate(specs)
                for unit_id in spec.partition_units
            )
            partition_plan = PartitionPlan.for_streaming(
                source_units,
                global_rank=self._partition.rank,
                world_size=self._partition.world_size,
                logical_worker_count=logical_workers,
                seed=self._config.mix.seed,
                epoch=0,
                shuffle=self._config.loader.stream_shard_shuffle,
            )
            nominal_epoch_size = sum(cast(int, spec.nominal_epoch_size) for spec in specs)
        sampling_plan = SamplingPlan(
            access_mode=mode,
            batch_size=self._config.loader.batch_size,
            drop_last=self._config.loader.drop_last,
            base_seed=self._config.mix.seed,
            map_shuffle=self._config.loader.map_shuffle,
            stream_shard_shuffle=self._config.loader.stream_shard_shuffle,
            stream_sample_shuffle_buffer=self._config.loader.stream_sample_shuffle_buffer,
            replacement=any(spec.stream_mode is StreamMode.RESAMPLED for spec in specs),
            nominal_epoch_size=nominal_epoch_size,
            exact_resume=self._config.loader.exact_resume,
        )
        start_method = (
            "none"
            if self._config.loader.num_workers == 0
            else self._config.loader.multiprocessing_context or "spawn"
        )
        topology = RuntimeTopology(
            global_rank=self._partition.rank,
            local_rank=self._partition.local_rank,
            world_size=self._partition.world_size,
            base_seed=self._config.mix.seed,
            split=specs[0].split,
            multiprocessing_start_method=start_method,
        )
        production_collator = ProductionCollator(
            collator=self._collator,
            transforms=self._transforms,
            manifest_fingerprint=manifest.fingerprint,
            statistics_fingerprint=manifest.statistics_fingerprint,
            source_identities=tuple(
                (
                    spec.dataset_key,
                    spec.source_fingerprint,
                    spec.schema_fingerprint,
                )
                for spec in specs
            ),
        )
        return TrainingDataLoader(
            factories=factories,
            source_specs=specs,
            partition_plan=partition_plan,
            sampling_plan=sampling_plan,
            config=self._config.loader,
            topology=topology,
            collator=production_collator,
            manifest_fingerprint=manifest.fingerprint,
            mix_strategy=self._config.mix.strategy,
            mix_balance_by=self._config.mix.balance_by,
            mix_weights=tuple(config.weight for config in datasets),
            base_map_sequence=sequence if mode is DataAccessMode.MAP else (),
            base_stream_units=source_units if mode is DataAccessMode.STREAMING else (),
        )

    def setup(self, stage: DataStage) -> None:
        """事务化构造 manifest、统计量和 source-driven loaders。"""
        if self._closed:
            raise RuntimeError("DataModule is closed")
        if self._stage is not None:
            if self._stage is stage:
                return
            raise RuntimeError(f"DataModule is already set up for stage {self._stage.value}")
        configs = self._dataset_configs()
        statistics = None
        if self._config.normalization is not None:
            if self._normalization_provider is None:
                raise ValueError(
                    "data.normalization selects statistics but no explicit provider was supplied"
                )
            statistics = self._normalization_provider(self._config.normalization, configs)
        statistics_fingerprint = "identity" if statistics is None else statistics.fingerprint

        def source_stage(config: DatasetConfig) -> DataStage:
            """按 split 选择实际打开源时使用的阶段。"""
            if config.split == "train":
                return DataStage.TRAIN
            if config.split in {"validation", "validate", "val"}:
                return DataStage.VALIDATE
            return stage

        resolved = tuple(
            (config, self._source_spec(config, source_stage(config))) for config in configs
        )
        specs = tuple(spec_and_path[0] for _, spec_and_path in resolved)
        train_resolved = tuple(
            (config, spec_and_path) for config, spec_and_path in resolved if config.split == "train"
        )
        validation_resolved = tuple(
            (config, spec_and_path)
            for config, spec_and_path in resolved
            if config.split in {"validation", "validate", "val"}
        )
        manifest = DatasetManifest(
            datasets=tuple(config.name for config in configs),
            backends=tuple(spec.backend_key for spec in specs),
            splits=tuple(config.split for config in configs),
            sample_counts=tuple(spec.sample_count or spec.nominal_epoch_size for spec in specs),
            source_fingerprints=tuple(spec.source_fingerprint for spec in specs),
            schema_fingerprints=tuple(spec.schema_fingerprint for spec in specs),
            temporal_query_fingerprints=tuple(
                self._temporal_query_fingerprint(config) for config in configs
            ),
            weights=tuple(config.weight for config in configs),
            embodiments=tuple(config.embodiment for config in configs),
            mix_strategy=self._config.mix.strategy,
            mix_seed=self._config.mix.seed,
            balance_by=self._config.mix.balance_by,
            loader_batch_size=self._config.loader.batch_size,
            loader_drop_last=self._config.loader.drop_last,
            transform_fingerprint=self._transforms.fingerprint,
            statistics_fingerprint=statistics_fingerprint,
            metadata={"backend_decision": "NO_BACKEND_WINNER"},
        )
        train = tuple(config for config, _ in train_resolved)
        validation = tuple(config for config, _ in validation_resolved)
        if stage in {DataStage.FIT, DataStage.TRAIN} and not train:
            raise ValueError("training setup requires at least one train split")
        train_loader = (
            None
            if not train
            else self._build_loader(
                train,
                manifest=manifest,
                stage=DataStage.TRAIN,
                specs_and_paths=tuple(item for _, item in train_resolved),
            )
        )
        validation_loader = (
            None
            if not validation
            else self._build_loader(
                validation,
                manifest=manifest,
                stage=DataStage.VALIDATE,
                specs_and_paths=tuple(item for _, item in validation_resolved),
            )
        )
        self._statistics = statistics
        self._manifest = manifest
        self._train_loader = train_loader
        self._validation_loader = validation_loader
        self._stage = stage

    def train_dataloader(self) -> TrainingDataLoader:
        """返回 source-driven 生产训练加载器。"""
        if self._train_loader is None:
            raise RuntimeError("train loader is unavailable; call setup for fit or train")
        return self._train_loader

    def validation_dataloader(self) -> TrainingDataLoader | None:
        """返回可选 source-driven 验证加载器。"""
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
        """导出模块和两个主进程 committed loader 状态。"""
        if self._stage is None or self._manifest is None:
            raise RuntimeError("DataModule state is unavailable before setup")
        return DataModuleState(
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
        ).to_dict()

    def _validate_state(
        self, state: Mapping[str, object]
    ) -> tuple[DataLoaderState | None, DataLoaderState | None]:
        """完整预验证模块和加载器状态,不修改 live 对象。"""
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
        return train, validation

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """预验证全部状态后原子应用两个 committed cursors。"""
        train, validation = self._validate_state(state)
        if train is not None and self._train_loader is not None:
            self._train_loader.apply_state(train)
        if validation is not None and self._validation_loader is not None:
            self._validation_loader.apply_state(validation)

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """只验证完整恢复状态。"""
        self._validate_state(state)

    def close(self) -> None:
        """幂等关闭迭代器、worker、worker-local 源和 loader 状态。"""
        if self._closed:
            return
        errors: list[Exception] = []
        for loader in (self._validation_loader, self._train_loader):
            if loader is None:
                continue
            try:
                loader.close()
            except Exception as exc:
                errors.append(exc)
        self._train_loader = None
        self._validation_loader = None
        self._statistics = None
        self._manifest = None
        self._stage = None
        self._closed = True
        if errors:
            raise RuntimeError(f"failed to close {len(errors)} data loader(s)") from errors[0]


def create_data_module(
    config: DataConfig,
    *,
    backend_registry: DataBackendRegistry | None = None,
    collator: BatchCollator | None = None,
    transform_pipeline: TransformPipeline | None = None,
    normalization_provider: NormalizationProvider | None = None,
    partition: PartitionContext | None = None,
) -> DataModule:
    """构造规范 DataModule,不在工厂调用时打开数据或导入 Torch。"""
    return DataModule(
        config,
        backend_registry=backend_registry,
        collator=collator,
        transform_pipeline=transform_pipeline,
        normalization_provider=normalization_provider,
        partition=partition,
    )


__all__ = ["DataModule", "NormalizationProvider", "create_data_module"]
