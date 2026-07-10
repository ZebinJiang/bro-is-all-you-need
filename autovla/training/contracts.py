"""AutoVLA 训练主干的规范轻量公共契约。"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from autovla.core.types import ModelInput, NumericArray, TrainingBatch
from autovla.training.checkpointing import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.losses import MaskedActionLoss


@runtime_checkable
class BatchAdapter(Protocol):
    """把通用 ``TrainingBatch`` 转成 ``ModelInput`` 的规范协议。"""

    def to_model_input(self, batch: TrainingBatch) -> ModelInput:
        """执行无 IO 的 batch 转换。"""
        ...


@runtime_checkable
class ActionPolicy(Protocol):
    """只负责批量动作预测的规范训练策略协议。"""

    def setup(self) -> None:
        """初始化轻量状态,不得隐藏下载或模型加载。"""
        ...

    def predict_actions(self, batch: ModelInput) -> NumericArray:
        """返回严格批量 ``[B,H,D]`` 数值动作。"""
        ...


TrainablePolicy = ActionPolicy


@runtime_checkable
class LossAdapter(Protocol):
    """在策略外部计算严格 action mask 损失的协议。"""

    def compute(
        self,
        prediction: object,
        target: object,
        action_mask: object,
    ) -> MaskedActionLoss:
        """根据预测、目标和严格 action mask 返回结构化损失。"""
        ...


@runtime_checkable
class CheckpointAdapter(Protocol):
    """metadata-only checkpoint manifest 适配器协议。"""

    def write_manifest(
        self,
        path: Path,
        manifest: TrainingCheckpointManifest,
    ) -> Path:
        """写出 JSON manifest,不得写模型权重。"""
        ...

    def validate_resume(
        self,
        manifest: TrainingCheckpointManifest,
        expected: CheckpointCompatibilitySpec,
    ) -> int:
        """校验恢复兼容性并返回 step。"""
        ...


__all__ = [
    "ActionPolicy",
    "BatchAdapter",
    "CheckpointAdapter",
    "LossAdapter",
    "TrainablePolicy",
    "TrainingBatch",
]
