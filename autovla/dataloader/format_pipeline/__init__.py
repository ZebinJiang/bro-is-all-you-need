"""AutoVLA 数据格式流水线公共入口。"""

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
