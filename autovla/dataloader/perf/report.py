"""DataLoader 性能报告与分类规则。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from autovla.dataloader.perf.metrics import MISSING, PerfMetrics

PerfConclusion = Literal["PASS", "WARN", "FAIL", "INSUFFICIENT_TELEMETRY"]


@dataclass(frozen=True, slots=True)
class PerfClassification:
    """性能 probe 的可报告分类。"""

    classification: PerfConclusion
    reasons: tuple[str, ...]
    recommendations: tuple[str, ...]

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 分类。"""
        return {
            "classification": self.classification,
            "reasons": list(self.reasons),
            "recommendations": list(self.recommendations),
        }


def classify_perf_report(metrics: PerfMetrics) -> PerfClassification:
    """按 M3.2 bottleneck 规则分类。"""
    reasons: list[str] = []
    recommendations: list[str] = []
    data_wait_ratio = metrics.data_wait_time_ms / max(metrics.compute_placeholder_time_ms, 0.001)
    if data_wait_ratio > 2.0:
        reasons.append("data_wait_time_ms dominates compute_placeholder_time_ms")
        recommendations.append("build packed Fast Training View before real finetune")
    if metrics.media_decode_time_ms > max(metrics.batch_latency_ms_p50 * 0.5, 1.0):
        reasons.append("media_decode_time_ms dominates per-batch time")
        recommendations.append("build a PFS-backed Training Store before training")
    if metrics.tokenization_time_ms > max(metrics.batch_latency_ms_p50 * 0.2, 1.0):
        reasons.append("tokenization_time_ms is nontrivial")
        recommendations.append("precompute or cache language tokens")
    if metrics.collate_time_ms > max(metrics.batch_latency_ms_p50 * 0.25, 1.0):
        reasons.append("collate_time_ms is high")
        recommendations.append("use a packed training view with deterministic collate layout")
    if reasons:
        return PerfClassification("FAIL", tuple(reasons), tuple(recommendations))

    if data_wait_ratio > 0.5:
        return PerfClassification(
            "WARN",
            ("data_wait_time_ms is a possible dataloader bottleneck",),
            ("run a larger compute-node benchmark before real finetune",),
        )

    missing_gpu = {"gpu_util_pct", "gpu_memory_used_mb", "hbm_bw_pct"} & set(
        metrics.missing_metrics
    )
    if missing_gpu:
        return PerfClassification(
            "INSUFFICIENT_TELEMETRY",
            (f"missing GPU telemetry: {sorted(missing_gpu)}",),
            ("collect nvidia-smi telemetry on compute node if available",),
        )
    return PerfClassification(
        "PASS",
        ("no obvious dataloader bottleneck in bounded probe",),
        ("keep perf gate active before authorizing real training",),
    )


def classify_training_store_comparison(comparison: Mapping[str, object]) -> PerfClassification:
    """按 raw/store 对比结果分类 Training Store 读取路径。"""
    effective_p50 = comparison.get("raw_effective_batch_latency_ms_p50")
    raw_p50 = comparison.get("raw_batch_latency_ms_p50")
    store_p50 = comparison.get("training_store_batch_latency_ms_p50")
    speedup = comparison.get("speedup_vs_raw_decode")
    if not isinstance(store_p50, (int, float)) or isinstance(store_p50, bool):
        return PerfClassification(
            "INSUFFICIENT_TELEMETRY",
            ("missing training store read latency",),
            ("rerun store-read-benchmark with generated store artifacts",),
        )
    if isinstance(effective_p50, (int, float)) and not isinstance(effective_p50, bool):
        raw_comparator = float(effective_p50)
    elif isinstance(raw_p50, (int, float)) and not isinstance(raw_p50, bool):
        raw_comparator = float(raw_p50)
    else:
        return PerfClassification(
            "INSUFFICIENT_TELEMETRY",
            ("missing effective raw bounded-decode comparison latency",),
            ("run bounded raw decode and store-read benchmark in one compute evidence pass",),
        )
    basis = comparison.get("raw_comparison_basis", "raw_batch_latency")
    basis_text = basis if isinstance(basis, str) and basis else "raw_batch_latency"
    speedup_value = float(speedup) if isinstance(speedup, (int, float)) else 0.0
    if float(store_p50) <= 0.5 * raw_comparator or speedup_value >= 2.0:
        return PerfClassification(
            "PASS",
            (f"training-store read meets speedup threshold using {basis_text}",),
            ("preserve raw/store comparison evidence for merge review",),
        )
    if float(store_p50) < raw_comparator:
        return PerfClassification(
            "WARN",
            (f"training-store read improves {basis_text} but misses threshold",),
            ("Owner reviewers may accept foundation PR status with recorded warning",),
        )
    return PerfClassification(
        "FAIL",
        (f"training-store read is not materially faster than {basis_text}",),
        ("keep PR draft and revisit store format or recording format",),
    )


def render_perf_markdown(
    *,
    config: Mapping[str, object],
    metrics: PerfMetrics,
    classification: PerfClassification,
    dataset_summary: Mapping[str, object],
) -> str:
    """渲染稳定 Markdown 性能报告。"""
    lines = [
        "# AutoVLA DataLoader Performance Report",
        "",
        "## Summary",
        "",
        f"- Classification: `{classification.classification}`",
        f"- Adapter: `{config['adapter']}`",
        f"- Mode: `{config['mode']}`",
        f"- Dataset sample count: `{dataset_summary.get('sample_count')}`",
        f"- Dataset episode count: `{dataset_summary.get('episode_count')}`",
        "",
        "## Metrics",
        "",
        "```json",
        json.dumps(metrics.to_json_dict(), indent=2, sort_keys=True),
        "```",
        "",
        "## Reasons",
        "",
        *(f"- {reason}" for reason in classification.reasons),
        "",
        "## Recommendations",
        "",
        *(f"- {item}" for item in classification.recommendations),
        "",
        "## Safety Boundary",
        "",
        "- No real training.",
        "- No model, checkpoint, tokenizer, W&B, Hugging Face, endpoint, or robot action.",
        "- Metadata-only mode does not decode media or scan parquet rows.",
        "- Missing telemetry remains explicit in `missing_metrics`.",
        "",
    ]
    return "\n".join(lines)


def build_fast_training_view_schema() -> dict[str, object]:
    """返回未来 Fast Training View 的 schema 草案。"""
    return {
        "data_loader_worker_prefetch_policy": {
            "prefetch_factor": "bounded",
            "worker_count": "configured_by_training_gate",
        },
        "deterministic_sampler_state": {
            "epoch": "int",
            "seed": "int",
            "shard_cursor": "stable mapping",
        },
        "episode_to_sample_index": {"schema": "episode_id -> [sample_id]"},
        "pfs_training_store_manifest": {
            "local_stage_used": False,
            "storage_backend": "pfs_shared",
            "store_format": "npz_jsonl_v0",
        },
        "performance_counters_schema": {
            "batch_latency_ms": "float",
            "data_wait_time_ms": "float",
            "decode_time_ms": "float",
            "gpu_util_pct": "float|missing",
        },
        "precomputed_action_normalization_policy": {
            "statistics_fingerprint": "required",
            "scope": "action_only|mixed",
        },
        "pfs_prepacked_frame_policy": {
            "decode_backend": "future task",
            "no_decode_in_training_step": True,
        },
        "pfs_language_token_policy": {
            "tokenizer_fingerprint": "future task",
            "no_tokenization_in_training_step": True,
        },
        "sample_to_shard_index": {"schema": "sample_id -> shard_id:offset"},
        "shard_manifest": {"schema": "ordered shards with checksums"},
    }


def write_baseline_comparison_report(
    baseline_summary: Mapping[str, object],
    perf_payload: Mapping[str, object],
    output_path: str | Path,
) -> Path:
    """写出 baseline wait 信号与新 perf probe 的对照报告。"""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    waits = cast(Mapping[str, object], baseline_summary.get("dataloader_waits", {}))
    classification = cast(Mapping[str, object], perf_payload.get("classification", {}))
    metrics = cast(Mapping[str, object], perf_payload.get("metrics", {}))
    lines = [
        "# Baseline Comparison Report",
        "",
        "## Baseline",
        "",
        f"- Schema: `{baseline_summary.get('schema_version', MISSING)}`",
        f"- Status: `{baseline_summary.get('status', {})}`",
        f"- Dataloader waits: `{waits}`",
        "",
        "## Current Probe",
        "",
        f"- Classification: `{classification.get('classification', MISSING)}`",
        f"- data_wait_time_ms: `{metrics.get('data_wait_time_ms', MISSING)}`",
        f"- samples_per_second: `{metrics.get('samples_per_second', MISSING)}`",
        f"- missing_metrics: `{metrics.get('missing_metrics', [])}`",
        "",
        "## Interpretation",
        "",
        "- Baseline wait signals are treated as seed evidence, not final diagnosis.",
        "- Current probe remains bounded and does not run real training.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
