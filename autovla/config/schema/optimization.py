"""AutoVLA 优化器和学习率调度配置。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.config.schema.base import (
    require_choice,
    require_non_empty_str,
    require_number,
    require_positive_int,
)


@dataclass(frozen=True, slots=True)
class LearningRateSchedulerConfig:
    """描述常量或预热余弦学习率计划。"""

    name: str = "constant"
    warmup_steps: int = 0
    total_steps: int | None = None
    minimum_ratio: float = 0.0

    def __post_init__(self) -> None:
        """校验学习率计划边界。"""
        require_choice(self.name, "training.optimization.scheduler.name", ("constant", "cosine"))
        if self.warmup_steps < 0:
            raise ValueError("scheduler.warmup_steps must be non-negative")
        if self.total_steps is not None:
            require_positive_int(self.total_steps, "scheduler.total_steps")
            if self.warmup_steps >= self.total_steps:
                raise ValueError("scheduler.warmup_steps must be below total_steps")
        ratio = require_number(self.minimum_ratio, "scheduler.minimum_ratio")
        if ratio < 0.0 or ratio > 1.0:
            raise ValueError("scheduler.minimum_ratio must be in [0, 1]")


@dataclass(frozen=True, slots=True)
class OptimizationConfig:
    """描述优化器及骨干和动作头参数组。"""

    optimizer_key: str = "adamw"
    learning_rate: float = 1e-4
    backbone_learning_rate: float | None = None
    action_head_learning_rate: float | None = None
    weight_decay: float = 0.01
    betas: tuple[float, float] = (0.9, 0.999)
    epsilon: float = 1e-8
    scheduler: LearningRateSchedulerConfig = LearningRateSchedulerConfig()

    def __post_init__(self) -> None:
        """校验优化器键、学习率和数值范围。"""
        require_non_empty_str(self.optimizer_key, "training.optimization.optimizer_key")
        for field_name in ("learning_rate", "epsilon"):
            value = require_number(getattr(self, field_name), f"training.optimization.{field_name}")
            if value <= 0.0:
                raise ValueError(f"training.optimization.{field_name} must be positive")
        for field_name in ("backbone_learning_rate", "action_head_learning_rate"):
            value = getattr(self, field_name)
            if value is not None and require_number(value, field_name) <= 0.0:
                raise ValueError(f"{field_name} must be positive")
        decay = require_number(self.weight_decay, "training.optimization.weight_decay")
        if decay < 0.0:
            raise ValueError("training.optimization.weight_decay must be non-negative")
        if len(self.betas) != 2 or any(beta < 0.0 or beta >= 1.0 for beta in self.betas):
            raise ValueError("training.optimization.betas must contain two values in [0, 1)")


__all__ = ["LearningRateSchedulerConfig", "OptimizationConfig"]
