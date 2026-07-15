"""数据格式流水线的轻量懒加载导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.dataloader.format_pipeline.contracts import (
        BENCHMARK_PAYLOAD_SCHEMA_VERSION,
        DATA_FORMAT_PIPELINE_SCHEMA_VERSION,
        FORMAT_PIPELINE_CANDIDATES,
        FormatCandidateManifest,
        FormatPipelineConfig,
        FormatPipelineResult,
    )
    from autovla.dataloader.format_pipeline.pipeline import (
        benchmark_format_pipeline,
        build_format_pipeline,
        build_validate_benchmark_pipeline,
        validate_benchmark_payload,
        validate_format_pipeline,
    )

_CONTRACTS = "autovla.dataloader.format_pipeline.contracts"
_PIPELINE = "autovla.dataloader.format_pipeline.pipeline"
_EXPORTS = {
    "BENCHMARK_PAYLOAD_SCHEMA_VERSION": _CONTRACTS,
    "DATA_FORMAT_PIPELINE_SCHEMA_VERSION": _CONTRACTS,
    "FORMAT_PIPELINE_CANDIDATES": _CONTRACTS,
    "FormatCandidateManifest": _CONTRACTS,
    "FormatPipelineConfig": _CONTRACTS,
    "FormatPipelineResult": _CONTRACTS,
    "benchmark_format_pipeline": _PIPELINE,
    "build_format_pipeline": _PIPELINE,
    "build_validate_benchmark_pipeline": _PIPELINE,
    "validate_benchmark_payload": _PIPELINE,
    "validate_format_pipeline": _PIPELINE,
}

__all__ = [
    "BENCHMARK_PAYLOAD_SCHEMA_VERSION",
    "DATA_FORMAT_PIPELINE_SCHEMA_VERSION",
    "FORMAT_PIPELINE_CANDIDATES",
    "FormatCandidateManifest",
    "FormatPipelineConfig",
    "FormatPipelineResult",
    "benchmark_format_pipeline",
    "build_format_pipeline",
    "build_validate_benchmark_pipeline",
    "validate_benchmark_payload",
    "validate_format_pipeline",
]


def __getattr__(name: str) -> object:
    """按需解析流水线公共导出。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共导出名称。"""
    return sorted(set(globals()) | set(__all__))
