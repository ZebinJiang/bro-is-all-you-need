"""确定性训练步数与学习率调度器。"""

from __future__ import annotations

import math

import torch

from autovla.config.schema.optimization import LearningRateSchedulerConfig


def calculate_total_optimizer_steps(
    *,
    batches_per_epoch: int,
    epochs: int,
    accumulation_steps: int,
    max_steps: int | None,
) -> int:
    """按 epoch、累积边界和可选最大微批次步数计算优化器总步数。"""

    if min(batches_per_epoch, epochs, accumulation_steps) <= 0:
        raise ValueError("batches_per_epoch, epochs, and accumulation_steps must be positive")
    remaining = batches_per_epoch * epochs
    if max_steps is not None:
        if max_steps <= 0:
            raise ValueError("max_steps must be positive")
        remaining = min(remaining, max_steps)
    steps = 0
    for _ in range(epochs):
        epoch_microbatches = min(batches_per_epoch, remaining)
        if epoch_microbatches == 0:
            break
        steps += math.ceil(epoch_microbatches / accumulation_steps)
        remaining -= epoch_microbatches
    return steps


def create_scheduler(
    optimizer: torch.optim.Optimizer,
    config: LearningRateSchedulerConfig,
    *,
    calculated_total_steps: int,
) -> torch.optim.lr_scheduler.LambdaLR:
    """创建常量或线性预热加余弦衰减调度器。"""

    total_steps = config.total_steps or calculated_total_steps
    if total_steps <= 0:
        raise ValueError("total scheduler steps must be positive")
    if config.warmup_steps >= total_steps:
        raise ValueError("warmup_steps must be below total scheduler steps")

    def multiplier(step: int) -> float:
        """返回给定已完成优化器步的学习率倍率。"""

        if config.warmup_steps and step < config.warmup_steps:
            return float(step + 1) / float(config.warmup_steps)
        if config.name == "constant":
            return 1.0
        progress = (step - config.warmup_steps) / max(1, total_steps - config.warmup_steps)
        progress = min(max(progress, 0.0), 1.0)
        cosine = 0.5 * (1.0 + math.cos(math.pi * progress))
        return config.minimum_ratio + (1.0 - config.minimum_ratio) * cosine

    if config.name not in {"constant", "cosine"}:
        raise ValueError(f"unsupported scheduler: {config.name!r}")
    return torch.optim.lr_scheduler.LambdaLR(optimizer, multiplier)


__all__ = ["calculate_total_optimizer_steps", "create_scheduler"]
