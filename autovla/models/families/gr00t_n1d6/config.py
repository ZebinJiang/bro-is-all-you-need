"""AutoVLA GR00T N1.6.1 不可变配置。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import MappingProxyType

from autovla.models.components.relative_actions import RelativeActionPolicy


def _default_cameras() -> tuple[str, ...]:
    """返回显式默认相机顺序。"""
    return ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")


def _default_embodiments() -> Mapping[str, int]:
    """返回 pinned N1.6.1 embodiment projector 映射。"""
    return {
        "oxe_google": 0,
        "oxe_widowx": 1,
        "libero_panda": 2,
        "unitree_g1": 8,
        "new_embodiment": 10,
        "robocasa_panda_omron": 13,
        "oxe_droid": 16,
        "gr1": 20,
        "behavior_r1_pro": 24,
    }


@dataclass(frozen=True, slots=True)
class FeatureStatistics:
    """保存一个 embodiment 的状态或动作归一化向量。"""

    offset: tuple[float, ...]
    scale: tuple[float, ...]
    clip: bool = True

    def __post_init__(self) -> None:
        """校验归一化向量同长且尺度严格为正。"""
        if not self.offset or len(self.offset) != len(self.scale):
            raise ValueError("normalization offset and scale must be non-empty and equally sized")
        if any(value <= 0 for value in self.scale):
            raise ValueError("normalization scale must be positive")


@dataclass(frozen=True, slots=True)
class EmbodimentStatistics:
    """保存状态/动作统计和相对动作维度。"""

    state: FeatureStatistics
    action: FeatureStatistics
    relative_action_policies: tuple[RelativeActionPolicy, ...] = ()

    def __post_init__(self) -> None:
        """校验相对动作策略切片不重叠且在统计范围内。"""
        occupied: set[int] = set()
        for policy in self.relative_action_policies:
            if policy.action_stop > len(self.action.offset):
                raise ValueError("relative action policy exceeds action statistics")
            if policy.state_stop > len(self.state.offset):
                raise ValueError("relative action policy exceeds state statistics")
            dimensions = set(range(policy.action_start, policy.action_stop))
            if occupied & dimensions:
                raise ValueError("relative action policy slices must not overlap")
            occupied.update(dimensions)


def _empty_statistics() -> Mapping[str, EmbodimentStatistics]:
    """返回空 embodiment 统计映射。"""
    return {}


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Config:
    """描述 pinned N1.6.1 模型、处理器和 tune/freeze 契约。

    配置只接受本地资产路径。默认 horizon 为 16,状态和动作最大维度均为
    29,embodiment 参数库容量为 32。
    """

    family_key: str = "gr00t_n1d6"
    action_horizon: int = 16
    max_state_dim: int = 29
    max_action_dim: int = 29
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
    tune_top_llm_layers: int = 0
    tune_action_head: bool = True
    tune_projector: bool = True
    tune_diffusion_model: bool = True
    tune_vlln: bool = True
    trainable_parameters_fp32: bool = True
    state_dropout_probability: float = 0.0
    state_noise_scale: float = 0.0
    eagle_asset_path: str | None = None
    checkpoint_path: str | None = None
    local_files_only: bool = True

    def __post_init__(self) -> None:
        """校验 pinned 架构、维度、路径和 tune 策略。"""
        if self.family_key != "gr00t_n1d6":
            raise ValueError("family_key must be gr00t_n1d6")
        if self.action_horizon != 16:
            raise ValueError("pinned N1.6.1 action_horizon must be exactly 16")
        if not 0 < self.max_state_dim <= 29 or not 0 < self.max_action_dim <= 29:
            raise ValueError("state/action dimensions must be in [1,29]")
        if self.max_num_embodiments != 32:
            raise ValueError("pinned N1.6.1 embodiment bank must contain 32 categories")
        if self.input_embedding_dim != self.num_attention_heads * self.attention_head_dim:
            raise ValueError("input_embedding_dim must equal heads * head_dim")
        if self.num_layers != 32 or self.num_inference_steps != 4:
            raise ValueError("pinned N1.6.1 requires 32 DiT layers and four Euler steps")
        if self.backbone_embedding_dim != 2048 or self.action_hidden_size != 1024:
            raise ValueError("pinned backbone/action widths must be 2048/1024")
        if self.retained_language_layers != 16:
            raise ValueError("pinned N1.6.1 Eagle path retains exactly 16 language layers")
        if not self.camera_order or len(set(self.camera_order)) != len(self.camera_order):
            raise ValueError("camera_order must be non-empty and unique")
        if any(not name.strip() for name in self.camera_order):
            raise ValueError("camera names must not be empty")
        embodiment_ids = dict(self.embodiment_ids)
        if any(not name.strip() for name in embodiment_ids):
            raise ValueError("embodiment names must not be empty")
        if len(set(embodiment_ids.values())) != len(embodiment_ids):
            raise ValueError("embodiment projector IDs must be unique")
        if any(index < 0 or index >= 32 for index in embodiment_ids.values()):
            raise ValueError("embodiment projector IDs must be in [0,32)")
        if not self.local_files_only:
            raise ValueError("GR00T N1.6.1 assets must remain local_files_only")
        for name in ("eagle_asset_path", "checkpoint_path"):
            value = getattr(self, name)
            if value is not None:
                path = Path(value).expanduser()
                if not path.is_absolute():
                    raise ValueError(f"{name} must be an absolute local path")
        if not 0 <= self.state_dropout_probability < 1:
            raise ValueError("state_dropout_probability must be in [0,1)")
        if self.state_noise_scale < 0:
            raise ValueError("state_noise_scale must be non-negative")
        if self.tune_top_llm_layers < 0:
            raise ValueError("tune_top_llm_layers must be non-negative")
        if not self.tune_backbone and (
            self.tune_llm or self.tune_visual or self.tune_top_llm_layers
        ):
            raise ValueError("frozen aggregate backbone cannot selectively unfreeze modules")
        if not self.tune_action_head and (
            self.tune_projector or self.tune_diffusion_model or self.tune_vlln
        ):
            raise ValueError("frozen aggregate action head cannot selectively unfreeze modules")
        object.__setattr__(self, "embodiment_ids", MappingProxyType(embodiment_ids))
        object.__setattr__(self, "statistics", MappingProxyType(dict(self.statistics)))

    @classmethod
    def from_mapping(
        cls,
        payload: Mapping[str, object],
        *,
        statistics: Mapping[str, EmbodimentStatistics],
        embodiment_ids: Mapping[str, int] | None,
        eagle_asset_path: str,
        checkpoint_path: str,
    ) -> "Gr00tN1d6Config":
        """从静态 checkpoint 映射逐字段构造配置,拒绝隐藏类型转换。"""
        defaults = cls()
        return cls(
            family_key=_string(payload, "family_key", defaults.family_key),
            action_horizon=_integer(payload, "action_horizon", defaults.action_horizon),
            max_state_dim=_integer(payload, "max_state_dim", defaults.max_state_dim),
            max_action_dim=_integer(payload, "max_action_dim", defaults.max_action_dim),
            max_num_embodiments=_integer(
                payload,
                "max_num_embodiments",
                defaults.max_num_embodiments,
            ),
            backbone_embedding_dim=_integer(
                payload,
                "backbone_embedding_dim",
                defaults.backbone_embedding_dim,
            ),
            retained_language_layers=_integer(
                payload,
                "retained_language_layers",
                defaults.retained_language_layers,
            ),
            action_hidden_size=_integer(
                payload,
                "action_hidden_size",
                defaults.action_hidden_size,
            ),
            input_embedding_dim=_integer(
                payload,
                "input_embedding_dim",
                defaults.input_embedding_dim,
            ),
            num_layers=_integer(payload, "num_layers", defaults.num_layers),
            num_attention_heads=_integer(
                payload,
                "num_attention_heads",
                defaults.num_attention_heads,
            ),
            attention_head_dim=_integer(
                payload,
                "attention_head_dim",
                defaults.attention_head_dim,
            ),
            attention_dropout=_number(
                payload,
                "attention_dropout",
                defaults.attention_dropout,
            ),
            attend_text_every_n_blocks=_integer(
                payload,
                "attend_text_every_n_blocks",
                defaults.attend_text_every_n_blocks,
            ),
            num_inference_steps=_integer(
                payload,
                "num_inference_steps",
                defaults.num_inference_steps,
            ),
            noise_beta_alpha=_number(
                payload,
                "noise_beta_alpha",
                defaults.noise_beta_alpha,
            ),
            noise_beta_beta=_number(
                payload,
                "noise_beta_beta",
                defaults.noise_beta_beta,
            ),
            noise_time_scale=_number(
                payload,
                "noise_time_scale",
                defaults.noise_time_scale,
            ),
            num_timestep_buckets=_integer(
                payload,
                "num_timestep_buckets",
                defaults.num_timestep_buckets,
            ),
            camera_order=_string_tuple(payload, "camera_order", defaults.camera_order),
            embodiment_ids=defaults.embodiment_ids if embodiment_ids is None else embodiment_ids,
            statistics=statistics,
            use_relative_actions=_boolean(
                payload,
                "use_relative_actions",
                defaults.use_relative_actions,
            ),
            formalize_language=_boolean(
                payload,
                "formalize_language",
                defaults.formalize_language,
            ),
            image_size=_integer(payload, "image_size", defaults.image_size),
            random_crop_scale=_number_pair(
                payload,
                "random_crop_scale",
                defaults.random_crop_scale,
            ),
            color_jitter=_optional_number_quad(payload, "color_jitter", defaults.color_jitter),
            tune_backbone=_boolean(payload, "tune_backbone", defaults.tune_backbone),
            tune_llm=_boolean(payload, "tune_llm", defaults.tune_llm),
            tune_visual=_boolean(payload, "tune_visual", defaults.tune_visual),
            tune_top_llm_layers=_integer(
                payload,
                "tune_top_llm_layers",
                defaults.tune_top_llm_layers,
            ),
            tune_action_head=_boolean(
                payload,
                "tune_action_head",
                defaults.tune_action_head,
            ),
            tune_projector=_boolean(payload, "tune_projector", defaults.tune_projector),
            tune_diffusion_model=_boolean(
                payload,
                "tune_diffusion_model",
                defaults.tune_diffusion_model,
            ),
            tune_vlln=_boolean(payload, "tune_vlln", defaults.tune_vlln),
            trainable_parameters_fp32=_boolean(
                payload,
                "trainable_parameters_fp32",
                defaults.trainable_parameters_fp32,
            ),
            state_dropout_probability=_number(
                payload,
                "state_dropout_probability",
                defaults.state_dropout_probability,
            ),
            state_noise_scale=_number(
                payload,
                "state_noise_scale",
                defaults.state_noise_scale,
            ),
            eagle_asset_path=eagle_asset_path,
            checkpoint_path=checkpoint_path,
            local_files_only=_boolean(payload, "local_files_only", True),
        )


def _string(payload: Mapping[str, object], key: str, default: str) -> str:
    """读取非空字符串字段。"""
    value = payload.get(key, default)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"config field {key!r} must be a non-empty string")
    return value


def _integer(payload: Mapping[str, object], key: str, default: int) -> int:
    """读取严格整数配置字段。"""
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"config field {key!r} must be an integer")
    return value


def _number(payload: Mapping[str, object], key: str, default: float) -> float:
    """读取有限数值配置字段。"""
    value = payload.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"config field {key!r} must be numeric")
    result = float(value)
    if result != result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"config field {key!r} must be finite")
    return result


def _boolean(payload: Mapping[str, object], key: str, default: bool) -> bool:
    """读取严格布尔配置字段。"""
    value = payload.get(key, default)
    if not isinstance(value, bool):
        raise ValueError(f"config field {key!r} must be bool")
    return value


def _string_tuple(
    payload: Mapping[str, object],
    key: str,
    default: tuple[str, ...],
) -> tuple[str, ...]:
    """读取非空字符串序列。"""
    value = payload.get(key, default)
    if (
        not isinstance(value, (list, tuple))
        or not value
        or not all(isinstance(item, str) and item.strip() for item in value)
    ):
        raise ValueError(f"config field {key!r} must be a non-empty string sequence")
    return tuple(value)


def _number_pair(
    payload: Mapping[str, object],
    key: str,
    default: tuple[float, float],
) -> tuple[float, float]:
    """读取两个有限数值。"""
    values = _number_sequence(payload.get(key, default), key=key, size=2)
    return values[0], values[1]


def _optional_number_quad(
    payload: Mapping[str, object],
    key: str,
    default: tuple[float, float, float, float] | None,
) -> tuple[float, float, float, float] | None:
    """读取可选四元数值配置。"""
    raw = payload.get(key, default)
    if raw is None:
        return None
    values = _number_sequence(raw, key=key, size=4)
    return values[0], values[1], values[2], values[3]


def _number_sequence(raw: object, *, key: str, size: int) -> tuple[float, ...]:
    """校验固定长度有限数值序列。"""
    if not isinstance(raw, (list, tuple)) or len(raw) != size:
        raise ValueError(f"config field {key!r} must contain {size} numbers")
    result: list[float] = []
    for value in raw:
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise ValueError(f"config field {key!r} must contain only numbers")
        numeric = float(value)
        if numeric != numeric or numeric in {float("inf"), float("-inf")}:
            raise ValueError(f"config field {key!r} must contain finite numbers")
        result.append(numeric)
    return tuple(result)


__all__ = [
    "EmbodimentStatistics",
    "FeatureStatistics",
    "Gr00tN1d6Config",
]
