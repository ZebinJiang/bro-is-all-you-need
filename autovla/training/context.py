"""AutoVLA 生产训练组件上下文。"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from torch import nn

from autovla.config.schema.training import TrainingConfig
from autovla.data.module import DataModule
from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
from autovla.models.interfaces.processor import ModelProcessor
from autovla.training.callbacks.base import TrainingCallback
from autovla.training.checkpointing.manager import CheckpointManager
from autovla.training.plan import TrainingPlan
from autovla.training.session import (
    OptimizerFactory,
    PreparedTrainingSession,
    SchedulerFactory,
    TrainingStrategy,
)
from autovla.training.state import TrainingState
from autovla.training.telemetry.logger import MetricLogger


@dataclass(slots=True)
class TrainingContext:
    """保存训练循环依赖,并分离 Engine 与 prepared session 所有权。

    Engine 拥有数据循环、处理器调用、状态、回调和 checkpoint 节奏。
    Prepared session 拥有模型准备、优化器、调度器、反向、累积、step
    以及策略 checkpoint 后端。
    """

    config: TrainingConfig
    plan: TrainingPlan
    model: nn.Module
    processor: ModelProcessor
    data_module: DataModule
    strategy: TrainingStrategy
    checkpoint_manager: CheckpointManager
    family_checkpoint_adapter: ModelCheckpointAdapter
    metric_logger: MetricLogger
    callbacks: tuple[TrainingCallback, ...] = ()
    state: TrainingState = field(default_factory=TrainingState)
    resume_from: Path | None = None
    optimizer_factory: OptimizerFactory | None = None
    scheduler_factory: SchedulerFactory | None = None
    session: PreparedTrainingSession | None = None


__all__ = ["TrainingContext"]
