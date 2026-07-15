"""N1.7 processor/modality/action_config 的纯契约投影。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import cast

import numpy as np
from numpy.typing import NDArray

from autovla.data.transforms import (
    ExecutionSide,
    RotationRepresentation,
    SE3FrameConvention,
    SE3RelativeActionTransform,
    SE3TypedParameter,
    TransformPlan,
)
from autovla.models.assembly import ModelAssemblyRequest
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config


class _ActionType(str, Enum):
    """区分末端位姿与普通动作。"""

    EEF = "eef"
    NON_EEF = "non_eef"


class _ActionRepresentation(str, Enum):
    """声明 artifact action_config 的物理表示。"""

    RELATIVE = "relative"
    ABSOLUTE = "absolute"


class _ActionFormat(str, Enum):
    """声明 processor 可投影的动作编码。"""

    XYZ_ROT6D = "xyz_rot6d"
    VECTOR = "vector"


@dataclass(frozen=True, slots=True)
class _ActionProjection:
    """保存一个动作切片及规范 SE(3) 投影元数据。"""

    key: str
    state_key: str
    action_type: _ActionType
    representation: _ActionRepresentation
    action_format: _ActionFormat
    source_indices: tuple[int, ...]
    canonical_pose_indices: tuple[int, int, int, int, int, int] | None = None
    state_pose_indices: tuple[int, int, int, int, int, int] | None = None

    def __post_init__(self) -> None:
        """拒绝不完整或越过 132 维 envelope 的投影。"""

        if not self.key.strip() or not self.state_key.strip():
            raise ValueError("action and state keys must not be empty")
        if not self.source_indices or len(set(self.source_indices)) != len(self.source_indices):
            raise ValueError("source action indices must be non-empty and unique")
        if any(
            type(index) is not int or index < 0 or index >= 132 for index in self.source_indices
        ):
            raise ValueError("source action indices must stay inside dimension 132")
        for field, indices in (
            ("canonical pose", self.canonical_pose_indices),
            ("state pose", self.state_pose_indices),
        ):
            if indices is not None and (
                len(set(indices)) != 6
                or any(type(index) is not int or index < 0 or index >= 132 for index in indices)
            ):
                raise ValueError(f"{field} indices must be unique inside dimension 132")
        relative_eef = (
            self.action_type is _ActionType.EEF
            and self.representation is _ActionRepresentation.RELATIVE
        )
        if relative_eef and (
            self.action_format is not _ActionFormat.XYZ_ROT6D
            or len(self.source_indices) != 9
            or self.canonical_pose_indices is None
            or self.state_pose_indices is None
        ):
            raise ValueError("relative EEF XYZ_ROT6D requires source and canonical pose indices")
        if not relative_eef and (
            self.canonical_pose_indices is not None or self.state_pose_indices is not None
        ):
            raise ValueError("only relative EEF actions may declare SE3 pose indices")


@dataclass(frozen=True, slots=True)
class _ProcessorProjection:
    """保存已关闭的有序 processor 投影。"""

    image_keys: tuple[str, ...]
    state_keys: tuple[str, ...]
    action_configs: tuple[_ActionProjection, ...]
    image_grid_thw: tuple[tuple[int, int, int], ...]
    left_padding: bool = True
    images_before_language: bool = True


def _enum_value(enum_type: type[Enum], value: object, field: str) -> Enum:
    """把 artifact 字符串收窄到封闭枚举。"""

    try:
        return enum_type(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"unsupported action_config {field}: {value!r}") from exc


class Gr00tN1d7Processor:
    """验证动态图像网格、132 维 padding/mask 和 action_config 投影。

    本类不导入 Qwen/Transformers 且不搬运 tensor。实际 tokenizer 和图像
    processor 必须由后续已许可的本地资产运行波次注入。
    """

    def __init__(self, config: Gr00tN1d7Config) -> None:
        """绑定 artifact 配置且不访问资产。"""

        if not isinstance(config, Gr00tN1d7Config):
            raise TypeError("processor requires Gr00tN1d7Config")
        self.config = config

    @classmethod
    def from_request(cls, request: ModelAssemblyRequest) -> Gr00tN1d7Processor:
        """实现共享组件工厂输入面。"""

        if request.family_key != "gr00t_n1d7" or not isinstance(request.config, Gr00tN1d7Config):
            raise TypeError("request must carry a GR00T N1.7 config")
        return cls(request.config)

    def project_contract(
        self,
        *,
        image_keys: Sequence[str],
        state_keys: Sequence[str],
        action_configs: Sequence[Mapping[str, object]],
        image_grid_thw: Sequence[Sequence[int]],
    ) -> _ProcessorProjection:
        """把本地 processor/modality JSON 投影为固定顺序契约。"""

        images = tuple(image_keys)
        states = tuple(state_keys)
        if not images or len(set(images)) != len(images) or any(not key.strip() for key in images):
            raise ValueError("image modality keys must be non-empty and unique")
        if not states or len(set(states)) != len(states) or any(not key.strip() for key in states):
            raise ValueError("state modality keys must be non-empty and unique")
        grids: list[tuple[int, int, int]] = []
        for raw_grid in image_grid_thw:
            grid = tuple(raw_grid)
            if len(grid) != 3 or any(type(value) is not int or value <= 0 for value in grid):
                raise ValueError("image_grid_thw entries must be positive [T,H,W] triples")
            grids.append((grid[0], grid[1], grid[2]))
        if len(grids) != len(images):
            raise ValueError("dynamic image grids must align with ordered image modalities")
        projections = tuple(self._project_action(item) for item in action_configs)
        occupied: set[int] = set()
        canonical_occupied: set[int] = set()
        for projection in projections:
            if occupied.intersection(projection.source_indices):
                raise ValueError("action_config slices must not overlap")
            occupied.update(projection.source_indices)
            canonical = projection.canonical_pose_indices
            if canonical is not None:
                if canonical_occupied.intersection(canonical):
                    raise ValueError("canonical action pose slices must not overlap")
                canonical_occupied.update(canonical)
        for projection in projections:
            canonical = set(projection.canonical_pose_indices or ())
            foreign_source = occupied.difference(projection.source_indices)
            if canonical.intersection(foreign_source):
                raise ValueError("canonical action pose must not overwrite another source slice")
        if not projections:
            raise ValueError("at least one action_config is required")
        return _ProcessorProjection(images, states, projections, tuple(grids))

    def transform_plan(self, projection: _ProcessorProjection) -> TransformPlan:
        """为相对 EEF 项生成唯一共享 TransformPlan/SE(3) 阶段。"""

        stages = []
        for action in projection.action_configs:
            if action.canonical_pose_indices is None or action.state_pose_indices is None:
                continue
            stages.append(
                SE3RelativeActionTransform(
                    action_feature="actions",
                    state_feature="reference_state",
                    action_translation_indices=action.canonical_pose_indices[:3],
                    action_rotation_indices=action.canonical_pose_indices[3:],
                    state_translation_indices=action.state_pose_indices[:3],
                    state_rotation_indices=action.state_pose_indices[3:],
                    rotation_representation=RotationRepresentation.AXIS_ANGLE,
                    frame_convention=SE3FrameConvention.REFERENCE_LOCAL,
                    valid_dimension_mask=(True,) * 132,
                    mask_feature="action_mask",
                    parameters=(
                        SE3TypedParameter("family", "gr00t_n1d7"),
                        SE3TypedParameter("action_config_key", action.key),
                        SE3TypedParameter("source_format", action.action_format.value),
                    ),
                    provenance="n1d7_action_config_projection_to_canonical_se3",
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                )
            )
        return TransformPlan(tuple(stages))

    def forward_action_projection(
        self,
        *,
        actions: NDArray[np.floating],
        action_mask: NDArray[np.bool_],
        projection: _ProcessorProjection,
    ) -> tuple[NDArray[np.floating], NDArray[np.bool_]]:
        """把 ``[40,132]`` 的 XYZ_ROT6D 源槽投影到规范轴角槽。

        ROT6D 按旋转矩阵前两行的顺序解释。正向投影只改写投影拥有的
        source/canonical 槽及其 mask，其他动作维度和 mask 保持逐位不变。
        """

        values, masks = self._validate_projection_arrays(actions, action_mask, projection)
        output = values.copy()
        output_mask = masks.copy()
        for item in projection.action_configs:
            if item.canonical_pose_indices is None:
                continue
            source = list(item.source_indices)
            canonical = list(item.canonical_pose_indices)
            valid = _closed_pose_validity(masks[:, source], item.key)
            output_mask[:, source] = False
            output_mask[:, canonical] = valid[:, None]
            for row in np.flatnonzero(valid):
                source_pose = values[row, source]
                rotation = _rot6d_to_matrix(source_pose[3:])
                output[row, canonical[:3]] = source_pose[:3]
                output[row, canonical[3:]] = _matrix_to_axis_angle(rotation)
        _require_finite_output(output)
        return output, output_mask

    def inverse_action_projection(
        self,
        *,
        actions: NDArray[np.floating],
        action_mask: NDArray[np.bool_],
        projection: _ProcessorProjection,
    ) -> tuple[NDArray[np.floating], NDArray[np.bool_]]:
        """把规范轴角槽逆投影为 ``[40,132]`` 的 XYZ_ROT6D 源槽。

        逆投影输出旋转矩阵的前两行，因此规范 SO(3) 行可稳定往返，其他
        非退化 ROT6D 输入会被确定性正交化；未拥有的维度和 mask 不变。
        """

        values, masks = self._validate_projection_arrays(actions, action_mask, projection)
        output = values.copy()
        output_mask = masks.copy()
        for item in projection.action_configs:
            if item.canonical_pose_indices is None:
                continue
            source = list(item.source_indices)
            canonical = list(item.canonical_pose_indices)
            valid = _closed_pose_validity(masks[:, canonical], item.key)
            output_mask[:, canonical] = False
            output_mask[:, source] = valid[:, None]
            for row in np.flatnonzero(valid):
                canonical_pose = values[row, canonical]
                rotation = _axis_angle_to_matrix(canonical_pose[3:])
                output[row, source[:3]] = canonical_pose[:3]
                output[row, source[3:]] = rotation[:2, :].reshape(6)
        _require_finite_output(output)
        return output, output_mask

    def _validate_projection_arrays(
        self,
        actions: NDArray[np.floating],
        action_mask: NDArray[np.bool_],
        projection: _ProcessorProjection,
    ) -> tuple[NDArray[np.floating], NDArray[np.bool_]]:
        """严格校验家族动作数组，不执行输入类型或精度隐式转换。"""

        if not isinstance(actions, np.ndarray) or not isinstance(action_mask, np.ndarray):
            raise TypeError("actions and action_mask must be NumPy arrays")
        if actions.dtype not in (np.dtype(np.float32), np.dtype(np.float64)):
            raise TypeError("actions dtype must be exactly float32 or float64")
        if action_mask.dtype != np.dtype(np.bool_):
            raise TypeError("action_mask dtype must be exactly bool")
        expected = (self.config.action_horizon, self.config.max_action_dim)
        if actions.shape != expected or action_mask.shape != expected:
            raise ValueError("N1.7 action projection requires actions and mask shaped [40,132]")
        if type(projection) is not _ProcessorProjection:
            raise TypeError("projection must be an N1.7 processor projection")
        if not bool(np.isfinite(actions).all()):
            raise ValueError("N1.7 action projection requires finite actions")
        return actions, action_mask

    @staticmethod
    def validate_padded_shapes(
        *,
        state_width: int,
        action_shape: tuple[int, int],
        state_mask_width: int,
        action_mask_shape: tuple[int, int],
    ) -> None:
        """关闭 state/action padding 与 mask 的 132/40 契约。"""

        if (state_width, action_shape, state_mask_width, action_mask_shape) != (
            132,
            (40, 132),
            132,
            (40, 132),
        ):
            raise ValueError("N1.7 padded state/action/mask shapes must be 132 and [40,132]")

    @staticmethod
    def _project_action(payload: Mapping[str, object]) -> _ActionProjection:
        """投影一个已解析的 action_config 记录。"""

        indices = payload.get("indices")
        if not isinstance(indices, Sequence) or isinstance(indices, (str, bytes)):
            raise ValueError("action_config indices must be a sequence")
        if any(type(index) is not int for index in indices):
            raise ValueError("action_config indices must contain exact integers")
        source_indices = cast(tuple[int, ...], tuple(indices))
        canonical = payload.get("canonical_pose_indices")
        state_pose = payload.get("state_pose_indices")
        canonical_indices = _pose_indices(canonical, "canonical_pose_indices")
        state_pose_indices = _pose_indices(state_pose, "state_pose_indices")
        return _ActionProjection(
            key=str(payload.get("key", "")),
            state_key=str(payload.get("state_key", "")),
            action_type=_enum_value(_ActionType, payload.get("type"), "type"),
            representation=_enum_value(
                _ActionRepresentation, payload.get("representation"), "representation"
            ),
            action_format=_enum_value(_ActionFormat, payload.get("format"), "format"),
            source_indices=source_indices,
            canonical_pose_indices=canonical_indices,
            state_pose_indices=state_pose_indices,
        )


def _pose_indices(
    value: object,
    field: str,
) -> tuple[int, int, int, int, int, int] | None:
    """把可选位姿索引关闭为六个精确整数。"""

    if value is None:
        return None
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{field} must be a six-index sequence")
    indices = tuple(value)
    if len(indices) != 6 or any(type(index) is not int for index in indices):
        raise ValueError(f"{field} must contain six exact integers")
    return cast(tuple[int, int, int, int, int, int], indices)


_ROT6D_DEGENERACY_EPS = 1e-8
_ROTATION_SMALL_ANGLE = 1e-8


def _closed_pose_validity(mask: NDArray[np.bool_], key: str) -> NDArray[np.bool_]:
    """要求一个 pose 在每个时间步全有效或全无效。"""

    all_valid = np.all(mask, axis=1)
    all_invalid = np.all(~mask, axis=1)
    if not bool(np.all(all_valid | all_invalid)):
        raise ValueError(f"action projection {key!r} requires closed pose masks")
    return np.asarray(all_valid, dtype=np.bool_)


def _rot6d_to_matrix(values: NDArray[np.floating]) -> NDArray[np.float64]:
    """用前两行 Gram-Schmidt 投影有限且非退化的 ROT6D。"""

    rows = np.asarray(values, dtype=np.float64).reshape(2, 3)
    first_norm = float(np.linalg.norm(rows[0]))
    if first_norm <= _ROT6D_DEGENERACY_EPS:
        raise ValueError("ROT6D first axis is degenerate")
    first = rows[0] / first_norm
    second_residual = rows[1] - float(np.dot(first, rows[1])) * first
    second_norm = float(np.linalg.norm(second_residual))
    if second_norm <= _ROT6D_DEGENERACY_EPS:
        raise ValueError("ROT6D axes are collinear or degenerate")
    second = second_residual / second_norm
    third = np.cross(first, second)
    return np.stack((first, second, third), axis=0)


def _axis_angle_to_matrix(values: NDArray[np.floating]) -> NDArray[np.float64]:
    """用 Rodrigues 公式把有限轴角向量转换为旋转矩阵。"""

    vector = np.asarray(values, dtype=np.float64)
    angle = float(np.linalg.norm(vector))
    skew = _skew(vector if angle <= _ROTATION_SMALL_ANGLE else vector / angle)
    if angle <= _ROTATION_SMALL_ANGLE:
        return np.eye(3, dtype=np.float64) + skew
    return (
        np.eye(3, dtype=np.float64) + np.sin(angle) * skew + (1.0 - np.cos(angle)) * (skew @ skew)
    )


def _matrix_to_axis_angle(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """经稳定 XYZW 四元数把 SO(3) 矩阵转换为主值轴角。"""

    quaternion = _matrix_to_quaternion_xyzw(matrix)
    vector = quaternion[:3]
    scalar = float(np.clip(quaternion[3], -1.0, 1.0))
    norm = float(np.linalg.norm(vector))
    if norm <= _ROTATION_SMALL_ANGLE:
        return 2.0 * vector
    angle = 2.0 * float(np.arctan2(norm, scalar))
    if angle > np.pi:
        angle -= 2.0 * np.pi
    return vector / norm * angle


def _matrix_to_quaternion_xyzw(matrix: NDArray[np.float64]) -> NDArray[np.float64]:
    """按最大对角分支稳定恢复单位 XYZW 四元数。"""

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
    if root <= _ROT6D_DEGENERACY_EPS:
        raise ValueError("ROT6D rotation matrix cannot form a stable quaternion")
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
    quaternion /= np.linalg.norm(quaternion)
    if quaternion[3] < 0.0:
        quaternion = -quaternion
    return quaternion


def _skew(values: NDArray[np.float64]) -> NDArray[np.float64]:
    """构造三维向量的反对称叉乘矩阵。"""

    x, y, z = values
    return np.asarray([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]], dtype=np.float64)


def _require_finite_output(actions: NDArray[np.floating]) -> None:
    """拒绝任何数值投影产生非有限动作。"""

    if not bool(np.isfinite(actions).all()):
        raise ValueError("N1.7 action projection produced non-finite actions")


def _build_processor(request: ModelAssemblyRequest) -> Gr00tN1d7Processor:
    """返回绑定共享请求的 processor 描述。"""

    return Gr00tN1d7Processor.from_request(request)


__all__ = ["Gr00tN1d7Processor"]
