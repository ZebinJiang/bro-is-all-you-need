"""本地推理会话协议。"""

from __future__ import annotations

from typing import Protocol

from autovla.inference.contracts import InferenceRequest, InferenceResult


class InferenceSession(Protocol):
    """约束共享 processor、模型和 inverse transform 的本地生命周期。"""

    @property
    def fingerprint(self) -> str:
        """返回 family/assets/processor/device/precision 会话身份。"""
        ...

    def predict(self, request: InferenceRequest) -> InferenceResult:
        """执行实现方显式授权的本地预测; 协议自身不创建运行时。"""
        ...

    def reset(self) -> None:
        """重置本地 episode/session 状态。"""
        ...

    def close(self) -> None:
        """释放本地模型和设备资源。"""
        ...


__all__ = ["InferenceSession"]
