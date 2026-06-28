"""AutoVLA 运行器协议。"""

from __future__ import annotations

from pathlib import Path
from typing import Mapping, Protocol


class RunnerProtocol(Protocol):
    """定义训练评估运行器的生命周期方法形状。"""

    def setup(self) -> None:
        """初始化运行器资源。"""
        ...

    def train(self) -> Mapping[str, float]:
        """执行训练并返回标量指标。"""
        ...

    def evaluate(self) -> Mapping[str, float]:
        """执行评估并返回标量指标。"""
        ...

    def save_checkpoint(self, step: int) -> Path:
        """保存指定步数的检查点并返回路径。"""
        ...

    def resume(self, path: Path) -> int:
        """从检查点恢复并返回恢复到的步数。"""
        ...
