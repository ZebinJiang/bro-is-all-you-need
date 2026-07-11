"""模型族处理器接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod

import torch

from autovla.core.types.training import TrainingBatch
from autovla.models.outputs import ActionPrediction, ModelInputBatch


class ModelProcessor(ABC):
    """把框架中立训练批转换为模型张量并解码动作。

    处理器拥有相机顺序、图像处理、语言分词、状态/动作归一化、padding、
    embodiment 编号与物理动作重建。它不拥有 DataLoader 或通用 batch 堆叠。
    """

    @abstractmethod
    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: torch.device,
        dtype: torch.dtype | None,
        training: bool,
    ) -> ModelInputBatch:
        """生成模型输入张量,不执行模型前向。"""
        raise NotImplementedError

    @abstractmethod
    def decode_actions(
        self,
        actions: torch.Tensor,
        *,
        batch: ModelInputBatch,
    ) -> ActionPrediction:
        """把归一化动作恢复到有效维度和物理单位。"""
        raise NotImplementedError


__all__ = ["ModelProcessor"]
