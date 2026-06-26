"""GenesisVLA 本地训练损失辅助函数。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import ActionMask, NumericArray


@dataclass(frozen=True, slots=True)
class MaskedActionLoss:
    """表示 action mask 约束下的标量损失。

    Args:
        value: 有效动作元素上的平均平方误差。
        valid_count: 参与损失统计的有效动作元素数量。
    """

    value: float
    valid_count: int


def validate_action_mask(mask: object, action_shape: tuple[int, ...]) -> ActionMask:
    """校验 action mask 为严格的 bool ``[B,H,D]`` 数组。"""
    if len(action_shape) != 3:
        raise ValueError("action_shape must describe [B,H,D]")
    array = np.asarray(mask)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError("action_mask must be bool [B,H,D] without coercion")
    if array.shape != action_shape:
        raise ValueError(f"action_mask shape must be {action_shape}, got {array.shape}")
    owned: ActionMask = np.array(array, dtype=np.bool_, copy=True)
    owned.setflags(write=False)
    return owned


def _numeric_action_array(value: object, *, name: str) -> NumericArray:
    """拥有并校验 action 张量为有限数值数组。"""
    array = np.asarray(value)
    if array.ndim != 3:
        raise ValueError(f"{name} must have shape [B,H,D]")
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    finite: NDArray[np.bool_] = np.isfinite(array)
    if not bool(finite.all()):
        raise ValueError(f"{name} must be finite")
    owned: NumericArray = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


def masked_action_mse(
    prediction: object,
    target: object,
    action_mask: object,
) -> MaskedActionLoss:
    """只在有效 action mask 元素上计算 MSE。"""
    prediction_array = _numeric_action_array(prediction, name="prediction")
    target_array = _numeric_action_array(target, name="target")
    if prediction_array.shape != target_array.shape:
        raise ValueError(
            f"prediction shape must match target shape {target_array.shape}, "
            f"got {prediction_array.shape}"
        )
    mask = validate_action_mask(action_mask, target_array.shape)
    valid_count = int(np.count_nonzero(mask))
    if valid_count <= 0:
        raise ValueError("valid action elements must be positive")
    diff: NDArray[Any] = prediction_array[mask] - target_array[mask]
    squared: NDArray[Any] = np.square(diff)
    return MaskedActionLoss(value=float(np.mean(squared)), valid_count=valid_count)
