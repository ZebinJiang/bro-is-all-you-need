"""动作模式转换。"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from genesisvla.core.types import RawSample

_SUPPORTED_MODES = ("abs", "delta", "relative")


class ActionModeTransform:
    """在 RawSample 动作数组上执行最小动作模式转换。

    Args:
        mode: 动作模式,仅支持 ``abs``、``delta`` 和 ``relative``。
    """

    def __init__(self, mode: str) -> None:
        """校验动作模式并保存配置。"""
        if mode not in _SUPPORTED_MODES:
            joined = ", ".join(_SUPPORTED_MODES)
            raise ValueError(f"unsupported action mode {mode!r}; expected one of: {joined}")
        self.mode = mode

    def __call__(self, sample: RawSample) -> RawSample:
        """按配置转换动作数组。"""
        actions = sample.actions
        if actions is None:
            raise ValueError("actions are required for action mode transform")

        if self.mode == "abs":
            return sample
        if self.mode == "delta":
            delta = np.empty_like(actions)
            delta[0] = actions[0]
            if actions.shape[0] > 1:
                delta[1:] = actions[1:] - actions[:-1]
            return replace(sample, actions=delta)

        state = sample.state
        if state is None:
            raise ValueError("state is required for relative action mode")
        if state.ndim != 1:
            raise ValueError("state must be 1-D for relative action mode")
        action_dim = actions.shape[1]
        if state.shape[0] < action_dim:
            raise ValueError("state length must be at least action_dim for relative action mode")
        base = state[:action_dim].astype(actions.dtype, copy=False)
        return replace(sample, actions=actions - base)
