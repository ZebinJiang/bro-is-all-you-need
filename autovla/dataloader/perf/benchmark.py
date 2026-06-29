"""DataLoader 性能 benchmark 执行器。"""

from __future__ import annotations

import json
import os
import platform
import time
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from autovla.dataloader.adapters import get_dataset_adapter
from autovla.dataloader.perf.config import PerfBenchmarkConfig
from autovla.dataloader.perf.metrics import PerfMetrics
from autovla.dataloader.perf.report import (
    PerfClassification,
    classify_perf_report,
    render_perf_markdown,
)

_ACTION_SUBSET: dict[str, object] = {
    "feature_key": "action",
    "reason": "perf harness metadata-only policy rows",
    "selection": "bounded_probe_action_rows",
}


@dataclass(frozen=True, slots=True)
class BenchmarkResult:
    """一次 benchmark 的输出路径和分类。"""

    output_dir: Path
    metrics: PerfMetrics
    classification: PerfClassification
    dataset_summary: Mapping[str, object]


def _is_compute_context() -> bool:
    """判断当前是否处于允许 bounded-decode 的 compute context。"""
    return bool(os.environ.get("SLURM_JOB_ID") or os.environ.get("AUTOVLA_PERF_COMPUTE_NODE"))


def _write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _environment_payload() -> dict[str, object]:
    """记录本地执行环境和外部副作用边界。"""
    return {
        "external_effects": {
            "checkpoint_read": False,
            "dataset_write": False,
            "full_conversion": False,
            "hf_network": False,
            "model_load": False,
            "real_training": False,
            "slurm_submission": False,
            "wandb_network": False,
        },
        "python": platform.python_version(),
        "slurm_job_id": os.environ.get("SLURM_JOB_ID", "missing"),
        "telemetry": {
            "nvidia_smi_called": False,
            "torch_cuda_called": False,
        },
    }


def _dataset_summary(
    *,
    config: PerfBenchmarkConfig,
    metadata_info: Mapping[str, object],
) -> dict[str, object]:
    """构造 dataset probe summary, 不读 parquet 行或媒体。"""
    episode_count = _positive_int_field(metadata_info, "episode_count")
    sample_count = _positive_int_field(metadata_info, "sample_count")
    return {
        "adapter": config.adapter,
        "dataset": config.dataset.as_posix(),
        "episode_count": min(episode_count, config.max_episodes),
        "full_conversion": False,
        "media_decode": config.mode == "bounded-decode",
        "mode": config.mode,
        "row_level_scan": False,
        "sample_count": min(sample_count, config.max_samples),
        "source_format": "lerobot-v2-compatible",
    }


def _positive_int_field(payload: Mapping[str, object], key: str) -> int:
    """从 mapping 中读取正整数字段。"""
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    if value <= 0:
        raise ValueError(f"{key} must be positive")
    return value


def _iter_bounded_video_files(dataset: Path, limit: int) -> list[Path]:
    """按稳定顺序找少量视频文件, 不遍历到全量之后再排序。"""
    videos_root = dataset / "videos"
    if not videos_root.is_dir():
        return []
    selected: list[Path] = []
    for root, dirs, files in os.walk(videos_root):
        dirs.sort()
        for filename in sorted(files):
            if filename.endswith(".mp4"):
                selected.append(Path(root) / filename)
                if len(selected) >= limit:
                    return selected
    return selected


def _bounded_media_read_probe(
    dataset: Path,
    *,
    max_files: int,
    max_bytes_per_file: int = 1_048_576,
) -> tuple[float, float, int, bool]:
    """读取少量视频字节来估计 I/O, 不做完整解码或转换。"""
    files = _iter_bounded_video_files(dataset, max_files)
    if not files:
        return 0.0, 0.0, 0, True
    total_bytes = 0
    start = time.perf_counter()
    for path in files:
        with path.open("rb") as handle:
            total_bytes += len(handle.read(max_bytes_per_file))
    elapsed_ms = max((time.perf_counter() - start) * 1000.0, 0.001)
    mb = total_bytes / (1024.0 * 1024.0)
    mb_s = mb / (elapsed_ms / 1000.0)
    return round(elapsed_ms, 6), round(mb_s, 6), len(files), False


def run_benchmark(
    config: PerfBenchmarkConfig,
    *,
    project_root: str | Path | None = None,
    compute_context: bool | None = None,
) -> BenchmarkResult:
    """运行 bounded DataLoader 性能 probe 并写出报告。

    `metadata-only` 只读取 metadata/info/tasks; `bounded-decode` 必须在 compute context
    下运行, 但当前实现仍保持 no-training/no-conversion 的受限 probe。
    """
    if config.mode == "bounded-decode":
        allowed_compute = _is_compute_context() if compute_context is None else compute_context
        if not allowed_compute:
            raise RuntimeError("bounded-decode benchmark must run on a compute node")

    adapter = get_dataset_adapter(config.adapter)
    start = time.perf_counter()
    metadata = adapter.inspect(config.dataset, project_root=project_root)
    adapter_ms = round((time.perf_counter() - start) * 1000.0, 6)
    artifact = adapter.emit_artifact(metadata, action_statistics_subset=_ACTION_SUBSET)
    info = artifact.to_json_dict()["dataset_manifest"]
    info_mapping = cast(Mapping[str, object], info)
    sample_count = min(_positive_int_field(info_mapping, "sample_count"), config.max_samples)
    episode_count = min(_positive_int_field(info_mapping, "episode_count"), config.max_episodes)
    media_decode_ms = 0.0
    disk_read_mb_s = 0.0
    media_files_read = 0
    missing_media_decode = False
    if config.mode == "bounded-decode":
        media_decode_ms, disk_read_mb_s, media_files_read, missing_media_decode = (
            _bounded_media_read_probe(
                config.dataset,
                max_files=max(1, min(config.max_episodes * 3, config.max_samples)),
            )
        )
    batch_latency = max(adapter_ms + 1.0, 1.0)
    missing = ["gpu_util_pct", "gpu_memory_used_mb", "hbm_bw_pct"]
    if missing_media_decode:
        missing.append("media_decode_time_ms")
    metrics = PerfMetrics.from_latencies(
        samples=sample_count,
        episodes=episode_count,
        batch_latencies_ms=[batch_latency],
        adapter_inspect_time_ms=adapter_ms,
        index_build_time_ms=0.0,
        media_decode_time_ms=media_decode_ms,
        transform_time_ms=0.0,
        tokenization_time_ms=0.0,
        collate_time_ms=0.0,
        data_wait_time_ms=0.0,
        compute_placeholder_time_ms=max(batch_latency, 1.0),
        disk_read_mb_s=disk_read_mb_s,
        missing_metrics=tuple(missing),
    )
    classification = classify_perf_report(metrics)
    dataset_summary = _dataset_summary(config=config, metadata_info=info_mapping)
    output_dir = config.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    report_payload: dict[str, object] = {
        "classification": classification.to_json_dict(),
        "config": config.to_json_dict(),
        "dataset_probe_summary": {**dataset_summary, "media_files_read": media_files_read},
        "fast_training_view": "schema_only",
        "metrics": metrics.to_json_dict(),
        "schema_version": "autovla.dataloader_perf_report.v1",
    }
    _write_json(output_dir / "perf_report.json", report_payload)
    _write_json(
        output_dir / "dataset_probe_summary.json",
        {**dataset_summary, "media_files_read": media_files_read},
    )
    _write_json(output_dir / "environment.json", _environment_payload())
    (output_dir / "metrics_timeseries.jsonl").write_text(metrics.to_json_line(), encoding="utf-8")
    (output_dir / "perf_report.md").write_text(
        render_perf_markdown(
            config=config.to_json_dict(),
            metrics=metrics,
            classification=classification,
            dataset_summary=dataset_summary,
        ),
        encoding="utf-8",
    )
    (output_dir / "recommendations.md").write_text(
        "\n".join(f"- {item}" for item in classification.recommendations) + "\n",
        encoding="utf-8",
    )
    return BenchmarkResult(
        output_dir=output_dir,
        metrics=metrics,
        classification=classification,
        dataset_summary=dataset_summary,
    )
