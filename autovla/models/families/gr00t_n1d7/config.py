"""GR00T N1.7 artifact 优先的类型化配置。"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

NVIDIA_GR00T_SOURCE_REVISION = "9c7e746b2cd37a810070a98ef41d290a07e806c2"
GR00T_N1D7_CHECKPOINT_REVISION = "2fc962b973bccdd5d8ce4f67cc63b264d6886495"
GR00T_N1D7_CHECKPOINT_ID = "nvidia/GR00T-N1.7-3B"
COSMOS_BACKBONE_ID = "nvidia/Cosmos-Reason2-2B"

EMBODIMENT_ALIAS_GROUPS = MappingProxyType(
    {
        0: ("simpler_env_google",),
        1: ("simpler_env_widowx",),
        2: ("libero_sim",),
        10: ("new_embodiment", "robocasa_panda_omron", "robocasa_gr1_tabletop"),
        11: ("unitree_g1_sonic",),
        24: ("oxe_droid_relative_eef_relative_joint",),
        25: (
            "real_g1_relative_eef_relative_joints",
            "unitree_g1_full_body_with_waist_height_nav_cmd",
        ),
        26: (
            "real_r1_pro_sharpa_relative_eef",
            "real_r1_pro_sharpa_relative_eef_human",
            "real_r1_pro_sharpa_relative_eef_maxinsights",
            "real_r1_pro_sharpa_relative_eef_mecka",
        ),
        27: ("xdof_relative_eef_relative_joint", "xdof_relative_eef_relative_joint_subtask"),
    }
)


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
    object_mapping = cast(Mapping[object, object], value)
    if any(not isinstance(item, str) for item in object_mapping):
        raise _ArtifactConfigurationError(f"artifact field {key!r} must use string keys")
    return cast(Mapping[str, object], object_mapping)


def _optional_mapping(payload: Mapping[str, object], key: str) -> Mapping[str, object] | None:
    """读取可选嵌套对象, 同时拒绝非字符串键。"""

    return _mapping(payload, key) if key in payload else None


def _optional_exact_int(payload: Mapping[str, object], key: str, default: int) -> int:
    """读取可选精确整数。"""

    return _exact_int(payload, key) if key in payload else default


def _optional_exact_float(payload: Mapping[str, object], key: str, default: float) -> float:
    """读取可选有限数值, 不接受 bool。"""

    value = payload.get(key, default)
    if type(value) not in (int, float):
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be numeric")
    result = float(cast(int | float, value))
    if not math.isfinite(result):
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be finite")
    return result


def _optional_positional_embedding(
    payload: Mapping[str, object],
    key: str,
    default: str | None,
) -> str | None:
    """读取上游 ``None`` 或 ``sinusoidal`` 位置编码选择。"""

    value = payload.get(key, default)
    if value not in {None, "sinusoidal"}:
        raise _ArtifactConfigurationError(f"artifact field {key!r} must be None or 'sinusoidal'")
    return cast(str | None, value)


def _expand_embodiment_aliases(mapping: Mapping[str, int]) -> dict[str, int]:
    """按固定上游 projector 分组补齐同一物理 embodiment 的别名。"""

    expanded = dict(mapping)
    for projector_id, aliases in EMBODIMENT_ALIAS_GROUPS.items():
        observed = {expanded[name] for name in aliases if name in expanded}
        if observed and observed != {projector_id}:
            raise _ArtifactConfigurationError(
                f"official embodiment aliases {aliases!r} must use projector {projector_id}"
            )
        for name in aliases:
            expanded.setdefault(name, projector_id)
    return expanded


def _default_embodiment_ids() -> Mapping[str, int]:
    """返回固定上游 alias 映射; artifact 可补充其他 projector。"""

    return _expand_embodiment_aliases({})


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
    action_model_width: int = 1536
    action_attention_heads: int = 32
    action_attention_head_dim: int = 48
    diffusion_output_dim: int = 1024
    attention_dropout: float = 0.2
    attention_bias: bool = True
    final_dropout: bool = True
    norm_epsilon: float = 1e-5
    diffusion_positional_embeddings: str | None = None
    diffusion_max_positional_embeddings: int = 512
    attend_text_every_n_blocks: int = 2
    state_history_length: int = 1
    max_sequence_length: int = 1024
    vl_attention_heads: int = 32
    vl_attention_head_dim: int = 64
    vl_attention_dropout: float = 0.1
    vl_attention_bias: bool = True
    vl_final_dropout: bool = True
    vl_positional_embeddings: str | None = "sinusoidal"
    vl_max_positional_embeddings: int = 512
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
            "action_model_width": 1536,
            "action_attention_heads": 32,
            "action_attention_head_dim": 48,
            "diffusion_output_dim": 1024,
            "attend_text_every_n_blocks": 2,
            "state_history_length": 1,
            "max_sequence_length": 1024,
            "vl_attention_heads": 32,
            "vl_attention_head_dim": 64,
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
        if self.diffusion_output_dim != self.action_hidden_size:
            raise _ArtifactConfigurationError("DiT output must match action decoder input")
        if self.backbone_hidden_size != self.vl_attention_heads * self.vl_attention_head_dim:
            raise _ArtifactConfigurationError(
                "VL self-attention width must match Cosmos hidden width"
            )
        if self.diffusion_positional_embeddings not in {None, "sinusoidal"}:
            raise _ArtifactConfigurationError("unsupported diffusion positional embedding")
        if self.vl_positional_embeddings not in {None, "sinusoidal"}:
            raise _ArtifactConfigurationError("unsupported VL positional embedding")
        if (
            min(
                self.diffusion_max_positional_embeddings,
                self.vl_max_positional_embeddings,
            )
            <= 0
        ):
            raise _ArtifactConfigurationError("positional embedding limits must be positive")
        if (
            self.flow_beta_alpha,
            self.flow_beta_beta,
            self.flow_time_scale,
            self.timestep_buckets,
        ) != (1.5, 1.0, 0.999, 1000):
            raise _ArtifactConfigurationError("flow-matching schedule must match the artifact")
        embodiment_ids = _expand_embodiment_aliases(self.embodiment_ids)
        for name, index in embodiment_ids.items():
            name_value = cast(object, name)
            index_value = cast(object, index)
            if (
                not isinstance(name_value, str)
                or not name_value.strip()
                or type(index_value) is not int
                or index_value < 0
                or index_value >= self.max_num_embodiments
            ):
                raise _ArtifactConfigurationError("embodiment ids must map names into [0,32)")
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

        model_payload = _optional_mapping(payload, "model_config") or payload
        dropout = model_payload.get("state_dropout_prob")
        if type(dropout) not in (int, float):
            raise _ArtifactConfigurationError("artifact field 'state_dropout_prob' must be numeric")
        diffusion_payload = _optional_mapping(model_payload, "diffusion_model_cfg") or model_payload
        vl_attention_payload = (
            _optional_mapping(model_payload, "vl_self_attention_cfg") or model_payload
        )
        model_name = model_payload.get("model_name", COSMOS_BACKBONE_ID)
        if model_name != COSMOS_BACKBONE_ID:
            raise _ArtifactConfigurationError("artifact model_name must identify Cosmos-Reason2-2B")
        model_revision = model_payload.get("model_revision")
        if model_revision is not None and model_revision != cosmos_revision:
            raise _ArtifactConfigurationError(
                "artifact Cosmos revision must exactly match the verified receipt"
            )
        tuning = model_payload.get("tuning")
        tuning_payload = (
            cast(Mapping[str, object], tuning) if isinstance(tuning, Mapping) else payload
        )
        return cls(
            artifact_revision=GR00T_N1D7_CHECKPOINT_REVISION,
            cosmos_revision=cosmos_revision,
            retained_language_layers=_exact_int(model_payload, "select_layer"),
            diffusion_layers=_exact_int(diffusion_payload, "num_layers"),
            vl_self_attention_layers=_exact_int(
                vl_attention_payload,
                (
                    "num_layers"
                    if "vl_self_attention_cfg" in model_payload
                    else "vl_self_attention_layers"
                ),
            ),
            load_bf16=_exact_bool(model_payload, "load_bf16"),
            state_dropout_probability=float(cast(float | int, dropout)),
            max_state_dim=_exact_int(model_payload, "max_state_dim"),
            max_action_dim=_exact_int(model_payload, "max_action_dim"),
            action_horizon=_exact_int(model_payload, "action_horizon"),
            max_num_embodiments=_optional_exact_int(model_payload, "max_num_embodiments", 32),
            backbone_hidden_size=_optional_exact_int(model_payload, "backbone_embedding_dim", 2048),
            action_hidden_size=_optional_exact_int(model_payload, "hidden_size", 1024),
            action_model_width=_optional_exact_int(model_payload, "input_embedding_dim", 1536),
            action_attention_heads=_optional_exact_int(
                diffusion_payload, "num_attention_heads", 32
            ),
            action_attention_head_dim=_optional_exact_int(
                diffusion_payload, "attention_head_dim", 48
            ),
            diffusion_output_dim=_optional_exact_int(diffusion_payload, "output_dim", 1024),
            attention_dropout=_optional_exact_float(diffusion_payload, "dropout", 0.2),
            attention_bias=_optional_bool(diffusion_payload, "attention_bias", True),
            final_dropout=_optional_bool(diffusion_payload, "final_dropout", True),
            norm_epsilon=_optional_exact_float(diffusion_payload, "norm_eps", 1e-5),
            diffusion_positional_embeddings=_optional_positional_embedding(
                diffusion_payload,
                "positional_embeddings",
                None,
            ),
            diffusion_max_positional_embeddings=_optional_exact_int(
                diffusion_payload,
                "max_num_positional_embeddings",
                512,
            ),
            attend_text_every_n_blocks=_optional_exact_int(
                model_payload, "attend_text_every_n_blocks", 2
            ),
            state_history_length=_optional_exact_int(model_payload, "state_history_length", 1),
            max_sequence_length=_optional_exact_int(model_payload, "max_seq_len", 1024),
            vl_attention_heads=_optional_exact_int(vl_attention_payload, "num_attention_heads", 32),
            vl_attention_head_dim=_optional_exact_int(
                vl_attention_payload, "attention_head_dim", 64
            ),
            vl_attention_dropout=_optional_exact_float(vl_attention_payload, "dropout", 0.1),
            vl_attention_bias=_optional_bool(vl_attention_payload, "attention_bias", True),
            vl_final_dropout=_optional_bool(vl_attention_payload, "final_dropout", True),
            vl_positional_embeddings=_optional_positional_embedding(
                vl_attention_payload,
                "positional_embeddings",
                "sinusoidal",
            ),
            vl_max_positional_embeddings=_optional_exact_int(
                vl_attention_payload,
                "max_num_positional_embeddings",
                512,
            ),
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
