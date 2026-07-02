"""AutoVLA 数据格式流水线合同。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal, Sequence

DATA_FORMAT_PIPELINE_SCHEMA_VERSION = "autovla.data_format_pipeline.v1"
BENCHMARK_PAYLOAD_SCHEMA_VERSION = "autovla.data_format_pipeline.payload.v1"
FORMAT_PIPELINE_CANDIDATES = (
    "raw_zjh_lerobot_v21_baseline",
    "webdataset_native",
    "robodm_style",
    "lerobot_v3",
)

CandidateId = Literal[
    "raw_zjh_lerobot_v21_baseline",
    "webdataset_native",
    "robodm_style",
    "lerobot_v3",
]
PipelinePhase = Literal["build", "validate", "benchmark", "build-validate-benchmark"]


@dataclass(frozen=True, slots=True)
class FormatPipelineConfig:
    """保存数据格式流水线的有界执行配置。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    candidates: tuple[str, ...] = FORMAT_PIPELINE_CANDIDATES
    max_episodes: int = 4
    max_samples: int = 512
    samples_per_shard: int = 128
    seed: int = 11
    worker_count: int = 8
    batch_size: int = 1
    warmup_batches: int = 1
    measured_batches: int = 8
    materializer: str = "ffmpeg"

    def __post_init__(self) -> None:
        """对路径和有界参数做 fail-closed 校验。"""
        unknown = set(self.candidates) - set(FORMAT_PIPELINE_CANDIDATES)
        if unknown:
            raise ValueError(f"unknown data format candidates: {sorted(unknown)}")
        for field_name in (
            "max_episodes",
            "max_samples",
            "samples_per_shard",
            "worker_count",
            "batch_size",
            "measured_batches",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or type(value) is not int or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if isinstance(self.seed, bool) or type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")
        if self.warmup_batches < 0:
            raise ValueError("warmup_batches must be non-negative")
        if self.materializer not in {"ffmpeg", "synthetic"}:
            raise ValueError("materializer must be ffmpeg or synthetic")
        source = self.source_dataset.resolve()
        working = self.working_root.resolve()
        output = self.output_dir.resolve()
        if working == source or source in working.parents:
            raise ValueError("working_root must not be inside source dataset")
        if output == source or source in output.parents:
            raise ValueError("output_dir must not be inside source dataset")


@dataclass(frozen=True, slots=True)
class FormatCandidateManifest:
    """记录单个数据格式候选的 JSON-safe manifest。"""

    candidate_id: str
    manifest_path: Path
    payload: dict[str, object]

    def to_json_dict(self) -> dict[str, object]:
        """返回可序列化 payload。"""
        return dict(self.payload)


@dataclass(frozen=True, slots=True)
class FormatPipelineResult:
    """记录流水线执行的核心输出。"""

    candidate_manifests: tuple[FormatCandidateManifest, ...]
    generated_artifact_ledger: Path
    output_dir: Path
    result_json: Path
    validation_report: Path


def normalize_candidates(candidates: Sequence[str] | None) -> tuple[str, ...]:
    """返回稳定候选列表。"""
    if not candidates:
        return FORMAT_PIPELINE_CANDIDATES
    normalized = tuple(candidates)
    unknown = set(normalized) - set(FORMAT_PIPELINE_CANDIDATES)
    if unknown:
        raise ValueError(f"unknown data format candidates: {sorted(unknown)}")
    return normalized
