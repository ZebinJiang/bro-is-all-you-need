"""AutoVLA 生产数据公共接口,按属性延迟加载实现模块。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    "BalanceGroup": ("autovla.data.mixing", "BalanceGroup"),
    "BatchBalancer": ("autovla.data.mixing", "BatchBalancer"),
    "BatchCollator": ("autovla.data.collators", "BatchCollator"),
    "CheckpointableDataLoaderProtocol": ("autovla.data.types", "CheckpointableDataLoaderProtocol"),
    "DataBackend": ("autovla.data.backends", "DataBackend"),
    "DataBackendCapabilities": ("autovla.data.backends", "DataBackendCapabilities"),
    "DataBackendRegistry": ("autovla.data.registry", "DataBackendRegistry"),
    "DataBackendSpec": ("autovla.data.backends", "DataBackendSpec"),
    "DataLoaderProtocol": ("autovla.data.types", "DataLoaderProtocol"),
    "DataLoaderState": ("autovla.data.types", "DataLoaderState"),
    "TrainingDataLoader": ("autovla.data.loader", "TrainingDataLoader"),
    "AccessMode": ("autovla.data.contracts", "AccessMode"),
    "DataAccessMode": ("autovla.data.contracts", "DataAccessMode"),
    "DataSourceSpec": ("autovla.data.contracts", "DataSourceSpec"),
    "PartitionPlan": ("autovla.data.contracts", "PartitionPlan"),
    "SamplingPlan": ("autovla.data.contracts", "SamplingPlan"),
    "TemporalQuery": ("autovla.data.contracts", "TemporalQuery"),
    "StreamMode": ("autovla.data.contracts", "StreamMode"),
    "StreamPartitionState": ("autovla.data.contracts", "StreamPartitionState"),
    "WorkerContext": ("autovla.data.contracts", "WorkerContext"),
    "DataModule": ("autovla.data.module", "DataModule"),
    "DataModuleFactory": ("autovla.data.registry", "DataModuleFactory"),
    "DataModuleRegistry": ("autovla.data.registry", "DataModuleRegistry"),
    "DataModuleState": ("autovla.data.types", "DataModuleState"),
    "DataStage": ("autovla.data.types", "DataStage"),
    "DatasetFactory": ("autovla.data.datasets", "DatasetFactory"),
    "DatasetHandle": ("autovla.data.datasets", "DatasetHandle"),
    "DatasetManifest": ("autovla.data.types", "DatasetManifest"),
    "DatasetMixer": ("autovla.data.mixing", "DatasetMixer"),
    "EpisodeSampler": ("autovla.data.sampling", "EpisodeSampler"),
    "EpisodeWindow": ("autovla.data.sampling", "EpisodeWindow"),
    "FeatureNormalizationStatistics": (
        "autovla.data.normalization",
        "FeatureNormalizationStatistics",
    ),
    "NormalizationProvider": ("autovla.data.module", "NormalizationProvider"),
    "NormalizationRegistry": ("autovla.data.normalization", "NormalizationRegistry"),
    "NormalizationStatistics": ("autovla.data.normalization", "NormalizationStatistics"),
    "NormalizationTransform": ("autovla.data.normalization", "NormalizationTransform"),
    "PaddedBatchCollator": ("autovla.data.collators", "PaddedBatchCollator"),
    "PartitionContext": ("autovla.data.sampling", "PartitionContext"),
    "RelativeActionTransform": ("autovla.data.normalization", "RelativeActionTransform"),
    "SampleTransform": ("autovla.data.transforms", "SampleTransform"),
    "StatisticsNormalizationTransform": (
        "autovla.data.normalization",
        "StatisticsNormalizationTransform",
    ),
    "TrainingBatch": ("autovla.core.types.training", "TrainingBatch"),
    "TrainingSample": ("autovla.core.types.training", "TrainingSample"),
    "TransformPipeline": ("autovla.data.transforms", "TransformPipeline"),
    "TransformStep": ("autovla.data.transforms", "TransformStep"),
    "WeightedDataset": ("autovla.data.mixing", "WeightedDataset"),
    "build_data_backend_registry": ("autovla.data.registry", "build_data_backend_registry"),
    "build_data_module_registry": ("autovla.data.registry", "build_data_module_registry"),
    "build_normalization_registry": ("autovla.data.normalization", "build_normalization_registry"),
    "collate_nested": ("autovla.data.collators", "collate_nested"),
    "create_data_module": ("autovla.data.module", "create_data_module"),
}

__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend(sorted(_EXPORTS))


def __getattr__(name: str) -> object:
    """按需解析公共对象并缓存,保持实现模块中的规范对象身份。"""

    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共名称集合。"""

    return sorted(set(globals()) | set(__all__))
