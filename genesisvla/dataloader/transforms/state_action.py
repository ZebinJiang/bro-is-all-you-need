"""M2 状态/动作归一化转换。"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import FeatureStatistics


def _valid_mask(stats: FeatureStatistics) -> NDArray[np.bool_]:
    """返回统计量有效维度 mask。"""
    if stats.valid_mask is None:
        return np.ones((stats.dimension,), dtype=np.bool_)
    return np.asarray(stats.valid_mask, dtype=np.bool_)


def _check_array(
    name: str,
    array: NDArray[np.generic],
    stats: FeatureStatistics,
) -> NDArray[np.float64]:
    """校验样本最后一维和统计量维度匹配。"""
    values = np.asarray(array, dtype=np.float64)
    if values.shape[-1] != stats.dimension:
        raise ValueError(f"{name} dimension must match statistics dimension")
    return values


def _normalize_array(
    name: str,
    array: NDArray[np.generic],
    stats: FeatureStatistics,
) -> NDArray[np.float32]:
    """按统计量归一化数组, invalid 维度保持原值。"""
    values = _check_array(name, array, stats)
    output = values.copy()
    mask = _valid_mask(stats)
    if stats.method == "mean_std":
        assert stats.mean is not None and stats.std is not None
        scale = stats.std.copy()
        zero_mask = scale == 0.0
        if bool(np.any(zero_mask & mask)) and stats.zero_variance_policy == "raise":
            raise ValueError("std contains zero variance dimensions")
        mask = mask & ~zero_mask
        scale[zero_mask] = 1.0
        output[..., mask] = (values[..., mask] - stats.mean[mask]) / scale[mask]
    else:
        assert stats.minimum is not None and stats.maximum is not None
        scale = stats.maximum - stats.minimum
        zero_mask = scale == 0.0
        if bool(np.any(zero_mask & mask)) and stats.zero_variance_policy == "raise":
            raise ValueError("min_max contains zero range dimensions")
        mask = mask & ~zero_mask
        scale[zero_mask] = 1.0
        output[..., mask] = (values[..., mask] - stats.minimum[mask]) / scale[mask]
    return output.astype(np.float32)


def _unnormalize_array(
    name: str,
    array: NDArray[np.generic],
    stats: FeatureStatistics,
) -> NDArray[np.float32]:
    """按统计量反归一化数组, invalid 维度保持原值。"""
    values = _check_array(name, array, stats)
    output = values.copy()
    mask = _valid_mask(stats)
    if stats.method == "mean_std":
        assert stats.mean is not None and stats.std is not None
        scale = stats.std.copy()
        zero_mask = scale == 0.0
        mask = mask & ~zero_mask
        scale[zero_mask] = 1.0
        output[..., mask] = values[..., mask] * scale[mask] + stats.mean[mask]
    else:
        assert stats.minimum is not None and stats.maximum is not None
        scale = stats.maximum - stats.minimum
        zero_mask = scale == 0.0
        mask = mask & ~zero_mask
        scale[zero_mask] = 1.0
        output[..., mask] = values[..., mask] * scale[mask] + stats.minimum[mask]
    return output.astype(np.float32)


class StateActionNormalize:
    """对 state/actions 执行显式统计量归一化。"""

    def __init__(
        self,
        *,
        state: FeatureStatistics | None = None,
        action: FeatureStatistics | None = None,
    ) -> None:
        self.state = state
        self.action = action

    def __call__(self, sample: RawSample) -> RawSample:
        """返回归一化后的样本。"""
        state = sample.state
        actions = sample.actions
        if self.state is not None:
            if state is None:
                raise ValueError("state is required for state normalization")
            state = _normalize_array("state", state, self.state)
        if self.action is not None:
            if actions is None:
                raise ValueError("actions are required for action normalization")
            actions = _normalize_array("actions", actions, self.action)
        return replace(sample, state=state, actions=actions)


class StateActionUnnormalize:
    """对 state/actions 执行显式统计量反归一化。"""

    def __init__(
        self,
        *,
        state: FeatureStatistics | None = None,
        action: FeatureStatistics | None = None,
    ) -> None:
        self.state = state
        self.action = action

    def __call__(self, sample: RawSample) -> RawSample:
        """返回反归一化后的样本。"""
        state = sample.state
        actions = sample.actions
        if self.state is not None:
            if state is None:
                raise ValueError("state is required for state unnormalization")
            state = _unnormalize_array("state", state, self.state)
        if self.action is not None:
            if actions is None:
                raise ValueError("actions are required for action unnormalization")
            actions = _unnormalize_array("actions", actions, self.action)
        return replace(sample, state=state, actions=actions)
