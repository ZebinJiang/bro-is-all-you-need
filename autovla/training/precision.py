"""AutoVLA 显式精度和梯度缩放策略。"""

from __future__ import annotations

from collections.abc import Mapping
from contextlib import nullcontext
from dataclasses import dataclass
from typing import Literal, Protocol, TypeGuard, runtime_checkable

import torch

PrecisionMode = Literal["float32", "bfloat16", "float16"]


@runtime_checkable
class _ContextManager(Protocol):
    """约束 autocast 与空上下文的共同接口。"""

    def __enter__(self) -> None: ...

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
        /,
    ) -> bool | None: ...


@runtime_checkable
class _BackwardValue(Protocol):
    """约束可执行反向传播的 Tensor 或缩放结果。"""

    def backward(self) -> object: ...


@runtime_checkable
class _GradScaler(Protocol):
    """约束训练策略使用的 GradScaler 公共表面。"""

    def scale(self, loss: torch.Tensor) -> _BackwardValue: ...

    def unscale_(self, optimizer: torch.optim.Optimizer) -> None: ...

    def step(self, optimizer: torch.optim.Optimizer) -> object: ...

    def update(self) -> None: ...

    def get_scale(self) -> float: ...

    def state_dict(self) -> dict[str, object]: ...

    def load_state_dict(self, state_dict: dict[str, object]) -> None: ...


@runtime_checkable
class _GradScalerFactory(Protocol):
    """约束 Torch 延迟 GradScaler 构造器。"""

    def __call__(self, device: str, *, enabled: bool) -> _GradScaler: ...


@runtime_checkable
class _AutocastFactory(Protocol):
    """约束 Torch autocast 构造器。"""

    def __call__(self, *, device_type: str, dtype: torch.dtype) -> _ContextManager: ...


def _make_grad_scaler() -> _GradScaler:
    """从 Torch 公共运行时属性构造 CUDA GradScaler。"""

    amp_module: object = getattr(torch, "amp", None)
    factory: object = getattr(amp_module, "GradScaler", None)
    if not isinstance(factory, _GradScalerFactory):
        raise RuntimeError("torch.amp.GradScaler is unavailable")
    return factory("cuda", enabled=True)


def _make_autocast(device_type: str, dtype: torch.dtype) -> _ContextManager:
    """从 Torch 公共运行时属性构造 autocast 上下文。"""

    factory: object = getattr(torch, "autocast", None)
    if not isinstance(factory, _AutocastFactory):
        raise RuntimeError("torch.autocast is unavailable")
    return factory(device_type=device_type, dtype=dtype)


def _run_backward(value: object) -> None:
    """运行时校验后执行无参数 backward。"""

    if not isinstance(value, _BackwardValue):
        raise TypeError("loss value does not support backward")
    value.backward()


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态 scaler 状态是否为对象映射。"""

    return isinstance(value, Mapping)


def _scaler_state(value: object) -> dict[str, object]:
    """逐键校验并复制 scaler 状态。"""

    if not _is_object_mapping(value):
        raise ValueError("checkpoint scaler state must be a mapping")
    output: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError("checkpoint scaler state keys must be strings")
        output[key] = item
    return output


@dataclass(slots=True)
class PrecisionPolicy:
    """提供 fp32、bf16 autocast 和 fp16 GradScaler 行为。

    构造对象不访问 CUDA,设备相关 scaler 仅在 ``setup`` 后按需创建。
    """

    mode: PrecisionMode
    _device_type: str | None = None
    _scaler: _GradScaler | None = None

    def __post_init__(self) -> None:
        """拒绝未知模式,禁止静默回退。"""

        if self.mode not in {"float32", "bfloat16", "float16"}:
            raise ValueError(f"unsupported precision mode: {self.mode!r}")

    def setup(self, device: torch.device) -> None:
        """绑定设备类型并为 CUDA fp16 延迟创建 GradScaler。"""

        self._device_type = device.type
        if self.mode == "float16" and device.type != "cuda":
            raise ValueError("float16 scaling requires a CUDA device")
        self._scaler = _make_grad_scaler() if self.mode == "float16" else None

    @property
    def model_dtype(self) -> torch.dtype | None:
        """返回处理器可使用的浮点 dtype,fp32 返回 ``None``。"""

        if self.mode == "bfloat16":
            return torch.bfloat16
        if self.mode == "float16":
            return torch.float16
        return None

    def autocast(self) -> _ContextManager:
        """返回当前设备的 autocast 上下文。"""

        if self._device_type is None:
            raise RuntimeError("precision policy is not set up")
        if self.mode == "float32":
            return nullcontext()
        dtype = torch.bfloat16 if self.mode == "bfloat16" else torch.float16
        return _make_autocast(self._device_type, dtype)

    def backward(self, loss: torch.Tensor) -> None:
        """按精度策略执行缩放或普通反向。"""

        if self._scaler is None:
            _run_backward(loss)
        else:
            _run_backward(self._scaler.scale(loss))

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
            self._scaler.load_state_dict(_scaler_state(scaler_state))

    def validate_state_dict(self, state: dict[str, object]) -> None:
        """不修改 live scaler 地验证精度和缩放器状态。"""

        if set(state) != {"mode", "scaler"}:
            raise ValueError("checkpoint precision fields are incomplete or unknown")
        if state.get("mode") != self.mode:
            raise ValueError("checkpoint precision mode does not match current policy")
        scaler_state = state.get("scaler")
        if scaler_state is not None:
            if self._scaler is None:
                raise ValueError("checkpoint scaler state is incompatible")
            validated = _scaler_state(scaler_state)
            current = self._scaler.state_dict()
            if set(validated) != set(current):
                raise ValueError("checkpoint scaler fields are incompatible")


__all__ = ["PrecisionMode", "PrecisionPolicy"]
