"""GenesisVLA 框架协议。"""

from __future__ import annotations

from typing import Protocol

from genesisvla.core.types import ActionChunk, FrameworkOutput, ModelInput


class FrameworkProtocol(Protocol):
    """定义训练或推理框架需要暴露的最小方法形状。"""

    def forward(self, batch: ModelInput) -> FrameworkOutput:
        """执行前向计算并返回框架输出。"""
        ...

    def predict_action(self, obs: ModelInput) -> ActionChunk:
        """根据观测输入预测动作块。"""
        ...
