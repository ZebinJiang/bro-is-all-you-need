"""AutoVLA 训练效率遥测契约。"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass


def _finite_non_negative(value: float, name: str) -> float:
    """校验有限非负浮点数。"""
    numeric = float(value)
    if not math.isfinite(numeric) or numeric < 0.0:
        raise ValueError(f"{name} must be finite and non-negative")
    return numeric


@dataclass(frozen=True, slots=True)
class EfficiencyTelemetry:
    """记录训练 step 的数据等待、适配、前向、损失和 checkpoint 时间。"""

    samples_per_second: float
    batches_per_second: float
    batch_latency_ms_p50: float
    batch_latency_ms_p95: float
    data_wait_time_ms: float
    collate_time_ms: float
    adapter_time_ms: float
    forward_time_ms: float
    loss_time_ms: float
    checkpoint_manifest_time_ms: float
    samples_dropped: int = 0
    rejection_reason: str = "none"
    memory_envelope_mb: float | None = None

    def __post_init__(self) -> None:
        """校验遥测字段可稳定序列化。"""
        for name in (
            "samples_per_second",
            "batches_per_second",
            "batch_latency_ms_p50",
            "batch_latency_ms_p95",
            "data_wait_time_ms",
            "collate_time_ms",
            "adapter_time_ms",
            "forward_time_ms",
            "loss_time_ms",
            "checkpoint_manifest_time_ms",
        ):
            object.__setattr__(self, name, _finite_non_negative(getattr(self, name), name))
        if self.samples_dropped < 0:
            raise ValueError("samples_dropped must be non-negative")
        if not self.rejection_reason.strip():
            raise ValueError("rejection_reason must not be empty")
        if self.memory_envelope_mb is not None:
            object.__setattr__(
                self,
                "memory_envelope_mb",
                _finite_non_negative(self.memory_envelope_mb, "memory_envelope_mb"),
            )

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "samples_per_second": self.samples_per_second,
            "batches_per_second": self.batches_per_second,
            "batch_latency_ms_p50": self.batch_latency_ms_p50,
            "batch_latency_ms_p95": self.batch_latency_ms_p95,
            "data_wait_time_ms": self.data_wait_time_ms,
            "collate_time_ms": self.collate_time_ms,
            "adapter_time_ms": self.adapter_time_ms,
            "forward_time_ms": self.forward_time_ms,
            "loss_time_ms": self.loss_time_ms,
            "checkpoint_manifest_time_ms": self.checkpoint_manifest_time_ms,
            "memory_envelope_mb": self.memory_envelope_mb,
            "samples_dropped": self.samples_dropped,
            "rejection_reason": self.rejection_reason,
        }

    def to_stable_json(self) -> str:
        """序列化为确定性 JSON。"""
        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
