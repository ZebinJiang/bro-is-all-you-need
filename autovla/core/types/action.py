"""AutoVLA 动作数组与动作空间契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias, cast

import numpy as np
from numpy.typing import NDArray

NumericArray: TypeAlias = NDArray[np.number[Any]]
ImageLike: TypeAlias = NumericArray
ActionMask: TypeAlias = NDArray[np.bool_]


@dataclass(frozen=True, slots=True)
class ActionChunk:
    """表示一段连续动作。

    Args:
        values: 二维 numpy 数组,形状必须为 ``(horizon, action_dim)``。
        mask: 可选动作掩码,存在时形状必须与 ``values`` 完全一致。
        horizon: 动作时间步数量,必须为正整数。
        action_dim: 单步动作维度,必须为正整数。
        normalized: 表示动作值是否已归一化。
    """

    values: NumericArray
    mask: ActionMask | None
    horizon: int
    action_dim: int
    normalized: bool

    def __post_init__(self) -> None:
        """校验动作张量形状与显式契约字段一致。"""
        values: NumericArray = np.array(self.values, copy=True)
        values.setflags(write=False)
        object.__setattr__(self, "values", values)
        if self.mask is not None:
            mask: ActionMask = np.array(self.mask, copy=True)
            mask.setflags(write=False)
            object.__setattr__(self, "mask", mask)
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        if self.action_dim <= 0:
            raise ValueError("action_dim must be positive")
        if values.ndim != 2:
            raise ValueError("action values must be a 2-D array")
        if not np.issubdtype(values.dtype, np.number):
            raise ValueError("action values must be numeric")
        finite_values: NDArray[np.bool_] = np.isfinite(values)
        if not bool(finite_values.all()):
            raise ValueError("action values must be finite")
        expected_shape = (self.horizon, self.action_dim)
        if values.shape != expected_shape:
            raise ValueError(f"action shape must be {expected_shape}, got {values.shape}")
        if self.mask is not None and self.mask.shape != values.shape:
            raise ValueError(
                f"action mask shape must match values shape {values.shape}, "
                f"got {self.mask.shape}"
            )
        if self.mask is not None and self.mask.dtype != np.bool_:
            raise ValueError("action mask dtype must be bool")


@dataclass(frozen=True, slots=True)
class ActionSpace:
    """描述动作空间的最小静态信息。

    Args:
        horizon: 默认动作时间步数量,必须为正整数。
        action_dim: 单步动作维度,必须为正整数。
        normalized: 表示该动作空间是否使用归一化动作。
        names: 可选动作维度名称,提供时数量必须等于 ``action_dim``。
    """

    horizon: int
    action_dim: int
    normalized: bool
    names: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验动作空间字段的基本一致性。"""
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        if self.action_dim <= 0:
            raise ValueError("action_dim must be positive")
        if self.names and len(self.names) != self.action_dim:
            raise ValueError("names length must equal action_dim when names are supplied")
        names = cast(tuple[object, ...], self.names)
        seen: set[str] = set()
        for index, name in enumerate(names):
            if not isinstance(name, str):
                raise ValueError(f"names[{index}] must be a string")
            if not name.strip():
                raise ValueError(f"names[{index}] must not be empty")
            if name in seen:
                raise ValueError("action names must be unique")
            seen.add(name)
