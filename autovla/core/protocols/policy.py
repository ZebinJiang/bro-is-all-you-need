"""AutoVLA 策略协议。"""

from __future__ import annotations

from typing import Protocol

from autovla.core.types import ActionChunk, ModelInput


class PolicyProtocol(Protocol):
    """定义可交互策略的最小方法形状。"""

    def reset(self) -> None:
        """重置策略内部状态。"""
        ...

    def select_action(self, observation: ModelInput) -> ActionChunk:
        """根据观测选择动作块。"""
        ...
