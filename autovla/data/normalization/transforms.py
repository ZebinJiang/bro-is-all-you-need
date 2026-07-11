"""AutoVLA 归一化和反归一化变换。"""

from __future__ import annotations

from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol

import numpy as np
from numpy.typing import NDArray

from autovla.data.normalization.statistics import (
    BoolArray,
    FeatureNormalizationStatistics,
    FloatArray,
)

NumericArray = NDArray[Any]
Float32Array = NDArray[np.float32]


class NormalizationTransform(Protocol):
    """定义可逆数值归一化边界。"""

    @abstractmethod
    def normalize(self, value: object) -> NumericArray:
        """返回拥有的归一化数组。"""
        raise NotImplementedError

    @abstractmethod
    def denormalize(self, value: object) -> NumericArray:
        """返回拥有的物理量数组。"""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class StatisticsNormalizationTransform:
    """根据类型化统计量执行最后一维归一化。"""

    statistics: FeatureNormalizationStatistics
    epsilon: float = 1e-8

    def _parameters(self) -> tuple[FloatArray | None, FloatArray | None]:
        """把统计方法转换为统一偏移和尺度。"""
        method = self.statistics.method
        if method == "identity":
            return None, None
        if method == "mean_std":
            return self.statistics.center, self.statistics.scale
        if method == "min_max":
            minimum = self.statistics.minimum
            maximum = self.statistics.maximum
            assert minimum is not None and maximum is not None
            return minimum, maximum - minimum
        lower = self.statistics.lower_quantile
        upper = self.statistics.upper_quantile
        assert lower is not None and upper is not None
        return lower, upper - lower

    def _validate(self, value: object) -> Float32Array:
        """校验最后一维并复制有限数值。"""
        array = np.asarray(value)
        if not np.issubdtype(array.dtype, np.number) or not bool(np.isfinite(array).all()):
            raise ValueError("normalization input must be finite numeric data")
        dimension = self.statistics.dimension
        if dimension is not None and array.shape[-1] != dimension:
            raise ValueError(
                f"normalization input final dimension must be {dimension}, got {array.shape[-1]}"
            )
        return np.array(array, dtype=np.float32, copy=True)

    def _mask(self, array: NumericArray) -> BoolArray:
        """返回广播到输入最后一维的有效统计掩码。"""
        if self.statistics.valid_mask is None:
            return np.ones(array.shape[-1], dtype=np.bool_)
        return self.statistics.valid_mask

    def normalize(self, value: object) -> Float32Array:
        """归一化有效维度并原样保留 padding 维度。"""
        array = self._validate(value)
        offset, scale = self._parameters()
        if offset is None or scale is None:
            return array
        mask = self._mask(array)
        array[..., mask] = (array[..., mask] - offset[mask]) / np.maximum(scale[mask], self.epsilon)
        return array

    def denormalize(self, value: object) -> Float32Array:
        """反归一化有效维度并原样保留 padding 维度。"""
        array = self._validate(value)
        offset, scale = self._parameters()
        if offset is None or scale is None:
            return array
        mask = self._mask(array)
        array[..., mask] = array[..., mask] * scale[mask] + offset[mask]
        return array


@dataclass(frozen=True, slots=True)
class RelativeActionTransform:
    """在动作和参考状态之间执行显式相对量转换。"""

    dimensions: tuple[int, ...]

    def to_relative(self, actions: object, reference_state: object) -> Float32Array:
        """从指定动作维度减去对应参考状态。"""
        output = np.array(actions, dtype=np.float32, copy=True)
        state = np.asarray(reference_state, dtype=np.float32)
        if output.ndim < 2 or state.ndim != 1:
            raise ValueError("actions must be [...,H,D] and reference_state must be [D]")
        for dimension in self.dimensions:
            if dimension < 0 or dimension >= output.shape[-1] or dimension >= state.shape[0]:
                raise ValueError("relative action dimension is out of range")
            output[..., dimension] -= state[dimension]
        return output

    def to_absolute(self, actions: object, reference_state: object) -> Float32Array:
        """把相对动作指定维度恢复为绝对量。"""
        output = np.array(actions, dtype=np.float32, copy=True)
        state = np.asarray(reference_state, dtype=np.float32)
        for dimension in self.dimensions:
            if dimension < 0 or dimension >= output.shape[-1] or dimension >= state.shape[0]:
                raise ValueError("relative action dimension is out of range")
            output[..., dimension] += state[dimension]
        return output


__all__ = [
    "NormalizationTransform",
    "RelativeActionTransform",
    "StatisticsNormalizationTransform",
]
