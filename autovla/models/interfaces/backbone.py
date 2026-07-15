"""视觉语言骨干接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from torch import nn

from autovla.models.outputs import BackboneOutput, ModelInputBatch


class VisionLanguageBackbone(nn.Module, ABC):
    """提取视觉语言序列表示,不拥有动作损失或训练生命周期。"""

    @abstractmethod
    def forward(self, batch: ModelInputBatch) -> BackboneOutput:
        """返回批量视觉语言特征和严格掩码。"""
        raise NotImplementedError


__all__ = ["VisionLanguageBackbone"]
