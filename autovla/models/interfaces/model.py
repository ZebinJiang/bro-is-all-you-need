"""视觉语言动作模型接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import torch
from torch import nn

from autovla.models.outputs import ActionPrediction, ModelInputBatch, ModelOutput


class VisionLanguageActionModel(nn.Module, ABC):
    """组合骨干与动作头,不拥有处理器、优化器或 checkpoint 生命周期。"""

    @abstractmethod
    def forward(self, batch: ModelInputBatch) -> ModelOutput:
        """执行训练前向并返回类型化损失。"""
        raise NotImplementedError

    @abstractmethod
    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """执行归一化动作生成。"""
        raise NotImplementedError


__all__ = ["VisionLanguageActionModel"]
