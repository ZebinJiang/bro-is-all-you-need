"""动作头接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import torch
from torch import nn

from autovla.models.outputs import (
    ActionHeadOutput,
    ActionPrediction,
    BackboneOutput,
    ModelInputBatch,
)


class ActionHead(nn.Module, ABC):
    """根据视觉语言表示计算动作损失或生成归一化动作。"""

    @abstractmethod
    def compute_loss(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
    ) -> ActionHeadOutput:
        """计算有限标量训练损失及逐元素证据。"""
        raise NotImplementedError

    @abstractmethod
    def predict_actions(
        self,
        backbone_output: BackboneOutput,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """生成归一化动作,不执行物理单位解码。"""
        raise NotImplementedError


__all__ = ["ActionHead"]
