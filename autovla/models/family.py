"""AutoVLA 模型族注册与许可证契约。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, TypeAlias

from autovla.core.runtime import EnvProfile

LicenseState: TypeAlias = Literal[
    "verified_permissive",
    "requires_upstream_verification",
    "requires_model_license_review",
    "requires_model_card_review",
]
RuntimeStatus: TypeAlias = Literal[
    "metadata_only",
    "dryrun_adapter_supported",
    "upstream_runtime_not_loaded",
    "roadmap_only",
    "no_import",
    "deterministic_test_only",
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
    """AutoVLA-native 模型族元数据。"""

    family_key: str
    display_name: str
    license: LicenseSpec
    upstream_reference: str
    modality_inputs: tuple[str, ...]
    action_output: str
    action_head_family: str
    embodiment: tuple[str, ...]
    runtime_status: tuple[RuntimeStatus, ...]
    env_profiles: tuple[EnvProfile, ...]
    processor_family: str = "metadata_only_unverified"
    backbone_family: str = "metadata_only_unverified"
    normalization_support: str = "unverified"
    no_weight_load: bool = True
    no_tokenizer_load: bool = True
    no_network: bool = True
    no_checkpoint_download: bool = True
    reuse: tuple[OpenSourceReuseSpec, ...] = ()

    def __post_init__(self) -> None:
        """校验模型族元数据保持 metadata-only 安全边界。"""
        for name in ("family_key", "display_name", "upstream_reference", "action_output"):
            _require_text(getattr(self, name), name)
        if not self.modality_inputs:
            raise ValueError("modality_inputs must not be empty")
        if not self.embodiment:
            raise ValueError("embodiment must not be empty")
        if not self.runtime_status:
            raise ValueError("runtime_status must not be empty")
        if not self.env_profiles:
            raise ValueError("env_profiles must not be empty")
        for name in ("processor_family", "backbone_family", "normalization_support"):
            _require_text(getattr(self, name), name)
        if not all(
            (
                self.no_weight_load,
                self.no_tokenizer_load,
                self.no_network,
                self.no_checkpoint_download,
            )
        ):
            raise ValueError("metadata family specs must keep no-load/no-network flags true")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "family_key": self.family_key,
            "display_name": self.display_name,
            "license": self.license.to_json_dict(),
            "upstream_reference": self.upstream_reference,
            "modality_inputs": list(self.modality_inputs),
            "action_output": self.action_output,
            "action_head_family": self.action_head_family,
            "embodiment": list(self.embodiment),
            "runtime_status": list(self.runtime_status),
            "env_profiles": [profile.to_json_dict() for profile in self.env_profiles],
            "processor_family": self.processor_family,
            "backbone_family": self.backbone_family,
            "normalization_support": self.normalization_support,
            "no_weight_load": self.no_weight_load,
            "no_tokenizer_load": self.no_tokenizer_load,
            "no_network": self.no_network,
            "no_checkpoint_download": self.no_checkpoint_download,
            "reuse": [item.to_json_dict() for item in self.reuse],
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistry:
    """轻量模型族注册表, 不做懒加载或重型 runtime import。"""

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
