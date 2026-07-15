"""提供规范变换计划的 NumPy 阶段实现。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
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
    if (
        not np.issubdtype(array.dtype, np.number)
        or np.issubdtype(array.dtype, np.complexfloating)
        or not bool(np.isfinite(array).all())
    ):
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
    stage_id: str = ""

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
        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
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
    stage_id: str = ""

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
        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
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
    stage_id: str = ""

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
        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
            "implementation_version": self.implementation_version,
            "action_feature": self.action_feature,
            "mode": self.mode,
            "state_feature": self.state_feature,
            "action_dimensions": list(self.action_dimensions),
            "state_indices": list(self.state_indices),
            "descriptor": self.descriptor.to_json_dict(),
        }


class PoseRepresentation(str, Enum):
    """声明动作向量中的位姿结构。"""

    TRANSLATION_ROTATION = "translation_rotation"


class RotationRepresentation(str, Enum):
    """声明旋转编码, 不绑定模型族名称。"""

    AXIS_ANGLE = "axis_angle"
    QUATERNION_XYZW = "quaternion_xyzw"


class TranslationAxes(str, Enum):
    """声明平移分量轴顺序。"""

    XYZ = "xyz"


class SE3FrameConvention(str, Enum):
    """声明相对位姿所在坐标系。"""

    REFERENCE_LOCAL = "reference_local"
    WORLD_DELTA = "world_delta"


class CurrentStateReference(str, Enum):
    """声明参考状态来源。"""

    EXPLICIT_FEATURE = "explicit_feature"
    LAST_OBSERVED_STATE = "last_observed_state"


class SE3TemporalAlignment(str, Enum):
    """声明参考位姿与动作时间轴对齐方式。"""

    CURRENT_STATE_TO_ALL_ACTIONS = "current_state_to_all_actions"


@dataclass(frozen=True, slots=True)
class SE3TypedParameter:
    """保存家族或 embodiment 的小型类型化标量参数。"""

    name: str
    value: str | int | float | bool

    def __post_init__(self) -> None:
        """拒绝空名称与非有限浮点值。"""

        if not self.name.strip():
            raise ValueError("SE3 parameter name must not be empty")
        if type(self.value) not in (str, int, float, bool):
            raise TypeError("SE3 parameter value must be an exact JSON scalar")
        if type(self.value) is float and not np.isfinite(self.value):
            raise ValueError("SE3 parameter float must be finite")

    def to_json_dict(self) -> dict[str, str | int | float | bool]:
        """返回稳定参数结构。"""

        return {"name": self.name, "value": self.value}


@dataclass(frozen=True, slots=True)
class SE3Tolerances:
    """声明旋转归一化和往返误差容限。"""

    quaternion_norm: float = 1e-8
    rotation_small_angle: float = 1e-8
    roundtrip_atol: float = 1e-5

    def __post_init__(self) -> None:
        """要求所有容限有限且为正。"""

        values = (self.quaternion_norm, self.rotation_small_angle, self.roundtrip_atol)
        if any(
            type(value) not in (int, float) or not np.isfinite(value) or value <= 0.0
            for value in values
        ):
            raise ValueError("SE3 tolerances must be finite positive values")

    def to_json_dict(self) -> dict[str, float]:
        """返回稳定容限结构。"""

        return {
            "quaternion_norm": self.quaternion_norm,
            "rotation_small_angle": self.rotation_small_angle,
            "roundtrip_atol": self.roundtrip_atol,
        }


DEFAULT_SE3_TOLERANCES = SE3Tolerances()


def closed_pose_row_validity(
    mask: NDArray[np.bool_],
    *,
    context: str,
) -> NDArray[np.bool_]:
    """按行关闭位姿掩码,仅允许整个位姿全有效或全无效。

    输入必须是 ``[T,P]`` 严格布尔位姿切片。返回 ``[T]`` 全有效行标记;
    全无效行返回 ``False``,部分有效行失败关闭。
    """

    values = np.asarray(mask)
    if values.dtype != np.dtype(np.bool_) or values.ndim != 2 or values.shape[1] <= 0:
        raise TypeError("closed pose mask must be a non-empty strict-bool [T,P] array")
    if not context.strip():
        raise ValueError("closed pose mask context must not be empty")
    all_valid = np.all(values, axis=1)
    all_invalid = np.all(~values, axis=1)
    if not bool(np.all(all_valid | all_invalid)):
        raise ValueError(
            f"{context} must be valid at every transformed step or fully invalid; "
            "partial rows violate closed pose masks"
        )
    return np.asarray(all_valid, dtype=np.bool_)


@dataclass(frozen=True, slots=True)
class SE3RotationCodec:
    """用一组显式共享容限统一轴角、XYZW 四元数与旋转矩阵转换。"""

    tolerances: SE3Tolerances = DEFAULT_SE3_TOLERANCES

    def __post_init__(self) -> None:
        """要求 codec 使用关闭的共享容限类型。"""

        if type(self.tolerances) is not SE3Tolerances:
            raise TypeError("SE3 rotation codec tolerances must use SE3Tolerances")

    def to_matrix(
        self,
        value: NDArray[np.generic],
        representation: RotationRepresentation,
    ) -> NDArray[np.float64]:
        """把轴角或 XYZW 四元数转换为 ``[3,3]`` 旋转矩阵。"""

        if type(representation) is not RotationRepresentation:
            raise TypeError("SE3 rotation representation must use RotationRepresentation")
        vector = np.asarray(value, dtype=np.float64)
        expected = 4 if representation is RotationRepresentation.QUATERNION_XYZW else 3
        if vector.shape != (expected,) or not bool(np.isfinite(vector).all()):
            raise ValueError(
                "SE3 rotation input must be a finite vector matching its representation"
            )
        if representation is RotationRepresentation.QUATERNION_XYZW:
            norm = float(np.linalg.norm(vector))
            if norm <= self.tolerances.quaternion_norm:
                raise ValueError("SE3 quaternion norm is too small")
            x, y, z, w = vector / norm
            return np.asarray(
                [
                    [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                    [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                    [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
                ],
                dtype=np.float64,
            )
        angle = float(np.linalg.norm(vector))
        if angle <= self.tolerances.rotation_small_angle:
            return np.eye(3, dtype=np.float64) + _skew(vector)
        axis = vector / angle
        skew = _skew(axis)
        return (
            np.eye(3, dtype=np.float64)
            + np.sin(angle) * skew
            + (1.0 - np.cos(angle)) * (skew @ skew)
        )

    def from_matrix(
        self,
        matrix: NDArray[np.generic],
        representation: RotationRepresentation,
    ) -> NDArray[np.float64]:
        """把有限 ``[3,3]`` 旋转矩阵稳定转换为声明表示。"""

        if type(representation) is not RotationRepresentation:
            raise TypeError("SE3 rotation representation must use RotationRepresentation")
        matrix64 = np.asarray(matrix, dtype=np.float64)
        if matrix64.shape != (3, 3) or not bool(np.isfinite(matrix64).all()):
            raise ValueError("SE3 rotation matrix must be finite with shape [3,3]")
        quaternion = self._matrix_to_quaternion_xyzw(matrix64)
        if representation is RotationRepresentation.QUATERNION_XYZW:
            return quaternion
        vector = quaternion[:3]
        scalar = min(max(float(quaternion[3]), -1.0), 1.0)
        norm = float(np.linalg.norm(vector))
        if norm <= self.tolerances.rotation_small_angle:
            return 2.0 * vector
        angle = 2.0 * float(np.arctan2(norm, scalar))
        if angle > np.pi:
            angle -= 2.0 * np.pi
        return vector / norm * angle

    def _matrix_to_quaternion_xyzw(
        self,
        matrix: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        """用最大对角分支避免接近 pi 时的数值消失。"""

        candidates = np.asarray(
            [
                1.0 + matrix[0, 0] - matrix[1, 1] - matrix[2, 2],
                1.0 - matrix[0, 0] + matrix[1, 1] - matrix[2, 2],
                1.0 - matrix[0, 0] - matrix[1, 1] + matrix[2, 2],
                1.0 + np.trace(matrix),
            ],
            dtype=np.float64,
        )
        index = int(np.argmax(candidates))
        root = np.sqrt(max(float(candidates[index]), 0.0)) * 0.5
        if root <= self.tolerances.quaternion_norm:
            raise ValueError("SE3 rotation matrix cannot be converted to a quaternion")
        denominator = 4.0 * root
        if index == 0:
            quaternion = np.asarray(
                [
                    root,
                    (matrix[0, 1] + matrix[1, 0]) / denominator,
                    (matrix[0, 2] + matrix[2, 0]) / denominator,
                    (matrix[2, 1] - matrix[1, 2]) / denominator,
                ]
            )
        elif index == 1:
            quaternion = np.asarray(
                [
                    (matrix[0, 1] + matrix[1, 0]) / denominator,
                    root,
                    (matrix[1, 2] + matrix[2, 1]) / denominator,
                    (matrix[0, 2] - matrix[2, 0]) / denominator,
                ]
            )
        elif index == 2:
            quaternion = np.asarray(
                [
                    (matrix[0, 2] + matrix[2, 0]) / denominator,
                    (matrix[1, 2] + matrix[2, 1]) / denominator,
                    root,
                    (matrix[1, 0] - matrix[0, 1]) / denominator,
                ]
            )
        else:
            quaternion = np.asarray(
                [
                    (matrix[2, 1] - matrix[1, 2]) / denominator,
                    (matrix[0, 2] - matrix[2, 0]) / denominator,
                    (matrix[1, 0] - matrix[0, 1]) / denominator,
                    root,
                ]
            )
        if quaternion[3] < 0.0:
            quaternion = -quaternion
        return quaternion / np.linalg.norm(quaternion)


@dataclass(frozen=True, slots=True)
class SE3RelativeActionTransform:
    """用直接 NumPy SE(3) 数学执行绝对/相对末端位姿双向转换。"""

    action_feature: str = "actions"
    state_feature: str = "reference_state"
    action_translation_indices: tuple[int, int, int] = (0, 1, 2)
    action_rotation_indices: tuple[int, ...] = (3, 4, 5)
    state_translation_indices: tuple[int, int, int] = (0, 1, 2)
    state_rotation_indices: tuple[int, ...] = (3, 4, 5)
    pose_representation: PoseRepresentation = PoseRepresentation.TRANSLATION_ROTATION
    rotation_representation: RotationRepresentation = RotationRepresentation.AXIS_ANGLE
    translation_axes: TranslationAxes = TranslationAxes.XYZ
    frame_convention: SE3FrameConvention = SE3FrameConvention.REFERENCE_LOCAL
    current_state_reference: CurrentStateReference = CurrentStateReference.EXPLICIT_FEATURE
    temporal_alignment: SE3TemporalAlignment = SE3TemporalAlignment.CURRENT_STATE_TO_ALL_ACTIONS
    valid_dimension_mask: tuple[bool, ...] = (True, True, True, True, True, True)
    mask_feature: str | None = None
    dtype: Literal["float32", "float64"] = "float32"
    parameters: tuple[SE3TypedParameter, ...] = ()
    provenance: str = "autovla_contract_reimplementation"
    implementation_version: str = "1"
    tolerances: SE3Tolerances = DEFAULT_SE3_TOLERANCES
    name: str = "se3_relative_action"
    execution_side: ExecutionSide = ExecutionSide.DATA
    stage_id: str = ""

    def __post_init__(self) -> None:
        """关闭索引、表示、mask、来源和参数身份。"""

        if (
            type(self.pose_representation) is not PoseRepresentation
            or type(self.rotation_representation) is not RotationRepresentation
            or type(self.translation_axes) is not TranslationAxes
            or type(self.frame_convention) is not SE3FrameConvention
            or type(self.current_state_reference) is not CurrentStateReference
            or type(self.temporal_alignment) is not SE3TemporalAlignment
        ):
            raise TypeError("SE3 semantic policies must use their closed enum types")
        if self.current_state_reference is not CurrentStateReference.EXPLICIT_FEATURE:
            raise ValueError("SE3 current state reference supports only explicit_feature")
        if self.dtype not in {"float32", "float64"}:
            raise ValueError("SE3 dtype must be float32 or float64")
        if (
            not self.action_feature.strip()
            or not self.state_feature.strip()
            or not self.name.strip()
        ):
            raise ValueError("SE3 feature and stage identities must not be empty")
        if self.mask_feature is not None and not self.mask_feature.strip():
            raise ValueError("SE3 mask feature must not be empty")
        if any(type(value) is not bool for value in self.valid_dimension_mask):
            raise TypeError("SE3 valid-dimension mask must contain exact bool values")
        if type(self.parameters) is not tuple or any(
            type(item) is not SE3TypedParameter for item in self.parameters
        ):
            raise TypeError("SE3 parameters must be a tuple of SE3TypedParameter")
        if type(self.tolerances) is not SE3Tolerances:
            raise TypeError("SE3 tolerances must use SE3Tolerances")
        rotation_size = (
            3 if self.rotation_representation is RotationRepresentation.AXIS_ANGLE else 4
        )
        if (
            len(self.action_rotation_indices) != rotation_size
            or len(self.state_rotation_indices) != rotation_size
        ):
            raise ValueError("SE3 rotation indices do not match rotation representation")
        groups = (
            self.action_translation_indices,
            self.action_rotation_indices,
            self.state_translation_indices,
            self.state_rotation_indices,
        )
        if any(
            len(set(group)) != len(group)
            or any(type(index) is not int or index < 0 for index in group)
            for group in groups
        ):
            raise ValueError("SE3 index groups must contain unique non-negative integers")
        if set(self.action_translation_indices) & set(self.action_rotation_indices):
            raise ValueError("SE3 action translation and rotation indices must be disjoint")
        if set(self.state_translation_indices) & set(self.state_rotation_indices):
            raise ValueError("SE3 state translation and rotation indices must be disjoint")
        selected = self.action_translation_indices + self.action_rotation_indices
        if not self.valid_dimension_mask or max(selected) >= len(self.valid_dimension_mask):
            raise ValueError("SE3 valid-dimension mask does not cover selected action dimensions")
        if any(not self.valid_dimension_mask[index] for index in selected):
            raise ValueError("SE3 selected action dimensions must be statically valid")
        if not self.provenance.strip() or not self.implementation_version.strip():
            raise ValueError("SE3 provenance and implementation version must not be empty")
        names = tuple(item.name for item in self.parameters)
        if len(set(names)) != len(names):
            raise ValueError("SE3 typed parameter names must be unique")
        _normalize_stage_id(self)

    @property
    def descriptor(self) -> StageDescriptor:
        """声明位姿、参考状态和可选动态 mask 依赖。"""

        required = [
            FeatureContract(self.action_feature, TensorLayout.time_feature()),
            FeatureContract(self.state_feature, TensorLayout.feature()),
        ]
        mask_behavior = ("consume:action_dimension:true_is_valid",)
        if self.mask_feature is not None:
            required.append(FeatureContract(self.mask_feature, TensorLayout.time_feature()))
        return StageDescriptor(
            tuple(required),
            (FeatureContract(self.action_feature, TensorLayout.time_feature()),),
            reversible=True,
            state_dependencies=(self.state_feature,),
            mask_behavior=mask_behavior,
            execution_side=self.execution_side,
        )

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """把绝对动作位姿转换到声明的参考坐标系。"""

        return self._convert(features, inverse=False)

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """把相对动作位姿恢复为绝对位姿。"""

        return self._convert(features, inverse=True)

    def _convert(self, features: FeatureMap, *, inverse: bool) -> dict[str, object]:
        """逐时间步执行 SE(3) 组合, 保留未选择动作维度。"""

        dtype = np.dtype(self.dtype)
        actions = np.array(_numeric(features, self.action_feature), dtype=dtype, copy=True)
        state = np.asarray(_numeric(features, self.state_feature), dtype=dtype)
        if actions.ndim != 2 or state.ndim != 1 or actions.shape[0] <= 0:
            raise ValueError("SE3 transform requires actions [T,D] and reference state [S]")
        if max(self.action_translation_indices + self.action_rotation_indices) >= actions.shape[1]:
            raise ValueError("SE3 action indices exceed the action dimension")
        if max(self.state_translation_indices + self.state_rotation_indices) >= state.shape[0]:
            raise ValueError("SE3 state indices exceed the state dimension")
        valid_rows = self._runtime_pose_validity(features, actions.shape)
        codec = SE3RotationCodec(self.tolerances)
        reference_translation = state[list(self.state_translation_indices)]
        reference_rotation = codec.to_matrix(
            state[list(self.state_rotation_indices)], self.rotation_representation
        )
        for index in np.flatnonzero(valid_rows):
            translation = actions[index, list(self.action_translation_indices)]
            rotation = codec.to_matrix(
                actions[index, list(self.action_rotation_indices)],
                self.rotation_representation,
            )
            if inverse:
                absolute_translation, absolute_rotation = _compose_absolute_pose(
                    translation,
                    rotation,
                    reference_translation,
                    reference_rotation,
                    self.frame_convention,
                )
                output_translation, output_rotation = absolute_translation, absolute_rotation
            else:
                relative_translation, relative_rotation = _compose_relative_pose(
                    translation,
                    rotation,
                    reference_translation,
                    reference_rotation,
                    self.frame_convention,
                )
                output_translation, output_rotation = relative_translation, relative_rotation
            actions[index, list(self.action_translation_indices)] = output_translation
            actions[index, list(self.action_rotation_indices)] = codec.from_matrix(
                output_rotation, self.rotation_representation
            )
        if not bool(np.isfinite(actions).all()):
            raise ValueError("SE3 transform produced non-finite actions")
        output = _copy(features)
        output[self.action_feature] = actions
        return output

    def _runtime_pose_validity(
        self,
        features: FeatureMap,
        action_shape: tuple[int, ...],
    ) -> NDArray[np.bool_]:
        """返回全有效位姿行,全无效行保持值与掩码不变。"""

        if self.mask_feature is None:
            return np.ones(action_shape[0], dtype=np.bool_)
        value = features.get(self.mask_feature)
        if not isinstance(value, SemanticMask) or value.values.shape != action_shape:
            raise TypeError("SE3 mask must be a same-shape SemanticMask")
        selected = self.action_translation_indices + self.action_rotation_indices
        return closed_pose_row_validity(
            value.values[:, list(selected)],
            context="SE3 pose dimensions",
        )

    def to_json_dict(self) -> dict[str, object]:
        """绑定全部数学、布局、mask、来源、参数和容限元数据。"""

        return {
            "name": self.name,
            "stage_id": self.stage_id,
            "implementation_version": self.implementation_version,
            "action_feature": self.action_feature,
            "state_feature": self.state_feature,
            "action_translation_indices": list(self.action_translation_indices),
            "action_rotation_indices": list(self.action_rotation_indices),
            "state_translation_indices": list(self.state_translation_indices),
            "state_rotation_indices": list(self.state_rotation_indices),
            "pose_representation": self.pose_representation.value,
            "rotation_representation": self.rotation_representation.value,
            "translation_axes": self.translation_axes.value,
            "frame_convention": self.frame_convention.value,
            "current_state_reference": self.current_state_reference.value,
            "direction": "forward_relative_inverse_absolute",
            "valid_dimension_mask": list(self.valid_dimension_mask),
            "mask_feature": self.mask_feature,
            "temporal_alignment": self.temporal_alignment.value,
            "dtype": self.dtype,
            "parameters": [item.to_json_dict() for item in self.parameters],
            "provenance": self.provenance,
            "tolerances": self.tolerances.to_json_dict(),
            "descriptor": self.descriptor.to_json_dict(),
        }


def _skew(vector: NDArray[np.generic]) -> NDArray[np.float64]:
    """构造三维向量的反对称矩阵。"""

    x, y, z = np.asarray(vector, dtype=np.float64)
    return np.asarray([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])


def _compose_relative_pose(
    translation: NDArray[np.generic],
    rotation: NDArray[np.generic],
    reference_translation: NDArray[np.generic],
    reference_rotation: NDArray[np.generic],
    convention: SE3FrameConvention,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """执行 ``reference^-1 * action`` 或世界坐标差分。"""

    translation64 = np.asarray(translation, dtype=np.float64)
    rotation64 = np.asarray(rotation, dtype=np.float64)
    reference_translation64 = np.asarray(reference_translation, dtype=np.float64)
    reference_rotation64 = np.asarray(reference_rotation, dtype=np.float64)
    reference_rotation_transpose = np.asarray(
        np.transpose(reference_rotation64),
        dtype=np.float64,
    )
    if convention is SE3FrameConvention.REFERENCE_LOCAL:
        relative_translation = np.asarray(
            reference_rotation_transpose @ (translation64 - reference_translation64),
            dtype=np.float64,
        )
        relative_rotation = np.asarray(
            reference_rotation_transpose @ rotation64,
            dtype=np.float64,
        )
        return relative_translation, relative_rotation
    relative_translation = np.asarray(
        translation64 - reference_translation64,
        dtype=np.float64,
    )
    relative_rotation = np.asarray(
        rotation64 @ reference_rotation_transpose,
        dtype=np.float64,
    )
    return relative_translation, relative_rotation


def _compose_absolute_pose(
    translation: NDArray[np.generic],
    rotation: NDArray[np.generic],
    reference_translation: NDArray[np.generic],
    reference_rotation: NDArray[np.generic],
    convention: SE3FrameConvention,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """逆转相对位姿组合并恢复世界绝对位姿。"""

    translation64 = np.asarray(translation, dtype=np.float64)
    rotation64 = np.asarray(rotation, dtype=np.float64)
    reference_translation64 = np.asarray(reference_translation, dtype=np.float64)
    reference_rotation64 = np.asarray(reference_rotation, dtype=np.float64)
    if convention is SE3FrameConvention.REFERENCE_LOCAL:
        return (
            reference_translation64 + reference_rotation64 @ translation64,
            reference_rotation64 @ rotation64,
        )
    return (
        reference_translation64 + translation64,
        rotation64 @ reference_rotation64,
    )


# 两个公开名称保持同一实现, 避免形成第二套 SE(3) 引擎。
SE3RelativeActionStage = SE3RelativeActionTransform


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
    stage_id: str = ""

    def __post_init__(self) -> None:
        """规范化稳定阶段实例身份。"""

        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
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
    stage_id: str = ""

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
        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
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
    stage_id: str = ""

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
        _normalize_stage_id(self)

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
            "stage_id": self.stage_id,
            "implementation_version": self.implementation_version,
            "inputs": list(self.inputs),
            "output": self.output,
            "kind": self.kind.value,
            "operation": self.operation,
            "descriptor": self.descriptor.to_json_dict(),
        }


def _normalize_stage_id(
    stage: (
        FeatureRenameStage
        | TemporalAlignmentStage
        | RelativeActionStage
        | SE3RelativeActionTransform
        | NormalizeStage
        | PaddingStage
        | MaskCompositionStage
    ),
) -> None:
    """把兼容空值规范化为显式稳定实例身份。"""

    if not stage.name.strip():
        raise ValueError("transform stage type name must not be empty")
    if stage.stage_id and not stage.stage_id.strip():
        raise ValueError("transform stage identifier must not be blank")
    object.__setattr__(stage, "stage_id", stage.stage_id or stage.name)


__all__ = [
    "CurrentStateReference",
    "FeatureRenameStage",
    "MaskCompositionStage",
    "NormalizeStage",
    "PaddingStage",
    "PoseRepresentation",
    "RelativeActionStage",
    "RotationRepresentation",
    "SE3FrameConvention",
    "SE3RelativeActionStage",
    "SE3RelativeActionTransform",
    "SE3TemporalAlignment",
    "SE3Tolerances",
    "SE3TypedParameter",
    "SemanticMask",
    "TemporalAlignmentStage",
    "TranslationAxes",
]
