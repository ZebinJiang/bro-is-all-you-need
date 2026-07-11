"""AutoVLA 生产训练组件上下文。"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import torch
from torch import nn

from autovla.config.schema.training import TrainingConfig
from autovla.data.module import DataModule
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.models.interfaces.processor import ModelProcessor
from autovla.training.callbacks.base import TrainingCallback
from autovla.training.checkpointing.manager import CheckpointManager
from autovla.training.state import TrainingState
from autovla.training.strategy.base import TrainingStrategy
from autovla.training.telemetry.logger import MetricLogger


@dataclass(slots=True)
class TrainingContext:
    """集中保存引擎拥有的模型、数据、优化、策略和本地输出组件。"""

    config: TrainingConfig
    model: nn.Module
    processor: ModelProcessor
    data_module: DataModule
    optimizer: torch.optim.Optimizer | None
    scheduler: torch.optim.lr_scheduler.LRScheduler | None
    strategy: TrainingStrategy
    checkpoint_manager: CheckpointManager
    family_checkpoint_adapter: ModelCheckpointAdapter
    metric_logger: MetricLogger
    callbacks: tuple[TrainingCallback, ...] = ()
    state: TrainingState = field(default_factory=TrainingState)
    resume_from: Path | None = None
    optimizer_factory: Callable[[nn.Module], torch.optim.Optimizer] | None = None
    scheduler_factory: (
        Callable[[torch.optim.Optimizer, int], torch.optim.lr_scheduler.LRScheduler] | None
    ) = None


__all__ = ["TrainingContext"]
