"""AutoVLA 模型族注册、许可证与结构化能力契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    ActionRepresentation,
    ExecutionMode,
    ModelCapabilities,
    NormalizationMode,
)

LicenseState: TypeAlias = Literal[
    "verified_permissive",
    "requires_upstream_verification",
    "requires_model_license_review",
    "requires_model_card_review",
]
ReuseMode: TypeAlias = Literal["inspired", "wrapped", "adapted", "copied", "rejected"]


def _empty_notes() -> tuple[str, ...]:
    """返回空说明元组。"""
    return ()


def _require_text(value: str, name: str) -> None:
    """校验文本非空。"""
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


@dataclass(frozen=True, slots=True)
class LicenseSpec:
    """记录模型族代码、权重和模型卡许可证状态。"""

    code_license_status: LicenseState
    weight_license_status: LicenseState
    model_card_status: LicenseState
    notes: tuple[str, ...] = field(default_factory=_empty_notes)

    def __post_init__(self) -> None:
        """校验许可证说明。"""
        for index, note in enumerate(self.notes):
            _require_text(note, f"license.notes[{index}]")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "code_license_status": self.code_license_status,
            "weight_license_status": self.weight_license_status,
            "model_card_status": self.model_card_status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class OpenSourceReuseSpec:
    """记录某个上游参考的复用决策。"""

    upstream_project: str
    upstream_url: str
    license: str
    reuse_mode: ReuseMode
    copied_or_adapted_code: bool
    wholesale_rejection_reason: str

    def __post_init__(self) -> None:
        """校验复用决策字段。"""
        for name in ("upstream_project", "upstream_url", "license", "wholesale_rejection_reason"):
            _require_text(getattr(self, name), name)
        if self.copied_or_adapted_code and self.reuse_mode not in {"copied", "adapted"}:
            raise ValueError("copied_or_adapted_code requires copied/adapted reuse_mode")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "upstream_project": self.upstream_project,
            "upstream_url": self.upstream_url,
            "license": self.license,
            "reuse_mode": self.reuse_mode,
            "copied_or_adapted_code": self.copied_or_adapted_code,
            "wholesale_rejection_reason": self.wholesale_rejection_reason,
        }


@dataclass(frozen=True, slots=True)
class ModelFamilySpec:
    """以 ``capabilities`` 作为唯一能力事实源的模型族元数据。"""

    family_key: str
    display_name: str
    license: LicenseSpec
    upstream_reference: str
    embodiment: tuple[str, ...]
    env_profiles: tuple[EnvProfile, ...]
    capabilities: ModelCapabilities
    reuse: tuple[OpenSourceReuseSpec, ...] = ()

    def __post_init__(self) -> None:
        """校验模型族身份和环境声明。"""
        for name in ("family_key", "display_name", "upstream_reference"):
            _require_text(getattr(self, name), name)
        if not self.embodiment:
            raise ValueError("embodiment must not be empty")
        if not self.env_profiles:
            raise ValueError("env_profiles must not be empty")

    @property
    def modality_inputs(self) -> tuple[str, ...]:
        """从能力记录派生旧输入模态摘要。"""
        inputs: list[str] = []
        if self.capabilities.inputs.language_required:
            inputs.append("language")
        if self.capabilities.inputs.required_cameras:
            inputs.append("three_rgb_cameras")
        else:
            inputs.append("image_views")
        if self.capabilities.inputs.state_policy.value in {"required", "optional", "unverified"}:
            inputs.append(
                "state"
                if self.capabilities.execution.executable_test_double
                else "proprioception/state"
            )
        return tuple(inputs)

    @property
    def action_output(self) -> str:
        """从动作表示派生旧输出摘要。"""
        if self.capabilities.action.representation is ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK:
            return "continuous action chunk"
        return "unverified action output"

    @property
    def action_head_family(self) -> str:
        """从规范组件描述符派生旧 action-head 名称。"""
        return self.capabilities.action_head.identity

    @property
    def runtime_status(self) -> tuple[str, ...]:
        """返回旧描述标签,不授予规范执行能力。"""
        mode = self.capabilities.execution.mode
        if mode is ExecutionMode.DETERMINISTIC_TEST_ONLY:
            return ("deterministic_test_only",)
        if self.family_key == "gr00t-n1d6":
            return ("metadata_only", "dryrun_adapter_supported", "upstream_runtime_not_loaded")
        if "roadmap_only" in self.embodiment:
            return ("roadmap_only", "no_import")
        return ("metadata_only", "no_import")

    @property
    def processor_family(self) -> str:
        """从规范组件描述符派生旧 processor 名称。"""
        return self.capabilities.processor.identity

    @property
    def backbone_family(self) -> str:
        """从规范组件描述符派生旧 backbone 名称。"""
        return self.capabilities.backbone.identity

    @property
    def normalization_support(self) -> str:
        """从规范归一化能力派生旧摘要。"""
        normalization = self.capabilities.normalization
        if normalization.mode is NormalizationMode.IDENTITY:
            return "supported_identity_only"
        if normalization.mode is NormalizationMode.STATISTICS_GOVERNED:
            return "unverified_statistics_governed"
        return "unverified"

    @property
    def no_weight_load(self) -> bool:
        """从副作用权限派生旧权重加载禁用标记。"""
        return not self.capabilities.execution.permissions.asset_load

    @property
    def no_tokenizer_load(self) -> bool:
        """从副作用权限派生旧 tokenizer 加载禁用标记。"""
        return not self.capabilities.execution.permissions.tokenizer_load

    @property
    def no_network(self) -> bool:
        """从副作用权限派生旧网络禁用标记。"""
        return not self.capabilities.execution.permissions.network

    @property
    def no_checkpoint_download(self) -> bool:
        """从副作用权限派生旧 checkpoint 加载禁用标记。"""
        return not self.capabilities.execution.permissions.checkpoint_load

    def to_json_dict(self) -> dict[str, object]:
        """返回含规范能力和派生兼容字段的稳定 JSON 表示。"""
        return {
            "action_head_family": self.action_head_family,
            "action_output": self.action_output,
            "backbone_family": self.backbone_family,
            "capabilities": self.capabilities.to_json_dict(),
            "display_name": self.display_name,
            "embodiment": list(self.embodiment),
            "env_profiles": [profile.to_json_dict() for profile in self.env_profiles],
            "family_key": self.family_key,
            "license": self.license.to_json_dict(),
            "modality_inputs": list(self.modality_inputs),
            "no_checkpoint_download": self.no_checkpoint_download,
            "no_network": self.no_network,
            "no_tokenizer_load": self.no_tokenizer_load,
            "no_weight_load": self.no_weight_load,
            "normalization_support": self.normalization_support,
            "processor_family": self.processor_family,
            "reuse": [item.to_json_dict() for item in self.reuse],
            "runtime_status": list(self.runtime_status),
            "upstream_reference": self.upstream_reference,
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistry:
    """轻量模型族注册表,不执行重型 runtime import。"""

    entries: tuple[ModelFamilySpec, ...]

    def __post_init__(self) -> None:
        """校验模型族 key 唯一。"""
        keys = [entry.family_key for entry in self.entries]
        if len(keys) != len(set(keys)):
            raise ValueError("model family keys must be unique")

    def get(self, family_key: str) -> ModelFamilySpec:
        """按 family key 返回模型族元数据。"""
        for entry in self.entries:
            if entry.family_key == family_key:
                return entry
        raise KeyError(f"unknown model family: {family_key}")

    def keys(self) -> tuple[str, ...]:
        """返回已注册模型族 key。"""
        return tuple(entry.family_key for entry in self.entries)
