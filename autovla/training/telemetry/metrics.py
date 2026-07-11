"""生产训练的类型化遥测记录。"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TrainingMetrics:
    """记录损失、学习率、梯度、阶段耗时、吞吐与可选内存指标。"""

    loss: float
    learning_rate: float
    gradient_norm: float | None
    data_wait_seconds: float
    processor_seconds: float
    forward_seconds: float
    backward_seconds: float
    optimizer_seconds: float
    samples_per_second: float
    memory_allocated_bytes: int | None = None
    memory_reserved_bytes: int | None = None

    def __post_init__(self) -> None:
        """拒绝非有限遥测值和负耗时。"""

        values = (
            self.loss,
            self.learning_rate,
            self.data_wait_seconds,
            self.processor_seconds,
            self.forward_seconds,
            self.backward_seconds,
            self.optimizer_seconds,
            self.samples_per_second,
        )
        if not all(math.isfinite(value) for value in values):
            raise ValueError("training metrics must be finite")
        if min(values[2:]) < 0.0:
            raise ValueError("timings and throughput must be non-negative")

    def to_dict(self) -> dict[str, float | int | None]:
        """返回适合本地日志 sink 的稳定字段映射。"""

        return {
            "loss": self.loss,
            "learning_rate": self.learning_rate,
            "gradient_norm": self.gradient_norm,
            "data_wait_seconds": self.data_wait_seconds,
            "processor_seconds": self.processor_seconds,
            "forward_seconds": self.forward_seconds,
            "backward_seconds": self.backward_seconds,
            "optimizer_seconds": self.optimizer_seconds,
            "samples_per_second": self.samples_per_second,
            "memory_allocated_bytes": self.memory_allocated_bytes,
            "memory_reserved_bytes": self.memory_reserved_bytes,
        }


__all__ = ["TrainingMetrics"]
