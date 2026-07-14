"""规范 ``autovla.data`` 的轻量兼容委托。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.core.types.training import TrainingBatch as TrainingBatch
    from autovla.data.module import DataModule as DataModule
    from autovla.data.registry import DataBackendRegistry as DataBackendRegistry
    from autovla.data.registry import DataModuleRegistry as DataModuleRegistry
    from autovla.data.registry import build_data_backend_registry as build_data_backend_registry
    from autovla.data.registry import build_data_module_registry as build_data_module_registry
    from autovla.dataloader.backends import get_backend_spec as get_backend_spec
    from autovla.dataloader.backends import list_backend_keys as list_backend_keys
    from autovla.dataloader.backends import resolve_backend_key as resolve_backend_key
    from autovla.dataloader.collate import collate_raw_samples as collate_raw_samples
    from autovla.dataloader.collate import (
        collate_raw_samples_typed as collate_raw_samples_typed,
    )
    from autovla.dataloader.contracts import CollatedBatch as CollatedBatch
    from autovla.dataloader.contracts import ComposeConfig as ComposeConfig
    from autovla.dataloader.contracts import JsonObject as JsonObject
    from autovla.dataloader.contracts import JsonScalar as JsonScalar
    from autovla.dataloader.contracts import JsonValue as JsonValue
    from autovla.dataloader.contracts import (
        SerializableTransformProtocol as SerializableTransformProtocol,
    )
    from autovla.dataloader.contracts import TransformContext as TransformContext
    from autovla.dataloader.contracts import TransformSpec as TransformSpec
    from autovla.dataloader.dataset_artifact import (
        ALLOWED_STATISTICS_SCOPES as ALLOWED_STATISTICS_SCOPES,
    )
    from autovla.dataloader.dataset_artifact import (
        DATASET_ARTIFACT_SCHEMA_VERSION as DATASET_ARTIFACT_SCHEMA_VERSION,
    )
    from autovla.dataloader.dataset_artifact import DatasetArtifactV1 as DatasetArtifactV1
    from autovla.dataloader.dataset_artifact import FingerprintSet as FingerprintSet
    from autovla.dataloader.dataset_artifact import StatisticsScope as StatisticsScope
    from autovla.dataloader.dataset_artifact import (
        build_fingerprint_set as build_fingerprint_set,
    )
    from autovla.dataloader.dataset_artifact import (
        canonical_json_bytes as canonical_json_bytes,
    )
    from autovla.dataloader.dataset_artifact import (
        canonical_json_payload as canonical_json_payload,
    )
    from autovla.dataloader.dataset_artifact import fingerprint_payload as fingerprint_payload
    from autovla.dataloader.dataset_artifact import (
        normalize_dataset_root as normalize_dataset_root,
    )
    from autovla.dataloader.dataset_artifact import (
        validate_statistics_scope as validate_statistics_scope,
    )
    from autovla.dataloader.dataset_artifact import (
        write_dataset_artifact_preview as write_dataset_artifact_preview,
    )
    from autovla.dataloader.format_pipeline import (
        FORMAT_PIPELINE_CANDIDATES as FORMAT_PIPELINE_CANDIDATES,
    )
    from autovla.dataloader.format_pipeline import FormatPipelineConfig as FormatPipelineConfig
    from autovla.dataloader.format_pipeline import (
        build_validate_benchmark_pipeline as build_validate_benchmark_pipeline,
    )
    from autovla.dataloader.format_pipeline import (
        validate_benchmark_payload as validate_benchmark_payload,
    )
    from autovla.testing.data.backends import (
        DataBackendCapabilities as DataBackendCapabilities,
    )
    from autovla.testing.data.backends import DataBackendSpec as DataBackendSpec
    from autovla.testing.data.backends import (
        create_training_batch_source as create_training_batch_source,
    )

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
