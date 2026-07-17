"""GR00T N1.7 artifact 优先的类型化配置。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

NVIDIA_GR00T_SOURCE_REVISION = "9c7e746b2cd37a810070a98ef41d290a07e806c2"
GR00T_N1D7_CHECKPOINT_REVISION = "2fc962b973bccdd5d8ce4f67cc63b264d6886495"
GR00T_N1D7_CHECKPOINT_ID = "nvidia/GR00T-N1.7-3B"
COSMOS_BACKBONE_ID = "nvidia/Cosmos-Reason2-2B"


class _ArtifactConfigurationError(ValueError):
    """表示 artifact 配置缺失或偏离固定 N1.7 契约。"""


def _exact_int(payload: Mapping[str, object], key: str) -> int:
    """读取 artifact 中不可由 bool 冒充的整数。"""

    value = payload.get(key)
    if type(value) is not int:
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be an exact integer")
    return value


def _exact_bool(payload: Mapping[str, object], key: str) -> bool:
    """读取 artifact 中的精确布尔值。"""

    value = payload.get(key)
    if type(value) is not bool:
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be an exact bool")
    return value


def _optional_bool(payload: Mapping[str, object], key: str, default: bool) -> bool:
    """读取可选 artifact 布尔值并拒绝真值隐式转换。"""

    value = payload.get(key, default)
    if type(value) is not bool:
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be an exact bool")
    return value


def _optional_nonnegative_int(payload: Mapping[str, object], key: str, default: int) -> int:
    """读取可选非负整数调优字段。"""

    value = payload.get(key, default)
    if type(value) is not int or value < 0:
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be a non-negative integer")
    return value


def _mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object]:
    """读取 checkpoint 中必需的嵌套配置对象。"""

    value = payload.get(key)
    if not isinstance(value, Mapping):
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be a mapping")
    if any(not isinstance(item, str) for item in value):
        raise _ArtifactConfigurationError(f"artifact field {key!r} must use string keys")
    return cast(Mapping[str, object], value)


def _default_embodiment_ids() -> Mapping[str, int]:
    """返回空映射; 正式装配必须从 ``embodiment_id.json`` 重建。"""

    return {}


@dataclass(frozen=True, slots=True)
class Gr00tN1d7Config:
    """绑定 checkpoint 实现值、调优默认值和本地资产身份。

    ``retained_language_layers=16`` 来自打包 artifact。扩散块数为 artifact
    实现的 32 而不是源码默认的 16。配置只描述装配。不执行运行时导入。
    """

    artifact_revision: str
    cosmos_revision: str
    retained_language_layers: int
    diffusion_layers: int
    vl_self_attention_layers: int
    load_bf16: bool
    state_dropout_probability: float
    family_key: str = "gr00t_n1d7"
    checkpoint_id: str = GR00T_N1D7_CHECKPOINT_ID
    cosmos_backbone_id: str = COSMOS_BACKBONE_ID
    max_state_dim: int = 132
    max_action_dim: int = 132
    action_horizon: int = 40
    max_num_embodiments: int = 32
    backbone_hidden_size: int = 2048
    action_hidden_size: int = 1024
    action_model_width: int = 1024
    action_attention_heads: int = 16
    action_attention_head_dim: int = 64
    flow_beta_alpha: float = 1.5
    flow_beta_beta: float = 1.0
    flow_time_scale: float = 0.999
    timestep_buckets: int = 1000
    num_inference_steps: int = 4
    image_resolution_policy: str = "processor_managed_dynamic_grid"
    tune_language: bool = True
    tune_visual: bool = True
    tune_action_head: bool = True
    tune_projectors: bool = True
    tune_diffusion_model: bool = True
    tune_vlln: bool = True
    tune_top_language_layers: int = 0
    embodiment_ids: Mapping[str, int] = field(default_factory=_default_embodiment_ids)
    local_files_only: bool = True
    trust_remote_code: bool = False

    def __post_init__(self) -> None:
        """拒绝源码默认回填、远端代码和不完整 artifact 身份。"""

        if self.family_key != "gr00t_n1d7":
            raise _ArtifactConfigurationError("family_key must be gr00t_n1d7")
        if self.artifact_revision != GR00T_N1D7_CHECKPOINT_REVISION:
            raise _ArtifactConfigurationError("checkpoint artifact revision is not pinned")
        if len(self.cosmos_revision) != 40 or any(
            character not in "0123456789abcdef" for character in self.cosmos_revision
        ):
            raise _ArtifactConfigurationError("Cosmos revision must be an immutable Git SHA")
        expected = {
            "retained_language_layers": 16,
            "diffusion_layers": 32,
            "vl_self_attention_layers": 4,
            "max_state_dim": 132,
            "max_action_dim": 132,
            "action_horizon": 40,
            "max_num_embodiments": 32,
            "backbone_hidden_size": 2048,
            "action_hidden_size": 1024,
            "action_model_width": 1024,
            "action_attention_heads": 16,
            "action_attention_head_dim": 64,
            "num_inference_steps": 4,
        }
        mismatches = tuple(name for name, value in expected.items() if getattr(self, name) != value)
        if mismatches:
            raise _ArtifactConfigurationError(
                f"GR00T N1.7 artifact contract mismatch: {mismatches}"
            )
        if not self.load_bf16 or self.state_dropout_probability != 0.2:
            raise _ArtifactConfigurationError("artifact BF16/dropout values must override source")
        if not self.local_files_only or self.trust_remote_code:
            raise _ArtifactConfigurationError("N1.7 must remain local-only without remote code")
        for name in (
            "tune_language",
            "tune_visual",
            "tune_action_head",
            "tune_projectors",
            "tune_diffusion_model",
            "tune_vlln",
        ):
            if type(getattr(self, name)) is not bool:
                raise _ArtifactConfigurationError(f"{name} must be an exact bool")
        if type(self.tune_top_language_layers) is not int or self.tune_top_language_layers < 0:
            raise _ArtifactConfigurationError("tune_top_language_layers must be non-negative")
        if self.action_model_width != self.action_attention_heads * self.action_attention_head_dim:
            raise _ArtifactConfigurationError("action width must equal heads times head dimension")
        if (
            self.flow_beta_alpha,
            self.flow_beta_beta,
            self.flow_time_scale,
            self.timestep_buckets,
        ) != (1.5, 1.0, 0.999, 1000):
            raise _ArtifactConfigurationError("flow-matching schedule must match the artifact")
        embodiment_ids = dict(self.embodiment_ids)
        if any(
            not isinstance(name, str)
            or not name.strip()
            or type(index) is not int
            or index < 0
            or index >= self.max_num_embodiments
            for name, index in embodiment_ids.items()
        ):
            raise _ArtifactConfigurationError("embodiment ids must map names into [0,32)")
        if len(set(embodiment_ids.values())) != len(embodiment_ids):
            raise _ArtifactConfigurationError("embodiment projector ids must be unique")
        object.__setattr__(self, "embodiment_ids", MappingProxyType(embodiment_ids))

    @classmethod
    def from_artifact_mapping(
        cls,
        payload: Mapping[str, object],
        *,
        cosmos_revision: str,
    ) -> Gr00tN1d7Config:
        """仅从已读取的本地 artifact 字段构造配置。

        缺失字段不会退回源码默认值。source 的 ``select_layer=12``、
        16 层扩散块和 ``load_bf16=false`` 不能覆盖 checkpoint 实现值。
        """

        dropout = payload.get("state_dropout_prob")
        if type(dropout) not in (int, float):
            raise _ArtifactConfigurationError("artifact field 'state_dropout_prob' must be numeric")
        diffusion = payload.get("diffusion_model_cfg")
        vl_attention = payload.get("vl_self_attention_cfg")
        diffusion_payload = (
            _mapping(payload, "diffusion_model_cfg") if diffusion is not None else payload
        )
        vl_attention_payload = (
            _mapping(payload, "vl_self_attention_cfg") if vl_attention is not None else payload
        )
        tuning = payload.get("tuning")
        tuning_payload = (
            cast(Mapping[str, object], tuning) if isinstance(tuning, Mapping) else payload
        )
        return cls(
            artifact_revision=GR00T_N1D7_CHECKPOINT_REVISION,
            cosmos_revision=cosmos_revision,
            retained_language_layers=_exact_int(payload, "select_layer"),
            diffusion_layers=_exact_int(diffusion_payload, "num_layers"),
            vl_self_attention_layers=_exact_int(
                vl_attention_payload,
                "num_layers" if vl_attention is not None else "vl_self_attention_layers",
            ),
            load_bf16=_exact_bool(payload, "load_bf16"),
            state_dropout_probability=float(cast(float | int, dropout)),
            max_state_dim=_exact_int(payload, "max_state_dim"),
            max_action_dim=_exact_int(payload, "max_action_dim"),
            action_horizon=_exact_int(payload, "action_horizon"),
            tune_language=_optional_bool(tuning_payload, "tune_llm", True),
            tune_visual=_optional_bool(tuning_payload, "tune_visual", True),
            tune_action_head=_optional_bool(tuning_payload, "tune_action_head", True),
            tune_projectors=_optional_bool(tuning_payload, "tune_projector", True),
            tune_diffusion_model=_optional_bool(tuning_payload, "tune_diffusion_model", True),
            tune_vlln=_optional_bool(tuning_payload, "tune_vlln", True),
            tune_top_language_layers=_optional_nonnegative_int(
                tuning_payload, "tune_top_llm_layers", 0
            ),
        )

    @property
    def fingerprint(self) -> str:
        """返回进入共享装配请求的稳定配置身份。"""

        payload = {
            name: (
                dict(getattr(self, name))
                if isinstance(getattr(self, name), Mapping)
                else getattr(self, name)
            )
            for name in self.__dataclass_fields__
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "COSMOS_BACKBONE_ID",
    "GR00T_N1D7_CHECKPOINT_ID",
    "GR00T_N1D7_CHECKPOINT_REVISION",
    "NVIDIA_GR00T_SOURCE_REVISION",
    "Gr00tN1d7Config",
]
