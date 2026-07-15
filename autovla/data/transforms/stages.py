"""提供规范变换计划的 NumPy 阶段实现。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
from numpy.typing import NDArray

from autovla.core.semantics import (
    AlignmentPolicy,
    MaskKind,
    MaskSemantics,
    MaskTruth,
    TensorLayout,
)
from autovla.data.normalization import FeatureStatistics, StatisticsNormalizationTransform
from autovla.data.transforms.pipeline import (
    ExecutionSide,
    FeatureContract,
    FeatureMap,
    StageDescriptor,
)


def _copy(features: FeatureMap) -> dict[str, object]:
    """复制顶层特征映射, 阶段只替换自己拥有的键。"""
    return dict(features)


def _numeric(features: FeatureMap, key: str) -> NDArray[np.generic]:
    """读取有限数值数组并拒绝隐式缺失。"""
    if key not in features:
        raise KeyError(f"transform feature {key!r} is missing")
    array = np.asarray(features[key])
    if not np.issubdtype(array.dtype, np.number) or not bool(np.isfinite(array).all()):
        raise ValueError(f"transform feature {key!r} must be finite numeric data")
    return array


@dataclass(frozen=True, slots=True)
class SemanticMask:
    """绑定严格 bool 数组和不可混淆的掩码语义。"""

    values: NDArray[np.bool_]
    semantics: MaskSemantics

    def __post_init__(self) -> None:
        """拥有并冻结严格 bool 数组。"""
        raw = np.asarray(self.values)
        if raw.dtype != np.dtype(np.bool_) or raw.ndim != self.semantics.layout.rank:
            raise TypeError("semantic mask must be strict bool with its declared layout rank")
        owned = np.array(raw, dtype=np.bool_, copy=True)
        owned.setflags(write=False)
        object.__setattr__(self, "values", owned)


@dataclass(frozen=True, slots=True)
class FeatureRenameStage:
    """可逆地重命名一个特征。"""

    source: str
    target: str
    implementation_version: str = "1"
    name: str = "feature_rename"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明重命名保持原布局且不依赖状态或统计量。"""
        return StageDescriptor(
            (FeatureContract(self.source, None, "preserve"),),
            (FeatureContract(self.target, None, "preserve"),),
            reversible=True,
            execution_side=self.execution_side,
        )

    def __post_init__(self) -> None:
        """拒绝空名和自重命名。"""
        if not self.source.strip() or not self.target.strip() or self.source == self.target:
            raise ValueError("feature rename requires two distinct non-empty names")

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """把源键移动到目标键。"""
        if self.source not in features or self.target in features:
            raise ValueError("feature rename source must exist and target must be absent")
        output = _copy(features)
        output[self.target] = output.pop(self.source)
        return output

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """恢复原始特征名。"""
        return FeatureRenameStage(self.target, self.source).forward(features)

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "source": self.source,
            "target": self.target,
            "descriptor": self.descriptor.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class TemporalAlignmentStage:
    """按显式索引对齐时间轴, 并产生独立 temporal mask。"""

    feature: str
    source_layout: TensorLayout
    indices: tuple[int, ...]
    source_length: int
    mask_feature: str
    pad_value: float = 0.0
    implementation_version: str = "1"
    name: str = "temporal_alignment"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明时间特征输入及独立 temporal mask 输出。"""
        return StageDescriptor(
            (FeatureContract(self.feature, self.source_layout),),
            (
                FeatureContract(self.feature, self.source_layout, "derived"),
                FeatureContract(self.mask_feature, TensorLayout.time(len(self.indices))),
            ),
            reversible=tuple(sorted(self.indices)) == tuple(range(self.source_length)),
            mask_behavior=("produce:temporal:true_is_valid",),
            execution_side=self.execution_side,
        )

    def __post_init__(self) -> None:
        """校验时间轴、源长度和索引。"""
        if not self.source_layout.contains("time"):
            raise ValueError("temporal alignment requires an explicit time axis")
        if self.source_length <= 0 or not self.indices:
            raise ValueError("temporal alignment requires positive source_length and indices")
        if any(index < -1 or index >= self.source_length for index in self.indices):
            raise ValueError("temporal alignment index is out of range; -1 is the only pad marker")

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """按索引取帧, ``-1`` 填充并标记 temporal 无效。"""
        values = _numeric(features, self.feature)
        axis = self.source_layout.index("time")
        if values.ndim != self.source_layout.rank or values.shape[axis] != self.source_length:
            raise ValueError("temporal source shape does not match declared layout/length")
        output_shape = list(values.shape)
        output_shape[axis] = len(self.indices)
        aligned = np.full(output_shape, self.pad_value, dtype=values.dtype)
        temporal_valid = np.asarray([index >= 0 for index in self.indices], dtype=np.bool_)
        for target_index, source_index in enumerate(self.indices):
            if source_index < 0:
                continue
            target_slice: list[slice | int] = [slice(None)] * values.ndim
            source_slice: list[slice | int] = [slice(None)] * values.ndim
            target_slice[axis] = target_index
            source_slice[axis] = source_index
            aligned[tuple(target_slice)] = values[tuple(source_slice)]
        output = _copy(features)
        output[self.feature] = aligned
        output[self.mask_feature] = SemanticMask(
            temporal_valid,
            MaskSemantics(MaskKind.TEMPORAL, TensorLayout.time(), MaskTruth.TRUE_IS_VALID),
        )
        return output

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """仅当索引是源时间轴完整排列时恢复原顺序。"""
        if tuple(sorted(self.indices)) != tuple(range(self.source_length)):
            raise ValueError(
                "temporal alignment is not reversible unless indices are a permutation"
            )
        values = _numeric(features, self.feature)
        axis = self.source_layout.index("time")
        inverse_indices = np.argsort(np.asarray(self.indices, dtype=np.int64))
        output = _copy(features)
        output[self.feature] = np.take(values, inverse_indices, axis=axis)
        output.pop(self.mask_feature, None)
        return output

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "feature": self.feature,
            "source_layout": self.source_layout.to_json_dict(),
            "indices": list(self.indices),
            "source_length": self.source_length,
            "mask_feature": self.mask_feature,
            "pad_value": self.pad_value,
            "descriptor": self.descriptor.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class RelativeActionStage:
    """执行 previous-action delta 或固定 state-reference 相对动作。"""

    action_feature: str = "actions"
    mode: Literal["previous_delta", "state_relative"] = "state_relative"
    state_feature: str = "state"
    action_dimensions: tuple[int, ...] = ()
    state_indices: tuple[int, ...] = ()
    implementation_version: str = "1"
    name: str = "relative_action"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明动作和可选固定状态参考依赖。"""
        inputs = [FeatureContract(self.action_feature, TensorLayout.time_feature())]
        state_dependencies: tuple[str, ...] = ()
        if self.mode == "state_relative":
            inputs.append(FeatureContract(self.state_feature, TensorLayout.feature()))
            state_dependencies = (self.state_feature,)
        return StageDescriptor(
            tuple(inputs),
            (FeatureContract(self.action_feature, TensorLayout.time_feature()),),
            reversible=True,
            state_dependencies=state_dependencies,
            execution_side=self.execution_side,
        )

    def __post_init__(self) -> None:
        """校验动作维度和 state 映射。"""
        if self.mode not in {"previous_delta", "state_relative"}:
            raise ValueError("unsupported relative action mode")
        if self.mode == "state_relative":
            if not self.action_dimensions or len(self.action_dimensions) != len(self.state_indices):
                raise ValueError("state_relative requires equal explicit action/state mappings")
        for values in (self.action_dimensions, self.state_indices):
            if any(type(index) is not int or index < 0 for index in values) or len(
                set(values)
            ) != len(values):
                raise ValueError("relative action mappings must be unique non-negative integers")

    def _state_relative(self, features: FeatureMap, *, inverse: bool) -> dict[str, object]:
        """按固定状态参考转换选定动作维度。"""
        actions = np.array(_numeric(features, self.action_feature), dtype=np.float32, copy=True)
        state = _numeric(features, self.state_feature)
        if actions.ndim < 2 or state.ndim != 1:
            raise ValueError("state_relative requires actions [...,T,D] and state [S]")
        for action_index, state_index in zip(
            self.action_dimensions, self.state_indices, strict=True
        ):
            if action_index >= actions.shape[-1] or state_index >= state.shape[0]:
                raise ValueError("relative action mapping is out of range")
            if inverse:
                actions[..., action_index] += state[state_index]
            else:
                actions[..., action_index] -= state[state_index]
        output = _copy(features)
        output[self.action_feature] = actions
        return output

    def _previous_delta(self, features: FeatureMap, *, inverse: bool) -> dict[str, object]:
        """以前一动作为参考转换, 首步保持绝对值以确保可逆。"""
        actions = np.array(_numeric(features, self.action_feature), dtype=np.float32, copy=True)
        if actions.ndim != 2 or actions.shape[0] <= 0:
            raise ValueError("previous_delta requires non-empty [T,D] actions")
        converted = np.empty_like(actions)
        converted[0] = actions[0]
        if inverse:
            for index in range(1, actions.shape[0]):
                converted[index] = converted[index - 1] + actions[index]
        else:
            converted[1:] = actions[1:] - actions[:-1]
        output = _copy(features)
        output[self.action_feature] = converted
        return output

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """执行正向相对动作转换。"""
        if self.mode == "previous_delta":
            return self._previous_delta(features, inverse=False)
        return self._state_relative(features, inverse=False)

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """执行逆向绝对动作恢复。"""
        if self.mode == "previous_delta":
            return self._previous_delta(features, inverse=True)
        return self._state_relative(features, inverse=True)

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "action_feature": self.action_feature,
            "mode": self.mode,
            "state_feature": self.state_feature,
            "action_dimensions": list(self.action_dimensions),
            "state_indices": list(self.state_indices),
            "descriptor": self.descriptor.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class NormalizeStage:
    """对一个特征执行规范统计量正向和逆向变换。"""

    feature: str
    statistics: FeatureStatistics
    value_layout: TensorLayout
    alignment: AlignmentPolicy
    implementation_version: str = "1"
    name: str = "normalize"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明值布局和规范统计量指纹依赖。"""
        return StageDescriptor(
            (FeatureContract(self.feature, self.value_layout),),
            (FeatureContract(self.feature, self.value_layout),),
            reversible=True,
            statistics_dependencies=(self.statistics.fingerprint,),
            execution_side=self.execution_side,
        )

    def _transform(self) -> StatisticsNormalizationTransform:
        """构造无状态 NumPy 执行器。"""
        return StatisticsNormalizationTransform(
            self.statistics,
            value_layout=self.value_layout,
            alignment=self.alignment,
        )

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """归一化指定特征。"""
        output = _copy(features)
        output[self.feature] = self._transform().normalize(_numeric(features, self.feature))
        return output

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """反归一化指定特征。"""
        output = _copy(features)
        output[self.feature] = self._transform().denormalize(_numeric(features, self.feature))
        return output

    def to_json_dict(self) -> dict[str, object]:
        """返回包含完整统计指纹和内容的稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "feature": self.feature,
            "statistics": self.statistics.to_json_dict(),
            "statistics_fingerprint": self.statistics.fingerprint,
            "value_layout": self.value_layout.to_json_dict(),
            "alignment": self.alignment.to_json_dict(),
            "descriptor": self.descriptor.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class PaddingStage:
    """按显式源/目标形状尾部补齐并生成独立 padding mask。"""

    feature: str
    layout: TensorLayout
    source_shape: tuple[int, ...]
    target_shape: tuple[int, ...]
    mask_feature: str
    pad_value: float = 0.0
    implementation_version: str = "1"
    name: str = "padding"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明 shape 扩展和独立 padding mask 输出。"""
        source_layout = self.layout.with_sizes(self.source_shape)
        target_layout = self.layout.with_sizes(self.target_shape)
        return StageDescriptor(
            (FeatureContract(self.feature, source_layout),),
            (
                FeatureContract(self.feature, target_layout),
                FeatureContract(self.mask_feature, target_layout),
            ),
            reversible=True,
            mask_behavior=("produce:padding:true_is_valid",),
            execution_side=self.execution_side,
        )

    def __post_init__(self) -> None:
        """校验布局秩和单调扩展。"""
        if len(self.source_shape) != self.layout.rank or len(self.target_shape) != self.layout.rank:
            raise ValueError("padding shapes must match explicit layout rank")
        if any(
            source <= 0 or target < source
            for source, target in zip(self.source_shape, self.target_shape, strict=True)
        ):
            raise ValueError(
                "padding target dimensions must be positive and not smaller than source"
            )

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """执行尾部 padding 并输出严格 bool 有效掩码。"""
        values = _numeric(features, self.feature)
        if values.shape != self.source_shape:
            raise ValueError("padding input shape does not match declared source_shape")
        padded = np.full(self.target_shape, self.pad_value, dtype=values.dtype)
        valid = np.zeros(self.target_shape, dtype=np.bool_)
        slices = tuple(slice(0, size) for size in self.source_shape)
        padded[slices] = values
        valid[slices] = True
        output = _copy(features)
        output[self.feature] = padded
        output[self.mask_feature] = SemanticMask(
            valid,
            MaskSemantics(MaskKind.PADDING, self.layout, MaskTruth.TRUE_IS_VALID),
        )
        return output

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """裁回源形状并移除派生 padding mask。"""
        values = _numeric(features, self.feature)
        if values.shape != self.target_shape:
            raise ValueError("padding inverse shape does not match declared target_shape")
        output = _copy(features)
        output[self.feature] = np.array(
            values[tuple(slice(0, size) for size in self.source_shape)], copy=True
        )
        output.pop(self.mask_feature, None)
        return output

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "feature": self.feature,
            "layout": self.layout.to_json_dict(),
            "source_shape": list(self.source_shape),
            "target_shape": list(self.target_shape),
            "mask_feature": self.mask_feature,
            "pad_value": self.pad_value,
            "descriptor": self.descriptor.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class MaskCompositionStage:
    """显式组合同布局、同真值语义的掩码, 不改变源掩码。"""

    inputs: tuple[str, ...]
    output: str
    kind: MaskKind
    operation: Literal["and", "or"] = "and"
    implementation_version: str = "1"
    name: str = "mask_composition"
    execution_side: ExecutionSide = ExecutionSide.DATA

    @property
    def descriptor(self) -> StageDescriptor:
        """声明源掩码不变并产出一种明确类别的组合掩码。"""
        return StageDescriptor(
            tuple(FeatureContract(name, None, "preserve") for name in self.inputs),
            (FeatureContract(self.output, None, "derived"),),
            reversible=True,
            mask_behavior=(f"compose:{self.operation}:{self.kind.value}",),
            execution_side=self.execution_side,
        )

    def __post_init__(self) -> None:
        """拒绝空输入、重复输入和覆盖源键。"""
        if (
            not self.inputs
            or len(set(self.inputs)) != len(self.inputs)
            or self.output in self.inputs
        ):
            raise ValueError("mask composition requires unique inputs and a distinct output")

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """组合严格语义掩码。"""
        masks: list[SemanticMask] = []
        for key in self.inputs:
            value = features.get(key)
            if not isinstance(value, SemanticMask):
                raise TypeError("mask composition inputs must be SemanticMask objects")
            masks.append(value)
        first = masks[0]
        if any(
            mask.semantics.layout != first.semantics.layout
            or mask.semantics.truth != first.semantics.truth
            or mask.values.shape != first.values.shape
            for mask in masks[1:]
        ):
            raise ValueError("mask composition requires identical layout, truth and shape")
        values = np.array(first.values, copy=True)
        for mask in masks[1:]:
            values = values & mask.values if self.operation == "and" else values | mask.values
        output = _copy(features)
        output[self.output] = SemanticMask(
            values,
            MaskSemantics(self.kind, first.semantics.layout, first.semantics.truth),
        )
        return output

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """移除派生组合掩码, 保留所有源掩码。"""
        output = _copy(features)
        output.pop(self.output, None)
        return output

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定计划项。"""
        return {
            "name": self.name,
            "implementation_version": self.implementation_version,
            "inputs": list(self.inputs),
            "output": self.output,
            "kind": self.kind.value,
            "operation": self.operation,
            "descriptor": self.descriptor.to_json_dict(),
        }


__all__ = [
    "FeatureRenameStage",
    "MaskCompositionStage",
    "NormalizeStage",
    "PaddingStage",
    "RelativeActionStage",
    "SemanticMask",
    "TemporalAlignmentStage",
]
