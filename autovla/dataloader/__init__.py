"""AutoVLA 数据加载公共接口的轻量懒加载导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.dataloader.backends import (
        DataBackendCapabilities,
        DataBackendSpec,
        create_training_batch_source,
        get_backend_spec,
        list_backend_keys,
        resolve_backend_key,
    )
    from autovla.dataloader.collate import collate_raw_samples, collate_raw_samples_typed
    from autovla.dataloader.contracts import (
        CollatedBatch,
        ComposeConfig,
        JsonObject,
        JsonScalar,
        JsonValue,
        SerializableTransformProtocol,
        TransformContext,
        TransformSpec,
    )
    from autovla.dataloader.dataset_artifact import (
        ALLOWED_STATISTICS_SCOPES,
        DATASET_ARTIFACT_SCHEMA_VERSION,
        DatasetArtifactV1,
        FingerprintSet,
        StatisticsScope,
        build_fingerprint_set,
        canonical_json_bytes,
        canonical_json_payload,
        fingerprint_payload,
        normalize_dataset_root,
        validate_statistics_scope,
        write_dataset_artifact_preview,
    )
    from autovla.dataloader.format_pipeline import (
        FORMAT_PIPELINE_CANDIDATES,
        FormatPipelineConfig,
        build_validate_benchmark_pipeline,
        validate_benchmark_payload,
    )

_EXPORTS = {
    "ALLOWED_STATISTICS_SCOPES": "autovla.dataloader.dataset_artifact",
    "DATASET_ARTIFACT_SCHEMA_VERSION": "autovla.dataloader.dataset_artifact",
    "FORMAT_PIPELINE_CANDIDATES": "autovla.dataloader.format_pipeline",
    "CollatedBatch": "autovla.dataloader.contracts",
    "ComposeConfig": "autovla.dataloader.contracts",
    "DataBackendCapabilities": "autovla.dataloader.backends",
    "DataBackendSpec": "autovla.dataloader.backends",
    "DatasetArtifactV1": "autovla.dataloader.dataset_artifact",
    "FingerprintSet": "autovla.dataloader.dataset_artifact",
    "FormatPipelineConfig": "autovla.dataloader.format_pipeline",
    "JsonObject": "autovla.dataloader.contracts",
    "JsonScalar": "autovla.dataloader.contracts",
    "JsonValue": "autovla.dataloader.contracts",
    "SerializableTransformProtocol": "autovla.dataloader.contracts",
    "StatisticsScope": "autovla.dataloader.dataset_artifact",
    "TransformContext": "autovla.dataloader.contracts",
    "TransformSpec": "autovla.dataloader.contracts",
    "build_fingerprint_set": "autovla.dataloader.dataset_artifact",
    "build_validate_benchmark_pipeline": "autovla.dataloader.format_pipeline",
    "canonical_json_bytes": "autovla.dataloader.dataset_artifact",
    "canonical_json_payload": "autovla.dataloader.dataset_artifact",
    "collate_raw_samples": "autovla.dataloader.collate",
    "collate_raw_samples_typed": "autovla.dataloader.collate",
    "create_training_batch_source": "autovla.dataloader.backends",
    "fingerprint_payload": "autovla.dataloader.dataset_artifact",
    "get_backend_spec": "autovla.dataloader.backends",
    "list_backend_keys": "autovla.dataloader.backends",
    "normalize_dataset_root": "autovla.dataloader.dataset_artifact",
    "resolve_backend_key": "autovla.dataloader.backends",
    "validate_benchmark_payload": "autovla.dataloader.format_pipeline",
    "validate_statistics_scope": "autovla.dataloader.dataset_artifact",
    "write_dataset_artifact_preview": "autovla.dataloader.dataset_artifact",
}

__all__ = [
    "ALLOWED_STATISTICS_SCOPES",
    "DATASET_ARTIFACT_SCHEMA_VERSION",
    "FORMAT_PIPELINE_CANDIDATES",
    "CollatedBatch",
    "ComposeConfig",
    "DataBackendCapabilities",
    "DataBackendSpec",
    "DatasetArtifactV1",
    "FingerprintSet",
    "FormatPipelineConfig",
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "SerializableTransformProtocol",
    "StatisticsScope",
    "TransformContext",
    "TransformSpec",
    "build_fingerprint_set",
    "build_validate_benchmark_pipeline",
    "canonical_json_bytes",
    "canonical_json_payload",
    "collate_raw_samples",
    "collate_raw_samples_typed",
    "create_training_batch_source",
    "fingerprint_payload",
    "get_backend_spec",
    "list_backend_keys",
    "normalize_dataset_root",
    "resolve_backend_key",
    "validate_benchmark_payload",
    "validate_statistics_scope",
    "write_dataset_artifact_preview",
]


def __getattr__(name: str) -> object:
    """按需解析兼容公共导出并缓存对象身份。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共导出名称。"""
    return sorted(set(globals()) | set(__all__))
