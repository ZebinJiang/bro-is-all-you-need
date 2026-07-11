"""AutoVLA 单步训练输出。"""

from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

from autovla.training.state import StepStatus


def _empty_metrics() -> Mapping[str, float]:
    """返回类型明确的空指标映射。"""

    return {}


@dataclass(frozen=True, slots=True)
class TrainingStepOutput:
    """保存一次微批次的有限标量指标和更新状态。"""

    status: StepStatus
    loss: float | None
    scaled_loss: float | None
    batch_size: int
    optimizer_updated: bool
    gradient_norm: float | None = None
    metrics: Mapping[str, float] = field(default_factory=_empty_metrics)
    message: str | None = None

    def __post_init__(self) -> None:
        """冻结指标并校验批大小。"""

        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


__all__ = ["TrainingStepOutput"]
