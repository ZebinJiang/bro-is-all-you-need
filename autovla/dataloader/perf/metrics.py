"""DataLoader 性能指标 schema。"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import cast

MetricValue = float | str

MISSING = "missing"


def percentile(values: Sequence[float], q: float) -> float:
    """用线性插值计算百分位。"""
    if not values:
        raise ValueError("values must not be empty")
    if q < 0.0 or q > 100.0:
        raise ValueError("q must be between 0 and 100")
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = (len(ordered) - 1) * (q / 100.0)
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    weight = position - lower
    return round(ordered[lower] * (1.0 - weight) + ordered[upper] * weight, 6)


def _non_negative_float(value: object, *, field: str) -> float:
    """校验非负数字。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field} must be a non-negative number")
    number = float(value)
    if number < 0.0:
        raise ValueError(f"{field} must be non-negative")
    return round(number, 6)


def _metric_value(value: object, *, field: str) -> MetricValue:
    """校验 metric value 可为数字或 missing。"""
    if value == MISSING:
        return MISSING
    return _non_negative_float(value, field=field)


@dataclass(frozen=True, slots=True)
class PerfMetrics:
    """DataLoader 性能指标记录。

    所有关键指标都有字段; 无法观测的 telemetry 必须进入 missing_metrics。
    """

    samples_per_second: float
    episodes_per_second: float
    batch_latency_ms_p50: float
    batch_latency_ms_p95: float
    batch_latency_ms_max: float
    adapter_inspect_time_ms: float
    index_build_time_ms: float
    media_decode_time_ms: float
    transform_time_ms: float
    tokenization_time_ms: float
    collate_time_ms: float
    data_wait_time_ms: float
    compute_placeholder_time_ms: float
    data_to_compute_ratio: float
    prefetch_queue_depth: float
    cache_hit_rate: float
    pfs_training_store_hit_rate: float
    disk_read_mb_s: float
    estimated_gpu_wait_time_ms: float
    gpu_util_pct: MetricValue
    gpu_memory_used_mb: MetricValue
    hbm_bw_pct: MetricValue
    cpu_user_pct: MetricValue
    cpu_system_pct: MetricValue
    rss_mb: MetricValue
    missing_metrics: tuple[str, ...]

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 指标。"""
        return {
            "adapter_inspect_time_ms": self.adapter_inspect_time_ms,
            "batch_latency_ms_max": self.batch_latency_ms_max,
            "batch_latency_ms_p50": self.batch_latency_ms_p50,
            "batch_latency_ms_p95": self.batch_latency_ms_p95,
            "cache_hit_rate": self.cache_hit_rate,
            "collate_time_ms": self.collate_time_ms,
            "compute_placeholder_time_ms": self.compute_placeholder_time_ms,
            "cpu_system_pct": self.cpu_system_pct,
            "cpu_user_pct": self.cpu_user_pct,
            "data_to_compute_ratio": self.data_to_compute_ratio,
            "data_wait_time_ms": self.data_wait_time_ms,
            "disk_read_mb_s": self.disk_read_mb_s,
            "episodes_per_second": self.episodes_per_second,
            "estimated_gpu_wait_time_ms": self.estimated_gpu_wait_time_ms,
            "gpu_memory_used_mb": self.gpu_memory_used_mb,
            "gpu_util_pct": self.gpu_util_pct,
            "hbm_bw_pct": self.hbm_bw_pct,
            "index_build_time_ms": self.index_build_time_ms,
            "media_decode_time_ms": self.media_decode_time_ms,
            "missing_metrics": list(self.missing_metrics),
            "pfs_training_store_hit_rate": self.pfs_training_store_hit_rate,
            "prefetch_queue_depth": self.prefetch_queue_depth,
            "rss_mb": self.rss_mb,
            "samples_per_second": self.samples_per_second,
            "tokenization_time_ms": self.tokenization_time_ms,
            "transform_time_ms": self.transform_time_ms,
        }

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "PerfMetrics":
        """从 JSON object 恢复指标。"""
        missing_raw = payload.get("missing_metrics", ())
        if not isinstance(missing_raw, list):
            raise ValueError("missing_metrics must be a list")
        missing_values = cast(list[object], missing_raw)
        missing_items: list[str] = []
        for value in missing_values:
            if not isinstance(value, str):
                raise ValueError("missing_metrics entries must be strings")
            missing_items.append(value)
        missing = tuple(missing_items)
        return cls(
            adapter_inspect_time_ms=_non_negative_float(
                payload["adapter_inspect_time_ms"], field="adapter_inspect_time_ms"
            ),
            batch_latency_ms_max=_non_negative_float(
                payload["batch_latency_ms_max"], field="batch_latency_ms_max"
            ),
            batch_latency_ms_p50=_non_negative_float(
                payload["batch_latency_ms_p50"], field="batch_latency_ms_p50"
            ),
            batch_latency_ms_p95=_non_negative_float(
                payload["batch_latency_ms_p95"], field="batch_latency_ms_p95"
            ),
            cache_hit_rate=_non_negative_float(payload["cache_hit_rate"], field="cache_hit_rate"),
            collate_time_ms=_non_negative_float(
                payload["collate_time_ms"],
                field="collate_time_ms",
            ),
            compute_placeholder_time_ms=_non_negative_float(
                payload["compute_placeholder_time_ms"], field="compute_placeholder_time_ms"
            ),
            cpu_system_pct=_metric_value(payload["cpu_system_pct"], field="cpu_system_pct"),
            cpu_user_pct=_metric_value(payload["cpu_user_pct"], field="cpu_user_pct"),
            data_to_compute_ratio=_non_negative_float(
                payload["data_to_compute_ratio"], field="data_to_compute_ratio"
            ),
            data_wait_time_ms=_non_negative_float(
                payload["data_wait_time_ms"], field="data_wait_time_ms"
            ),
            disk_read_mb_s=_non_negative_float(payload["disk_read_mb_s"], field="disk_read_mb_s"),
            episodes_per_second=_non_negative_float(
                payload["episodes_per_second"], field="episodes_per_second"
            ),
            estimated_gpu_wait_time_ms=_non_negative_float(
                payload["estimated_gpu_wait_time_ms"], field="estimated_gpu_wait_time_ms"
            ),
            gpu_memory_used_mb=_metric_value(
                payload["gpu_memory_used_mb"], field="gpu_memory_used_mb"
            ),
            gpu_util_pct=_metric_value(payload["gpu_util_pct"], field="gpu_util_pct"),
            hbm_bw_pct=_metric_value(payload["hbm_bw_pct"], field="hbm_bw_pct"),
            index_build_time_ms=_non_negative_float(
                payload["index_build_time_ms"], field="index_build_time_ms"
            ),
            pfs_training_store_hit_rate=_non_negative_float(
                payload["pfs_training_store_hit_rate"], field="pfs_training_store_hit_rate"
            ),
            media_decode_time_ms=_non_negative_float(
                payload["media_decode_time_ms"], field="media_decode_time_ms"
            ),
            missing_metrics=missing,
            prefetch_queue_depth=_non_negative_float(
                payload["prefetch_queue_depth"], field="prefetch_queue_depth"
            ),
            rss_mb=_metric_value(payload["rss_mb"], field="rss_mb"),
            samples_per_second=_non_negative_float(
                payload["samples_per_second"], field="samples_per_second"
            ),
            tokenization_time_ms=_non_negative_float(
                payload["tokenization_time_ms"], field="tokenization_time_ms"
            ),
            transform_time_ms=_non_negative_float(
                payload["transform_time_ms"], field="transform_time_ms"
            ),
        )

    @classmethod
    def from_latencies(
        cls,
        *,
        samples: int,
        episodes: int,
        batch_latencies_ms: Sequence[float],
        adapter_inspect_time_ms: float = 0.0,
        index_build_time_ms: float = 0.0,
        media_decode_time_ms: float = 0.0,
        transform_time_ms: float = 0.0,
        tokenization_time_ms: float = 0.0,
        collate_time_ms: float = 0.0,
        data_wait_time_ms: float = 0.0,
        compute_placeholder_time_ms: float = 1.0,
        disk_read_mb_s: float = 0.0,
        missing_metrics: Sequence[str] = (),
    ) -> "PerfMetrics":
        """从小型 latency 样本构造指标。"""
        if samples < 0 or episodes < 0:
            raise ValueError("samples and episodes must be non-negative")
        latencies = [float(value) for value in batch_latencies_ms]
        if not latencies:
            latencies = [0.0]
        total_latency_ms = max(sum(latencies), 1.0)
        compute_ms = max(float(compute_placeholder_time_ms), 0.001)
        missing = tuple(dict.fromkeys(missing_metrics))
        if "gpu_util_pct" not in missing:
            missing = (*missing, "gpu_util_pct")
        if "gpu_memory_used_mb" not in missing:
            missing = (*missing, "gpu_memory_used_mb")
        if "hbm_bw_pct" not in missing:
            missing = (*missing, "hbm_bw_pct")
        if "cpu_user_pct" not in missing:
            missing = (*missing, "cpu_user_pct")
        if "cpu_system_pct" not in missing:
            missing = (*missing, "cpu_system_pct")
        if "rss_mb" not in missing:
            missing = (*missing, "rss_mb")
        return cls(
            adapter_inspect_time_ms=round(float(adapter_inspect_time_ms), 6),
            batch_latency_ms_max=round(max(latencies), 6),
            batch_latency_ms_p50=percentile(latencies, 50.0),
            batch_latency_ms_p95=percentile(latencies, 95.0),
            cache_hit_rate=0.0,
            collate_time_ms=round(float(collate_time_ms), 6),
            compute_placeholder_time_ms=round(compute_ms, 6),
            cpu_system_pct=MISSING,
            cpu_user_pct=MISSING,
            data_to_compute_ratio=round(float(data_wait_time_ms) / compute_ms, 6),
            data_wait_time_ms=round(float(data_wait_time_ms), 6),
            disk_read_mb_s=round(float(disk_read_mb_s), 6),
            episodes_per_second=round(float(episodes) / (total_latency_ms / 1000.0), 6),
            estimated_gpu_wait_time_ms=round(max(0.0, float(data_wait_time_ms) - compute_ms), 6),
            gpu_memory_used_mb=MISSING,
            gpu_util_pct=MISSING,
            hbm_bw_pct=MISSING,
            index_build_time_ms=round(float(index_build_time_ms), 6),
            media_decode_time_ms=round(float(media_decode_time_ms), 6),
            missing_metrics=missing,
            pfs_training_store_hit_rate=0.0,
            prefetch_queue_depth=0.0,
            rss_mb=MISSING,
            samples_per_second=round(float(samples) / (total_latency_ms / 1000.0), 6),
            tokenization_time_ms=round(float(tokenization_time_ms), 6),
            transform_time_ms=round(float(transform_time_ms), 6),
        )

    def to_json_line(self) -> str:
        """返回 metrics_timeseries JSONL 行。"""
        return json.dumps(self.to_json_dict(), sort_keys=True) + "\n"
