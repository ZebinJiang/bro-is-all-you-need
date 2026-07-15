"""AutoVLA GR00T N1.6.1 不可变配置和 R3 变换计划。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType

import numpy as np

from autovla.assets import Gr00tModelAssetBundle
from autovla.core.semantics import (
    AlignmentMode,
    AlignmentPolicy,
    MaskKind,
    TensorLayout,
)
from autovla.data.normalization import ConstantFeaturePolicy, FeatureStatistics
from autovla.data.transforms import (
    ExecutionSide,
    MaskCompositionStage,
    NormalizeStage,
    PaddingStage,
    RelativeActionStage,
    ReversibleTransformStage,
    RotationRepresentation,
    SE3FrameConvention,
    SE3RelativeActionStage,
    SE3TypedParameter,
    TransformPlan,
)
from autovla.models.components.relative_actions import RelativeActionPolicy

PerHorizonFeatureStatistics = FeatureStatistics

_OFFICIAL_ARCHITECTURE = {
    "action_horizon": 50,
    "max_state_dim": 128,
    "max_action_dim": 128,
    "max_num_embodiments": 32,
    "backbone_embedding_dim": 2048,
    "retained_language_layers": 16,
    "action_hidden_size": 1024,
    "input_embedding_dim": 1536,
    "num_layers": 32,
    "num_attention_heads": 32,
    "attention_head_dim": 48,
    "num_inference_steps": 4,
    "num_timestep_buckets": 1000,
    "image_size": 448,
}


def _default_cameras() -> tuple[str, ...]:
    """返回官方相机顺序。"""

    return ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")


def _default_embodiments() -> Mapping[str, int]:
    """返回 pinned embodiment projector 映射。"""

    return {
        "oxe_google": 0,
        "oxe_widowx": 1,
        "libero_panda": 2,
        "unitree_g1": 8,
        "robocasa_panda_omron": 13,
        "gr1": 20,
        "behavior_r1_pro": 24,
    }


def _identity_statistics(
    dimension: int, *, layout: TensorLayout | None = None
) -> FeatureStatistics:
    """构造显式 identity 参数,不隐藏 epsilon。"""

    return FeatureStatistics(
        method="mean_std",
        layout=layout or TensorLayout.feature(dimension),
        mean=np.zeros((dimension,), dtype=np.float32),
        std=np.ones((dimension,), dtype=np.float32),
        constant_feature_policy=ConstantFeaturePolicy.IDENTITY,
        alignment=AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES),
    )


@dataclass(frozen=True, slots=True)
class EmbodimentStatistics:
    """绑定一个 embodiment 的 R3 统计量、顺序、策略与来源指纹。"""

    state: FeatureStatistics
    action: FeatureStatistics
    relative_action: FeatureStatistics | None = None
    relative_action_policies: tuple[RelativeActionPolicy, ...] = ()
    state_modality_order: tuple[str, ...] = ()
    action_modality_order: tuple[str, ...] = ()
    relative_action_modality_order: tuple[str, ...] = ()
    state_clip: bool = True
    action_clip: bool = True
    relative_action_clip: bool = True
    source_fingerprint: str = "unspecified"
    camera_order: tuple[str, ...] = ()
    sin_cos_state_slices: tuple[tuple[int, int], ...] = ()
    mean_std_state_modalities: tuple[str, ...] = ()
    mean_std_action_modalities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验轴、模态顺序、策略切片和来源身份。"""

        if self.state.layout.axes != TensorLayout.feature().axes:
            raise ValueError("state statistics must use explicit [D] layout")
        if self.action.layout.axes != TensorLayout.feature().axes:
            raise ValueError("action statistics must use explicit [D] layout")
        if self.relative_action is not None and (
            self.relative_action.layout.axes != TensorLayout.time_feature().axes
        ):
            raise ValueError("relative action statistics must preserve explicit [T,D] layout")
        for order in (
            self.state_modality_order,
            self.action_modality_order,
            self.relative_action_modality_order,
            self.camera_order,
            self.mean_std_state_modalities,
            self.mean_std_action_modalities,
        ):
            if len(order) != len(set(order)) or any(not item.strip() for item in order):
                raise ValueError("statistics modality order must be unique and non-empty")
        for start, stop in self.sin_cos_state_slices:
            if type(start) is not int or type(stop) is not int or start < 0 or stop <= start:
                raise ValueError("sin/cos state slices must be ordered non-negative ranges")
        if not self.source_fingerprint.strip():
            raise ValueError("statistics source_fingerprint must not be empty")

    @property
    def fingerprint(self) -> str:
        """把统计、顺序、裁剪和来源合并为稳定摘要。"""

        payload = {
            "state": self.state.fingerprint,
            "action": self.action.fingerprint,
            "relative_action": (
                None if self.relative_action is None else self.relative_action.fingerprint
            ),
            "state_modality_order": self.state_modality_order,
            "action_modality_order": self.action_modality_order,
            "relative_action_modality_order": self.relative_action_modality_order,
            "state_clip": self.state_clip,
            "action_clip": self.action_clip,
            "relative_action_clip": self.relative_action_clip,
            "source_fingerprint": self.source_fingerprint,
            "camera_order": self.camera_order,
            "sin_cos_state_slices": self.sin_cos_state_slices,
            "mean_std_state_modalities": self.mean_std_state_modalities,
            "mean_std_action_modalities": self.mean_std_action_modalities,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def _empty_statistics() -> Mapping[str, EmbodimentStatistics]:
    """返回空统计映射。"""

    return {}


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Config:
    """描述 pinned 50/128/128 官方 envelope、资产和 processor 行为。"""

    family_key: str = "gr00t_n1d6"
    architecture_variant: str = "official_n1d6"
    action_horizon: int = 50
    max_state_dim: int = 128
    max_action_dim: int = 128
    max_num_embodiments: int = 32
    backbone_embedding_dim: int = 2048
    retained_language_layers: int = 16
    action_hidden_size: int = 1024
    input_embedding_dim: int = 1536
    num_layers: int = 32
    num_attention_heads: int = 32
    attention_head_dim: int = 48
    attention_dropout: float = 0.2
    attend_text_every_n_blocks: int = 2
    num_inference_steps: int = 4
    noise_beta_alpha: float = 1.5
    noise_beta_beta: float = 1.0
    noise_time_scale: float = 0.999
    num_timestep_buckets: int = 1000
    camera_order: tuple[str, ...] = field(default_factory=_default_cameras)
    embodiment_ids: Mapping[str, int] = field(default_factory=_default_embodiments)
    statistics: Mapping[str, EmbodimentStatistics] = field(default_factory=_empty_statistics)
    use_relative_actions: bool = False
    formalize_language: bool = True
    image_size: int = 448
    random_crop_scale: tuple[float, float] = (0.95, 1.0)
    color_jitter: tuple[float, float, float, float] | None = None
    tune_backbone: bool = False
    tune_llm: bool = False
    tune_visual: bool = False
    tune_top_llm_layers: int = 4
    tune_action_head: bool = True
    tune_projector: bool = True
    tune_diffusion_model: bool = True
    tune_vlln: bool = True
    trainable_parameters_fp32: bool = True
    state_dropout_probability: float = 0.0
    state_noise_scale: float = 0.0
    asset_bundle: Gr00tModelAssetBundle | None = field(default=None, repr=False, compare=False)
    checkpoint_path: str | None = None
    eagle_asset_path: str | None = None
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """校验官方/缩小架构、资产和 tune 策略。"""

        if self.family_key != "gr00t_n1d6":
            raise ValueError("family_key must be gr00t_n1d6")
        if self.architecture_variant not in {"official_n1d6", "reduced_runtime"}:
            raise ValueError("unsupported GR00T architecture_variant")
        if self.architecture_variant == "official_n1d6":
            mismatches = tuple(
                name
                for name, expected in _OFFICIAL_ARCHITECTURE.items()
                if getattr(self, name) != expected
            )
            if mismatches:
                raise ValueError(f"official_n1d6 pinned architecture mismatch: {mismatches}")
        elif (
            self.action_horizon,
            self.max_state_dim,
            self.max_action_dim,
            self.backbone_embedding_dim,
            self.action_hidden_size,
            self.input_embedding_dim,
            self.num_layers,
            self.num_attention_heads,
            self.attention_head_dim,
            self.image_size,
            len(self.camera_order),
        ) != (16, 8, 8, 64, 64, 64, 2, 4, 16, 32, 1):
            raise ValueError("reduced_runtime dimensions must match the bounded contract")
        if self.input_embedding_dim != self.num_attention_heads * self.attention_head_dim:
            raise ValueError("input_embedding_dim must equal heads * head_dim")
        if self.num_inference_steps != 4:
            raise ValueError("GR00T requires exactly four Euler steps")
        if not self.local_files_only:
            raise ValueError("GR00T assets must remain local_files_only")
        if self.asset_bundle is not None:
            if self.checkpoint_path not in {None, str(self.asset_bundle.base_checkpoint.root)}:
                raise ValueError("checkpoint_path conflicts with verified asset bundle")
            if self.eagle_asset_path not in {None, str(self.asset_bundle.eagle_root)}:
                raise ValueError("eagle_asset_path conflicts with verified asset bundle")
            object.__setattr__(self, "checkpoint_path", str(self.asset_bundle.base_checkpoint.root))
            object.__setattr__(self, "eagle_asset_path", str(self.asset_bundle.eagle_root))
        if (
            self.architecture_variant == "official_n1d6"
            and self.asset_bundle is None
            and (self.checkpoint_path is not None or self.eagle_asset_path is not None)
        ):
            raise ValueError("official paths cannot bypass the typed GR00T asset bundle")
        if not self.camera_order or len(set(self.camera_order)) != len(self.camera_order):
            raise ValueError("camera_order must be non-empty and unique")
        if self.max_num_embodiments != 32 or self.state_dropout_probability < 0:
            raise ValueError("invalid embodiment bank or state dropout")
        if self.tune_top_llm_layers < 0 or self.state_noise_scale < 0:
            raise ValueError("tune layers and state noise must be non-negative")
        object.__setattr__(self, "embodiment_ids", MappingProxyType(dict(self.embodiment_ids)))
        object.__setattr__(self, "statistics", MappingProxyType(dict(self.statistics)))

    @property
    def fingerprint(self) -> str:
        """返回架构、统计、策略和资产身份的稳定摘要。"""

        payload = {
            "family_key": self.family_key,
            "architecture_variant": self.architecture_variant,
            "architecture": {name: getattr(self, name) for name in sorted(_OFFICIAL_ARCHITECTURE)},
            "camera_order": self.camera_order,
            "embodiment_ids": dict(sorted(self.embodiment_ids.items())),
            "statistics": {
                name: statistics.fingerprint for name, statistics in sorted(self.statistics.items())
            },
            "use_relative_actions": self.use_relative_actions,
            "formalize_language": self.formalize_language,
            "random_crop_scale": self.random_crop_scale,
            "color_jitter": self.color_jitter,
            "tuning": {
                "backbone": self.tune_backbone,
                "llm": self.tune_llm,
                "visual": self.tune_visual,
                "top_llm_layers": self.tune_top_llm_layers,
                "action_head": self.tune_action_head,
                "projector": self.tune_projector,
                "diffusion_model": self.tune_diffusion_model,
                "vlln": self.tune_vlln,
                "trainable_parameters_fp32": self.trainable_parameters_fp32,
            },
            "state_dropout_probability": self.state_dropout_probability,
            "state_noise_scale": self.state_noise_scale,
            "asset_bundle": None if self.asset_bundle is None else self.asset_bundle.fingerprint,
            "local_files_only": self.local_files_only,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def transform_plan(
        self,
        embodiment: str,
        *,
        state_shape: tuple[int, int],
        action_shape: tuple[int, int],
    ) -> TransformPlan:
        """构造归一化、相对动作、padding 和 mask 组合的共享 R3 计划。"""

        statistics = self.statistics[embodiment]
        state_time, state_dim = state_shape
        action_time, action_dim = action_shape
        if statistics.state.dimension != state_dim or statistics.action.dimension != action_dim:
            raise ValueError("statistics dimensions must exactly match physical features")
        stages: list[ReversibleTransformStage] = []
        joint_policies = tuple(
            policy for policy in statistics.relative_action_policies if policy.kind.value == "joint"
        )
        if self.use_relative_actions and joint_policies:
            action_dimensions: list[int] = []
            state_indices: list[int] = []
            for policy in joint_policies:
                action_dimensions.extend(range(policy.action_start, policy.action_stop))
                state_indices.extend(range(policy.state_start, policy.state_stop))
            stages.append(
                RelativeActionStage(
                    state_feature="reference_state",
                    action_dimensions=tuple(action_dimensions),
                    state_indices=tuple(state_indices),
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                )
            )
        eef_policies = tuple(
            policy
            for policy in statistics.relative_action_policies
            if policy.kind.value == "end_effector"
        )
        if self.use_relative_actions:
            for index, policy in enumerate(eef_policies):
                if policy.representation is None or policy.representation.value != "xyz+rotvec":
                    raise ValueError(
                        "canonical SE3 stage supports official EEF xyz_rotvec policies only"
                    )
                stages.append(
                    SE3RelativeActionStage(
                        action_translation_indices=(
                            policy.action_start,
                            policy.action_start + 1,
                            policy.action_start + 2,
                        ),
                        action_rotation_indices=tuple(
                            range(policy.action_start + 3, policy.action_stop)
                        ),
                        state_translation_indices=(
                            policy.state_start,
                            policy.state_start + 1,
                            policy.state_start + 2,
                        ),
                        state_rotation_indices=tuple(
                            range(policy.state_start + 3, policy.state_stop)
                        ),
                        rotation_representation=RotationRepresentation.AXIS_ANGLE,
                        frame_convention=SE3FrameConvention.REFERENCE_LOCAL,
                        valid_dimension_mask=tuple(True for _ in range(action_dim)),
                        parameters=(
                            SE3TypedParameter("family", self.family_key),
                            SE3TypedParameter("embodiment", embodiment),
                        ),
                        provenance=(
                            "Isaac-GR00T n1.6.1-release action_config; "
                            "AutoVLA canonical SE3 reimplementation"
                        ),
                        execution_side=ExecutionSide.FAMILY_PROCESSOR,
                        name=f"se3_relative_action_{index}",
                    )
                )
        stages.append(
            NormalizeStage(
                "state",
                statistics.state,
                TensorLayout.time_feature(state_time, state_dim),
                AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES),
                execution_side=ExecutionSide.FAMILY_PROCESSOR,
                name="normalize_state",
            )
        )
        action_statistics = (
            statistics.relative_action
            if self.use_relative_actions and statistics.relative_action is not None
            else statistics.action
        )
        action_alignment = (
            AlignmentPolicy(AlignmentMode.EXACT)
            if action_statistics.layout.contains("time")
            else AlignmentPolicy(AlignmentMode.BROADCAST_MISSING_AXES)
        )
        stages.append(
            NormalizeStage(
                "actions",
                action_statistics,
                TensorLayout.time_feature(action_time, action_dim),
                action_alignment,
                execution_side=ExecutionSide.FAMILY_PROCESSOR,
                name="normalize_actions",
            )
        )
        stages.extend(
            (
                PaddingStage(
                    "state",
                    TensorLayout.time_feature(),
                    state_shape,
                    (state_time, self.max_state_dim),
                    "state_padding_mask",
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                    name="pad_state",
                ),
                PaddingStage(
                    "actions",
                    TensorLayout.time_feature(),
                    action_shape,
                    (self.action_horizon, self.max_action_dim),
                    "action_padding_mask",
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                    name="pad_actions",
                ),
                MaskCompositionStage(
                    ("action_observed_mask", "action_padding_mask"),
                    "action_mask",
                    MaskKind.LOSS,
                    execution_side=ExecutionSide.FAMILY_PROCESSOR,
                    name="compose_action_mask",
                ),
            )
        )
        return TransformPlan(stages)

    @classmethod
    def reduced_runtime(cls, *, eagle_asset_path: str) -> "Gr00tN1d6Config":
        """构造缩小类图测试配置;路径仍不得用于官方资产。"""

        statistics = EmbodimentStatistics(
            state=_identity_statistics(8),
            action=_identity_statistics(8),
            state_clip=False,
            action_clip=False,
            source_fingerprint="autovla-reduced-runtime-v1",
        )
        return cls(
            architecture_variant="reduced_runtime",
            action_horizon=16,
            max_state_dim=8,
            max_action_dim=8,
            backbone_embedding_dim=64,
            retained_language_layers=2,
            action_hidden_size=64,
            input_embedding_dim=64,
            num_layers=2,
            num_attention_heads=4,
            attention_head_dim=16,
            camera_order=("camera.rgb_0",),
            embodiment_ids={"reduced": 0},
            statistics={"reduced": statistics},
            image_size=32,
            random_crop_scale=(1.0, 1.0),
            tune_top_llm_layers=0,
            eagle_asset_path=eagle_asset_path,
        )


__all__ = [
    "EmbodimentStatistics",
    "FeatureStatistics",
    "Gr00tN1d6Config",
    "PerHorizonFeatureStatistics",
]
