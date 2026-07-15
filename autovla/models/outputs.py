"""AutoVLA 模型层类型化输入、输出与兼容性值对象。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import torch

from autovla.data.transforms import TransformPlan


def _empty_tensor_mapping() -> Mapping[str, torch.Tensor]:
    """返回空张量映射。"""
    return {}


def _empty_object_mapping() -> Mapping[str, object]:
    """返回空对象映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class ModelInputBatch:
    """保存处理器生成的 torch 模型输入。

    ``state`` 为 ``[B,T_state,D_state]``,训练动作和严格布尔掩码均为
    ``[B,H,D]``。图像张量按相机名保存,具体像素布局由模型族声明。
    """

    images: Mapping[str, torch.Tensor]
    input_ids: torch.Tensor
    attention_mask: torch.Tensor
    state: torch.Tensor
    embodiment_ids: torch.Tensor
    actions: torch.Tensor | None = None
    action_mask: torch.Tensor | None = None
    raw_state: torch.Tensor | None = None
    transform_plans: tuple[TransformPlan, ...] = ()
    physical_action_shapes: tuple[tuple[int, int], ...] = ()
    embodiments: tuple[str, ...] = ()
    camera_order: tuple[str, ...] = ()
    sample_source: tuple[Mapping[str, object], ...] = ()
    metadata: Mapping[str, object] = field(default_factory=_empty_object_mapping)

    def __post_init__(self) -> None:
        """校验 batch、形状和严格掩码不变量。"""
        if self.state.ndim != 3:
            raise ValueError("state must have shape [B,T,D]")
        batch_size = self.state.shape[0]
        if self.input_ids.ndim != 2 or self.input_ids.shape[0] != batch_size:
            raise ValueError("input_ids must have shape [B,L]")
        if self.attention_mask.shape != self.input_ids.shape:
            raise ValueError("attention_mask must match input_ids")
        if self.embodiment_ids.shape != (batch_size,):
            raise ValueError("embodiment_ids must have shape [B]")
        if self.embodiment_ids.dtype != torch.long:
            raise TypeError("embodiment_ids must use torch.long")
        if tuple(self.images) != self.camera_order:
            raise ValueError("images must follow camera_order exactly")
        for name, image in self.images.items():
            if image.shape[0] != batch_size:
                raise ValueError(f"image {name!r} must have batch dimension B")
        if (self.actions is None) != (self.action_mask is None):
            raise ValueError("actions and action_mask must be provided together")
        if self.actions is not None and self.action_mask is not None:
            if self.actions.ndim != 3 or self.actions.shape[0] != batch_size:
                raise ValueError("actions must have shape [B,H,D]")
            if self.action_mask.shape != self.actions.shape:
                raise ValueError("action_mask must match actions")
            if self.action_mask.dtype != torch.bool:
                raise TypeError("action_mask must be strict torch.bool")
        if self.raw_state is not None and self.raw_state.shape[0] != batch_size:
            raise ValueError("raw_state must have batch dimension B")
        if self.sample_source and len(self.sample_source) != batch_size:
            raise ValueError("sample_source length must match batch size")
        for name, values in (
            ("transform_plans", self.transform_plans),
            ("physical_action_shapes", self.physical_action_shapes),
            ("embodiments", self.embodiments),
        ):
            if values and len(values) != batch_size:
                raise ValueError(f"{name} length must match batch size")
        object.__setattr__(self, "images", MappingProxyType(dict(self.images)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def batch_size(self) -> int:
        """返回批大小。"""
        return int(self.state.shape[0])


@dataclass(frozen=True, slots=True)
class BackboneOutput:
    """保存骨干特征 ``[B,S,C]`` 与 token 掩码 ``[B,S]``。"""

    features: torch.Tensor
    attention_mask: torch.Tensor
    image_mask: torch.Tensor
    hidden_states: tuple[torch.Tensor, ...] = ()

    def __post_init__(self) -> None:
        """校验序列和严格布尔掩码。"""
        if self.features.ndim != 3:
            raise ValueError("features must have shape [B,S,C]")
        expected = self.features.shape[:2]
        if self.attention_mask.shape != expected or self.image_mask.shape != expected:
            raise ValueError("backbone masks must have shape [B,S]")
        if self.attention_mask.dtype != torch.bool or self.image_mask.dtype != torch.bool:
            raise TypeError("backbone masks must be strict torch.bool")


@dataclass(frozen=True, slots=True)
class ActionHeadOutput:
    """保存标量流匹配损失与逐元素 ``[B,H,D]`` 证据。"""

    loss: torch.Tensor
    elementwise_loss: torch.Tensor
    action_mask: torch.Tensor
    predicted_velocity: torch.Tensor
    target_velocity: torch.Tensor
    metrics: Mapping[str, torch.Tensor] = field(default_factory=_empty_tensor_mapping)

    def __post_init__(self) -> None:
        """校验损失和掩码形状。"""
        if self.loss.numel() != 1:
            raise ValueError("loss must be scalar")
        shape = self.elementwise_loss.shape
        if len(shape) != 3:
            raise ValueError("elementwise_loss must have shape [B,H,D]")
        if any(
            value.shape != shape
            for value in (self.action_mask, self.predicted_velocity, self.target_velocity)
        ):
            raise ValueError("action-head tensors must share [B,H,D] shape")
        if self.action_mask.dtype != torch.bool:
            raise TypeError("action_mask must be strict torch.bool")
        object.__setattr__(self, "metrics", MappingProxyType(dict(self.metrics)))


@dataclass(frozen=True, slots=True)
class ModelOutput:
    """保存组合模型训练输出。"""

    loss: torch.Tensor
    backbone: BackboneOutput
    action_head: ActionHeadOutput

    def __post_init__(self) -> None:
        """要求组合损失为标量。"""
        if self.loss.numel() != 1:
            raise ValueError("model loss must be scalar")


@dataclass(frozen=True, slots=True)
class ActionPrediction:
    """保存归一化动作及可选物理单位动作。"""

    normalized_actions: torch.Tensor
    action_mask: torch.Tensor
    decoded_actions: torch.Tensor | None = None

    def __post_init__(self) -> None:
        """校验动作形状和严格布尔掩码。"""
        if self.normalized_actions.ndim != 3:
            raise ValueError("normalized_actions must have shape [B,H,D]")
        if self.action_mask.shape != self.normalized_actions.shape:
            raise ValueError("action_mask must match normalized_actions")
        if self.action_mask.dtype != torch.bool:
            raise TypeError("action_mask must be strict torch.bool")
        if (
            self.decoded_actions is not None
            and self.decoded_actions.shape != self.normalized_actions.shape
        ):
            raise ValueError("decoded_actions must match normalized_actions")


@dataclass(frozen=True, slots=True)
class ModelCapabilitySpec:
    """声明模型族的静态能力和构造边界。"""

    family_key: str
    action_horizon: int
    max_state_dim: int
    max_action_dim: int
    supported_precisions: tuple[str, ...]
    local_files_only: bool
    processor_required: bool = True
    training_supported_by_source: bool = True


@dataclass(frozen=True, slots=True)
class CompatibilityIssue:
    """描述一个可操作的能力或 checkpoint 兼容性问题。"""

    code: str
    message: str
    fatal: bool = True


@dataclass(frozen=True, slots=True)
class CompatibilityResult:
    """汇总跨组件兼容性结论。"""

    compatible: bool
    issues: tuple[CompatibilityIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckpointCompatibilityReport:
    """描述本地 checkpoint 布局,不包含已加载张量。"""

    root: str
    weight_format: str | None
    weight_files: tuple[str, ...]
    required_files: tuple[str, ...]
    missing_files: tuple[str, ...]
    config_file: str | None
    processor_files: tuple[str, ...]
    provenance_file: str | None
    compatible: bool
    issues: tuple[CompatibilityIssue, ...] = ()


@dataclass(frozen=True, slots=True)
class CheckpointLoadReport:
    """保存本地权重映射和加载的完整结果。"""

    compatibility: CheckpointCompatibilityReport
    mapped_keys: tuple[str, ...]
    missing_keys: tuple[str, ...]
    unexpected_keys: tuple[str, ...]
    shape_mismatches: tuple[str, ...]
    strictness: str
    provenance: Mapping[str, object] = field(default_factory=_empty_object_mapping)

    def __post_init__(self) -> None:
        """冻结 provenance 映射。"""
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


__all__ = [
    "ActionHeadOutput",
    "ActionPrediction",
    "BackboneOutput",
    "CheckpointCompatibilityReport",
    "CheckpointLoadReport",
    "CompatibilityIssue",
    "CompatibilityResult",
    "ModelCapabilitySpec",
    "ModelInputBatch",
    "ModelOutput",
]
