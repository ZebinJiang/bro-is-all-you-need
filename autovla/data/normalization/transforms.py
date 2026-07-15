"""针对同一统计计划提供 NumPy 和可选 Torch 执行。"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass
from importlib import import_module
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from autovla.core.semantics import AlignmentPolicy, TensorLayout
from autovla.data.normalization.statistics import (
    BoolArray,
    FeatureStatistics,
    FloatArray,
    _align_numpy,
)

NumericArray = NDArray[Any]
Float32Array = NDArray[np.float32]


class _TorchTensor(Protocol):
    """描述可选适配器实际使用的最小 Torch 张量表面。"""

    ndim: int
    shape: Sequence[int]
    dtype: object
    device: object

    def clone(self) -> "_TorchTensor":
        """复制张量。"""
        ...

    def all(self) -> "_TorchTensor":
        """归约布尔张量。"""
        ...

    def item(self) -> object:
        """返回标量。"""
        ...

    def __mul__(self, other: object) -> "_TorchTensor": ...

    def __add__(self, other: object) -> "_TorchTensor": ...

    def __sub__(self, other: object) -> "_TorchTensor": ...

    def __truediv__(self, other: object) -> "_TorchTensor": ...


class _TorchModule(Protocol):
    """描述惰性 Torch 模块所需的最小函数集合。"""

    bool: object

    def is_tensor(self, value: object) -> bool: ...

    def isfinite(self, value: _TorchTensor) -> _TorchTensor: ...

    def as_tensor(self, value: object, *, dtype: object, device: object) -> _TorchTensor: ...

    def where(
        self, condition: _TorchTensor, left: _TorchTensor, right: _TorchTensor
    ) -> _TorchTensor: ...


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
    """使用显式值布局和对齐策略执行 NumPy 归一化。"""

    statistics: FeatureStatistics
    value_layout: TensorLayout | None = None
    alignment: AlignmentPolicy | None = None

    def _validate(self, value: object) -> Float32Array:
        """校验数值和布局秩并返回拥有副本。"""
        array = np.asarray(value)
        if not np.issubdtype(array.dtype, np.number) or not bool(np.isfinite(array).all()):
            raise ValueError("normalization input must be finite numeric data")
        layout = self.value_layout or self.statistics.layout
        if array.ndim != layout.rank:
            raise ValueError("normalization input rank must match explicit value_layout")
        return np.array(array, dtype=np.float32, copy=True)

    def aligned_parameters(
        self, value: Float32Array, *, broadcast: bool = True
    ) -> tuple[FloatArray | None, FloatArray | None, BoolArray]:
        """把偏移、尺度和活动掩码对齐到值形状。"""
        offset, scale = self.statistics.parameters()
        layout = self.value_layout or self.statistics.layout
        policy = self.alignment or self.statistics.alignment
        shape = tuple(int(size) for size in value.shape)
        active = cast(
            BoolArray,
            _align_numpy(
                self.statistics.active_mask(),
                source_layout=self.statistics.layout,
                target_layout=layout,
                target_shape=shape,
                policy=policy,
                broadcast=broadcast,
            ),
        )
        if offset is None or scale is None:
            return None, None, active
        return (
            cast(
                FloatArray,
                _align_numpy(
                    offset,
                    source_layout=self.statistics.layout,
                    target_layout=layout,
                    target_shape=shape,
                    policy=policy,
                    broadcast=broadcast,
                ),
            ),
            cast(
                FloatArray,
                _align_numpy(
                    scale,
                    source_layout=self.statistics.layout,
                    target_layout=layout,
                    target_shape=shape,
                    policy=policy,
                    broadcast=broadcast,
                ),
            ),
            active,
        )

    def normalize(self, value: object) -> Float32Array:
        """仅归一化活动位置; 常量 identity 位置保持物理值。"""
        output = self._validate(value)
        offset, scale, active = self.aligned_parameters(output)
        if offset is not None and scale is not None:
            output[active] = (output[active] - offset[active]) / scale[active]
        return output

    def denormalize(self, value: object) -> Float32Array:
        """仅反归一化活动位置并保持完全可逆。"""
        output = self._validate(value)
        offset, scale, active = self.aligned_parameters(output)
        if offset is not None and scale is not None:
            output[active] = output[active] * scale[active] + offset[active]
        return output


@dataclass(frozen=True, slots=True)
class TorchStatisticsNormalizationTransform:
    """惰性 Torch 适配器; 语义计划仍由同一个规范统计量生成。"""

    statistics: FeatureStatistics
    value_layout: TensorLayout | None = None
    alignment: AlignmentPolicy | None = None

    def _execute(self, value: object, *, inverse: bool) -> object:
        """惰性导入 Torch 并在原设备上应用共享参数计划。"""
        try:
            torch = cast(_TorchModule, import_module("torch"))
        except ImportError as exc:  # pragma: no cover - 取决于可选环境
            raise ImportError("Torch normalization adapter requires the torch extra") from exc
        if not torch.is_tensor(value):
            raise TypeError("Torch normalization adapter requires torch.Tensor input")
        tensor = cast(_TorchTensor, value)
        if not bool(torch.isfinite(tensor).all().item()):
            raise ValueError("normalization input must be finite")
        layout = self.value_layout or self.statistics.layout
        if tensor.ndim != layout.rank:
            raise ValueError("normalization input rank must match explicit value_layout")
        helper = StatisticsNormalizationTransform(
            self.statistics,
            value_layout=layout,
            alignment=self.alignment,
        )
        # 仅生成小型统计参数计划; 动作张量本身不在 CPU/GPU 间搬运。
        shape_probe = np.broadcast_to(
            np.empty((), dtype=np.float32), tuple(int(size) for size in tensor.shape)
        )
        offset, scale, active = helper.aligned_parameters(shape_probe, broadcast=False)
        output = tensor.clone()
        if offset is None or scale is None:
            return output
        torch_offset = torch.as_tensor(
            np.array(offset, copy=True), dtype=output.dtype, device=output.device
        )
        torch_scale = torch.as_tensor(
            np.array(scale, copy=True), dtype=output.dtype, device=output.device
        )
        torch_active = torch.as_tensor(
            np.array(active, copy=True), dtype=torch.bool, device=output.device
        )
        candidate = (
            output * torch_scale + torch_offset
            if inverse
            else (output - torch_offset) / torch_scale
        )
        return torch.where(torch_active, candidate, output)

    def normalize(self, value: object) -> object:
        """在 Torch 张量上执行正向归一化。"""
        return self._execute(value, inverse=False)

    def denormalize(self, value: object) -> object:
        """在 Torch 张量上执行反向归一化。"""
        return self._execute(value, inverse=True)


@dataclass(frozen=True, slots=True)
class RelativeActionTransform:
    """在动作和固定参考状态之间执行显式相对量转换。"""

    dimensions: tuple[int, ...]

    def __post_init__(self) -> None:
        """校验相对动作维度唯一且非负。"""
        if any(type(index) is not int or index < 0 for index in self.dimensions):
            raise ValueError("relative action dimensions must be non-negative integers")
        if len(set(self.dimensions)) != len(self.dimensions):
            raise ValueError("relative action dimensions must be unique")

    def _apply(self, actions: object, reference_state: object, *, inverse: bool) -> Float32Array:
        """按固定参考状态执行正向或逆向变换。"""
        output = np.array(actions, dtype=np.float32, copy=True)
        state = np.asarray(reference_state, dtype=np.float32)
        if output.ndim < 2 or state.ndim != 1 or not bool(np.isfinite(output).all()):
            raise ValueError("actions must be finite [...,H,D] and reference_state must be [D]")
        for dimension in self.dimensions:
            if dimension >= output.shape[-1] or dimension >= state.shape[0]:
                raise ValueError("relative action dimension is out of range")
            if inverse:
                output[..., dimension] += state[dimension]
            else:
                output[..., dimension] -= state[dimension]
        return output

    def to_relative(self, actions: object, reference_state: object) -> Float32Array:
        """把绝对动作转换为固定状态参考的相对动作。"""
        return self._apply(actions, reference_state, inverse=False)

    def to_absolute(self, actions: object, reference_state: object) -> Float32Array:
        """把相对动作恢复为绝对动作。"""
        return self._apply(actions, reference_state, inverse=True)


__all__ = [
    "NormalizationTransform",
    "RelativeActionTransform",
    "StatisticsNormalizationTransform",
    "TorchStatisticsNormalizationTransform",
]
