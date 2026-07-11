"""规范 ``autovla.data`` 的轻量兼容委托。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    "ALLOWED_STATISTICS_SCOPES": "autovla.dataloader.dataset_artifact",
    "DATASET_ARTIFACT_SCHEMA_VERSION": "autovla.dataloader.dataset_artifact",
    "FORMAT_PIPELINE_CANDIDATES": "autovla.dataloader.format_pipeline",
    "CollatedBatch": "autovla.dataloader.contracts",
    "ComposeConfig": "autovla.dataloader.contracts",
    "DataBackendCapabilities": "autovla.testing.data.backends",
    "DataBackendRegistry": "autovla.data.registry",
    "DataBackendSpec": "autovla.testing.data.backends",
    "DataModule": "autovla.data.module",
    "DataModuleRegistry": "autovla.data.registry",
    "DatasetArtifactV1": "autovla.dataloader.dataset_artifact",
    "FingerprintSet": "autovla.dataloader.dataset_artifact",
    "FormatPipelineConfig": "autovla.dataloader.format_pipeline",
    "JsonObject": "autovla.dataloader.contracts",
    "JsonScalar": "autovla.dataloader.contracts",
    "JsonValue": "autovla.dataloader.contracts",
    "SerializableTransformProtocol": "autovla.dataloader.contracts",
    "StatisticsScope": "autovla.dataloader.dataset_artifact",
    "TrainingBatch": "autovla.core.types.training",
    "TransformContext": "autovla.dataloader.contracts",
    "TransformSpec": "autovla.dataloader.contracts",
    "build_data_backend_registry": "autovla.data.registry",
    "build_data_module_registry": "autovla.data.registry",
    "build_fingerprint_set": "autovla.dataloader.dataset_artifact",
    "build_validate_benchmark_pipeline": "autovla.dataloader.format_pipeline",
    "canonical_json_bytes": "autovla.dataloader.dataset_artifact",
    "canonical_json_payload": "autovla.dataloader.dataset_artifact",
    "collate_raw_samples": "autovla.dataloader.collate",
    "collate_raw_samples_typed": "autovla.dataloader.collate",
    "create_training_batch_source": "autovla.testing.data.backends",
    "fingerprint_payload": "autovla.dataloader.dataset_artifact",
    "get_backend_spec": "autovla.dataloader.backends",
    "list_backend_keys": "autovla.dataloader.backends",
    "normalize_dataset_root": "autovla.dataloader.dataset_artifact",
    "resolve_backend_key": "autovla.dataloader.backends",
    "validate_benchmark_payload": "autovla.dataloader.format_pipeline",
    "validate_statistics_scope": "autovla.dataloader.dataset_artifact",
    "write_dataset_artifact_preview": "autovla.dataloader.dataset_artifact",
}

NO_BACKEND_WINNER = "NO_BACKEND_WINNER"
__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend((*sorted(_EXPORTS), "NO_BACKEND_WINNER"))


def __getattr__(name: str) -> object:
    """按需委托规范 Data 对象并保持对象身份。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定兼容名称。"""
    return sorted(set(globals()) | set(__all__))
