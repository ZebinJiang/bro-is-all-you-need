"""关节与末端执行器相对动作的类型化变换。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import torch
from torch.nn import functional as F


class RelativeActionKind(str, Enum):
    """区分关节加法与末端执行器 SE(3) 组合。"""

    JOINT = "joint"
    END_EFFECTOR = "end_effector"


class EndEffectorRepresentation(str, Enum):
    """声明末端执行器 pose 的扁平存储格式。"""

    HOMOGENEOUS = "default"
    XYZ_ROT6D = "xyz+rot6d"
    XYZ_ROTVEC = "xyz+rotvec"

    @property
    def dimension(self) -> int:
        """返回该 pose 格式的固定宽度。"""
        return {
            EndEffectorRepresentation.HOMOGENEOUS: 16,
            EndEffectorRepresentation.XYZ_ROT6D: 9,
            EndEffectorRepresentation.XYZ_ROTVEC: 6,
        }[self]


@dataclass(frozen=True, slots=True)
class RelativeActionPolicy:
    """描述一个动作切片相对于状态切片的变换策略。

    关节策略执行逐维减法/加法。末端执行器策略把 pose 转为齐次矩阵,
    训练时计算 ``T_ref^-1 @ T_action``,解码时计算
    ``T_ref @ T_relative``。
    """

    kind: RelativeActionKind
    action_start: int
    state_start: int
    dimension: int
    representation: EndEffectorRepresentation | None = None

    def __post_init__(self) -> None:
        """校验切片和 pose 表示的一致性。"""
        if self.action_start < 0 or self.state_start < 0 or self.dimension <= 0:
            raise ValueError("relative action slices must be non-negative and non-empty")
        if self.kind is RelativeActionKind.JOINT:
            if self.representation is not None:
                raise ValueError("joint relative action must not declare an EEF representation")
        elif self.kind is RelativeActionKind.END_EFFECTOR:
            if self.representation is None:
                raise ValueError("end-effector relative action requires a representation")
            if self.dimension != self.representation.dimension:
                raise ValueError("end-effector dimension does not match representation")
        else:
            raise ValueError(f"unsupported relative action kind: {self.kind}")

    @property
    def action_stop(self) -> int:
        """返回动作切片右边界。"""
        return self.action_start + self.dimension

    @property
    def state_stop(self) -> int:
        """返回状态切片右边界。"""
        return self.state_start + self.dimension

    def to_relative(self, actions: torch.Tensor, reference_state: torch.Tensor) -> torch.Tensor:
        """把 ``[...,H,D]`` 绝对动作转换为相对动作。"""
        self._validate_inputs(actions, reference_state)
        output = actions.clone()
        action_slice = output[..., self.action_start : self.action_stop]
        reference = reference_state[..., self.state_start : self.state_stop]
        if self.kind is RelativeActionKind.JOINT:
            output[..., self.action_start : self.action_stop] = action_slice - reference.unsqueeze(
                -2
            )
            return output
        if self.representation is None:
            raise RuntimeError("validated EEF policy lacks representation")
        action_poses = _decode_pose(action_slice, self.representation)
        reference_pose = _decode_pose(reference, self.representation)
        relative = _invert_pose(reference_pose).unsqueeze(-3) @ action_poses
        output[..., self.action_start : self.action_stop] = _encode_pose(
            relative,
            self.representation,
        )
        return output

    def to_absolute(self, actions: torch.Tensor, reference_state: torch.Tensor) -> torch.Tensor:
        """在反归一化后重建绝对关节或末端执行器动作。"""
        self._validate_inputs(actions, reference_state)
        output = actions.clone()
        action_slice = output[..., self.action_start : self.action_stop]
        reference = reference_state[..., self.state_start : self.state_stop]
        if self.kind is RelativeActionKind.JOINT:
            output[..., self.action_start : self.action_stop] = action_slice + reference.unsqueeze(
                -2
            )
            return output
        if self.representation is None:
            raise RuntimeError("validated EEF policy lacks representation")
        relative_poses = _decode_pose(action_slice, self.representation)
        reference_pose = _decode_pose(reference, self.representation)
        absolute = reference_pose.unsqueeze(-3) @ relative_poses
        output[..., self.action_start : self.action_stop] = _encode_pose(
            absolute,
            self.representation,
        )
        return output

    def _validate_inputs(self, actions: torch.Tensor, reference_state: torch.Tensor) -> None:
        """校验动作 horizon 和参考状态切片均存在。"""
        if actions.ndim < 2 or reference_state.ndim != actions.ndim - 1:
            raise ValueError("actions must be [...,H,D] and reference_state must be [...,D]")
        if actions.shape[:-2] != reference_state.shape[:-1]:
            raise ValueError("action and reference batch dimensions must match")
        if self.action_stop > actions.shape[-1] or self.state_stop > reference_state.shape[-1]:
            raise ValueError("relative action policy slice exceeds tensor dimension")


def _decode_pose(values: torch.Tensor, representation: EndEffectorRepresentation) -> torch.Tensor:
    """把扁平 pose 转换为 ``[...,4,4]`` 齐次矩阵。"""
    if values.shape[-1] != representation.dimension:
        raise ValueError("pose width does not match representation")
    if representation is EndEffectorRepresentation.HOMOGENEOUS:
        pose = values.reshape(*values.shape[:-1], 4, 4)
        _validate_homogeneous(pose)
        return pose
    pose = torch.zeros((*values.shape[:-1], 4, 4), dtype=values.dtype, device=values.device)
    pose[..., 3, 3] = 1
    pose[..., :3, 3] = values[..., :3]
    if representation is EndEffectorRepresentation.XYZ_ROT6D:
        pose[..., :3, :3] = _rot6d_to_matrix(values[..., 3:])
    else:
        pose[..., :3, :3] = _rotvec_to_matrix(values[..., 3:])
    return pose


def _encode_pose(pose: torch.Tensor, representation: EndEffectorRepresentation) -> torch.Tensor:
    """把齐次矩阵转换回声明的扁平 pose 格式。"""
    _validate_homogeneous(pose)
    if representation is EndEffectorRepresentation.HOMOGENEOUS:
        return pose.flatten(start_dim=-2)
    translation = pose[..., :3, 3]
    rotation = pose[..., :3, :3]
    if representation is EndEffectorRepresentation.XYZ_ROT6D:
        encoded_rotation = rotation[..., :2, :].flatten(start_dim=-2)
    else:
        encoded_rotation = _matrix_to_rotvec(rotation)
    return torch.cat((translation, encoded_rotation), dim=-1)


def _invert_pose(pose: torch.Tensor) -> torch.Tensor:
    """利用旋转正交性求齐次变换逆。"""
    rotation = pose[..., :3, :3]
    translation = pose[..., :3, 3]
    inverse = torch.zeros_like(pose)
    inverse[..., :3, :3] = rotation.transpose(-1, -2)
    inverse[..., :3, 3] = -(rotation.transpose(-1, -2) @ translation.unsqueeze(-1)).squeeze(-1)
    inverse[..., 3, 3] = 1
    return inverse


def _rot6d_to_matrix(values: torch.Tensor) -> torch.Tensor:
    """按 pinned 源码的前两行 Gram-Schmidt 规则恢复旋转矩阵。"""
    rows = values.reshape(*values.shape[:-1], 2, 3)
    first = F.normalize(rows[..., 0, :], dim=-1)
    second = rows[..., 1, :] - (first * rows[..., 1, :]).sum(dim=-1, keepdim=True) * first
    second = F.normalize(second, dim=-1)
    third = torch.cross(first, second, dim=-1)
    return torch.stack((first, second, third), dim=-2)


def _rotvec_to_matrix(values: torch.Tensor) -> torch.Tensor:
    """使用 Rodrigues 公式把旋转向量转换为矩阵。"""
    angle = torch.sqrt(torch.sum(values * values, dim=-1, keepdim=True))
    axis = values / torch.clamp_min(angle, torch.finfo(values.dtype).eps)
    skew = _skew(axis)
    identity = torch.eye(3, dtype=values.dtype, device=values.device).expand(
        *values.shape[:-1], 3, 3
    )
    sine = torch.unsqueeze(torch.sin(angle), -1)
    cosine = torch.unsqueeze(torch.cos(angle), -1)
    matrix = identity + sine * skew + (1 - cosine) * (skew @ skew)
    small = torch.unsqueeze(torch.unsqueeze(torch.squeeze(angle, -1) < 1e-7, -1), -1)
    return torch.where(small, identity + _skew(values), matrix)


def _matrix_to_rotvec(matrix: torch.Tensor) -> torch.Tensor:
    """把旋转矩阵转换为稳定的轴角旋转向量。"""
    flat = matrix.reshape(-1, 3, 3)
    outputs: list[torch.Tensor] = []
    for rotation in flat:
        cosine = ((torch.trace(rotation) - 1) / 2).clamp(-1, 1)
        angle = torch.acos(cosine)
        skew_vector = torch.stack(
            (
                rotation[2, 1] - rotation[1, 2],
                rotation[0, 2] - rotation[2, 0],
                rotation[1, 0] - rotation[0, 1],
            )
        )
        if bool(angle < 1e-7):
            outputs.append(skew_vector / 2)
        elif bool(torch.pi - angle < 1e-5):
            diagonal = torch.diagonal(rotation)
            dominant = int(torch.argmax(diagonal))
            axis = torch.zeros(3, dtype=rotation.dtype, device=rotation.device)
            axis[dominant] = torch.sqrt(((diagonal[dominant] + 1) / 2).clamp_min(0))
            denominator = (4 * axis[dominant]).clamp_min(torch.finfo(rotation.dtype).eps)
            if dominant == 0:
                axis[1] = (rotation[0, 1] + rotation[1, 0]) / denominator
                axis[2] = (rotation[0, 2] + rotation[2, 0]) / denominator
            elif dominant == 1:
                axis[0] = (rotation[0, 1] + rotation[1, 0]) / denominator
                axis[2] = (rotation[1, 2] + rotation[2, 1]) / denominator
            else:
                axis[0] = (rotation[0, 2] + rotation[2, 0]) / denominator
                axis[1] = (rotation[1, 2] + rotation[2, 1]) / denominator
            outputs.append(F.normalize(axis, dim=0) * angle)
        else:
            outputs.append(skew_vector * (angle / (2 * torch.sin(angle))))
    return torch.stack(outputs).reshape(*matrix.shape[:-2], 3)


def _skew(values: torch.Tensor) -> torch.Tensor:
    """构造向量的反对称叉乘矩阵。"""
    x, y, z = values.unbind(dim=-1)
    zero = torch.zeros_like(x)
    return torch.stack((zero, -z, y, z, zero, -x, -y, x, zero), dim=-1).reshape(
        *values.shape[:-1], 3, 3
    )


def _validate_homogeneous(pose: torch.Tensor) -> None:
    """校验齐次形状、最后一行和旋转正交性。"""
    if pose.shape[-2:] != (4, 4):
        raise ValueError("homogeneous pose must have shape [...,4,4]")
    expected_row = torch.tensor((0, 0, 0, 1), dtype=pose.dtype, device=pose.device)
    if not bool(
        torch.allclose(pose[..., 3, :], expected_row.expand_as(pose[..., 3, :]), atol=1e-4)
    ):
        raise ValueError("homogeneous pose last row must be [0,0,0,1]")
    rotation = pose[..., :3, :3]
    identity = torch.eye(3, dtype=pose.dtype, device=pose.device)
    if not bool(torch.allclose(rotation.transpose(-1, -2) @ rotation, identity, atol=1e-4)):
        raise ValueError("pose rotation must be orthonormal")
    if not bool(
        torch.allclose(torch.det(rotation), torch.ones_like(torch.det(rotation)), atol=1e-4)
    ):
        raise ValueError("pose rotation determinant must be one")


__all__ = [
    "EndEffectorRepresentation",
    "RelativeActionKind",
    "RelativeActionPolicy",
]
