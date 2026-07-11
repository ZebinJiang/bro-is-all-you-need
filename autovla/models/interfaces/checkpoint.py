"""模型族 checkpoint 适配器接口。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from pathlib import Path

import torch

from autovla.models.outputs import CheckpointCompatibilityReport, CheckpointLoadReport


class ModelCheckpointAdapter(ABC):
    """定义本地 checkpoint 发现、键转换和形状安全加载边界。"""

    @abstractmethod
    def inspect(self, path: str | Path) -> CheckpointCompatibilityReport:
        """静态检查本地布局,不加载权重张量。"""
        raise NotImplementedError

    @abstractmethod
    def convert_state_dict(
        self,
        state_dict: Mapping[str, torch.Tensor],
    ) -> Mapping[str, torch.Tensor]:
        """确定性转换键并拒绝碰撞,不改变张量形状。"""
        raise NotImplementedError

    @abstractmethod
    def load_local(
        self,
        model: torch.nn.Module,
        path: str | Path,
        *,
        strictness: str = "strict",
        device: torch.device | str = "cpu",
        dtype: torch.dtype | None = None,
    ) -> CheckpointLoadReport:
        """从现有本地文件加载并返回完整兼容性报告。"""
        raise NotImplementedError


__all__ = ["ModelCheckpointAdapter"]
