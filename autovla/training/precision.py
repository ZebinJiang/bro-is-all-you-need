"""AutoVLA 显式精度和梯度缩放策略。"""

from __future__ import annotations

from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from typing import Literal

import torch

PrecisionMode = Literal["float32", "bfloat16", "float16"]


@dataclass(slots=True)
class PrecisionPolicy:
    """提供 fp32、bf16 autocast 和 fp16 GradScaler 行为。

    构造对象不访问 CUDA,设备相关 scaler 仅在 ``setup`` 后按需创建。
    """

    mode: PrecisionMode
    _device_type: str | None = None
    _scaler: torch.amp.GradScaler | None = None

    def __post_init__(self) -> None:
        """拒绝未知模式,禁止静默回退。"""

        if self.mode not in {"float32", "bfloat16", "float16"}:
            raise ValueError(f"unsupported precision mode: {self.mode!r}")

    def setup(self, device: torch.device) -> None:
        """绑定设备类型并为 CUDA fp16 延迟创建 GradScaler。"""

        self._device_type = device.type
        if self.mode == "float16" and device.type != "cuda":
            raise ValueError("float16 scaling requires a CUDA device")
        self._scaler = (
            torch.amp.GradScaler("cuda", enabled=True) if self.mode == "float16" else None
        )

    @property
    def model_dtype(self) -> torch.dtype | None:
        """返回处理器可使用的浮点 dtype,fp32 返回 ``None``。"""

        if self.mode == "bfloat16":
            return torch.bfloat16
        if self.mode == "float16":
            return torch.float16
        return None

    def autocast(self) -> AbstractContextManager[None]:
        """返回当前设备的 autocast 上下文。"""

        if self._device_type is None:
            raise RuntimeError("precision policy is not set up")
        if self.mode == "float32":
            return nullcontext()
        dtype = torch.bfloat16 if self.mode == "bfloat16" else torch.float16
        return torch.autocast(device_type=self._device_type, dtype=dtype)

    def backward(self, loss: torch.Tensor) -> None:
        """按精度策略执行缩放或普通反向。"""

        if self._scaler is None:
            loss.backward()
        else:
            self._scaler.scale(loss).backward()

    def unscale(self, optimizer: torch.optim.Optimizer) -> None:
        """在裁剪前解除 fp16 梯度缩放。"""

        if self._scaler is not None:
            self._scaler.unscale_(optimizer)

    def step(self, optimizer: torch.optim.Optimizer) -> bool:
        """执行优化器更新并返回 scaler 是否接受该更新。"""

        if self._scaler is None:
            optimizer.step()
            return True
        old_scale = self._scaler.get_scale()
        self._scaler.step(optimizer)
        self._scaler.update()
        return self._scaler.get_scale() >= old_scale

    def state_dict(self) -> dict[str, object]:
        """返回精度策略和可选 scaler 状态。"""

        return {
            "mode": self.mode,
            "scaler": None if self._scaler is None else self._scaler.state_dict(),
        }

    def load_state_dict(self, state: dict[str, object]) -> None:
        """恢复与当前模式一致的 scaler 状态。"""

        self.validate_state_dict(state)
        scaler_state = state.get("scaler")
        if scaler_state is not None:
            if self._scaler is None:
                raise RuntimeError("validated scaler state has no live scaler")
            self._scaler.load_state_dict(scaler_state)

    def validate_state_dict(self, state: dict[str, object]) -> None:
        """不修改 live scaler 地验证精度和缩放器状态。"""

        if set(state) != {"mode", "scaler"}:
            raise ValueError("checkpoint precision fields are incomplete or unknown")
        if state.get("mode") != self.mode:
            raise ValueError("checkpoint precision mode does not match current policy")
        scaler_state = state.get("scaler")
        if scaler_state is not None:
            if self._scaler is None or not isinstance(scaler_state, dict):
                raise ValueError("checkpoint scaler state is incompatible")
            current = self._scaler.state_dict()
            if set(scaler_state) != set(current):
                raise ValueError("checkpoint scaler fields are incompatible")


__all__ = ["PrecisionMode", "PrecisionPolicy"]
