"""GenesisVLA 动作数组与动作空间契约。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, TypeAlias

from numpy.typing import NDArray

NumericArray: TypeAlias = NDArray[Any]
ImageLike: TypeAlias = NDArray[Any]
ActionMask: TypeAlias = NDArray[Any]


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
        if self.horizon <= 0:
            raise ValueError("horizon must be positive")
        if self.action_dim <= 0:
            raise ValueError("action_dim must be positive")
        if self.values.ndim != 2:
            raise ValueError("action values must be a 2-D array")
        expected_shape = (self.horizon, self.action_dim)
        if self.values.shape != expected_shape:
            raise ValueError(f"action shape must be {expected_shape}, got {self.values.shape}")
        if self.mask is not None and self.mask.shape != self.values.shape:
            raise ValueError(
                f"action mask shape must match values shape {self.values.shape}, "
                f"got {self.mask.shape}"
            )


@dataclass(frozen=True, slots=True)
class ActionSpace:
    """描述动作空间的最小静态信息。

    Args:
        horizon: 默认动作时间步数量,必须为正整数。
        action_dim: 单步动作维度,必须为正整数。
        normalized: 表示该动作空间是否使用归一化动作。
        names: 可选动作维度名称,数量不能超过 ``action_dim``。
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
        if len(self.names) > self.action_dim:
            raise ValueError("names length must not exceed action_dim")
