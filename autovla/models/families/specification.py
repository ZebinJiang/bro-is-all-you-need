"""模型族唯一不可变定义及轻量架构契约。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    ActionRepresentation,
    ExecutionMode,
    ModelCapabilities,
    NormalizationMode,
)

LicenseState: TypeAlias = str
ReuseMode: TypeAlias = str


def _require_text(value: str, name: str) -> None:
    """要求标识文本非空。"""

    if not value.strip():
        raise ValueError(f"{name} must not be empty")


class RuntimeSupportState(str, Enum):
    """描述模型族运行时支持的封闭状态。"""

    EXECUTABLE = "executable"
    ARCHITECTURE_DEFINED_RUNTIME_DEFERRED = "architecture_defined_runtime_deferred"
    ASSET_REQUIRED = "asset_required"
    OPTIONAL_DEPENDENCY_REQUIRED = "optional_dependency_required"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class LicenseSpec:
    """分别记录源码、权重和模型卡许可状态。"""

    code_license_status: LicenseState
    weight_license_status: LicenseState
    model_card_status: LicenseState
    notes: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """拒绝空许可说明。"""

        for index, note in enumerate(self.notes):
            _require_text(note, f"license.notes[{index}]")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""

        return {
            "code_license_status": self.code_license_status,
            "weight_license_status": self.weight_license_status,
            "model_card_status": self.model_card_status,
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class OpenSourceReuseSpec:
    """记录固定上游来源及复用决策。"""

    upstream_project: str
    upstream_url: str
    license: str
    reuse_mode: ReuseMode
    copied_or_adapted_code: bool
    wholesale_rejection_reason: str
    revision: str | None = None

    def __post_init__(self) -> None:
        """校验来源、许可和固定 revision。"""

        for name in ("upstream_project", "upstream_url", "license", "reuse_mode"):
            _require_text(getattr(self, name), name)
        _require_text(self.wholesale_rejection_reason, "wholesale_rejection_reason")
        if self.revision is not None and (
            len(self.revision) != 40
            or any(character not in "0123456789abcdef" for character in self.revision)
        ):
            raise ValueError("upstream revision must be a lowercase 40-hex commit")
        if self.copied_or_adapted_code and self.reuse_mode not in {"copied", "adapted"}:
            raise ValueError("copied_or_adapted_code requires copied/adapted reuse_mode")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""

        return {
            "upstream_project": self.upstream_project,
            "upstream_url": self.upstream_url,
            "license": self.license,
            "reuse_mode": self.reuse_mode,
            "copied_or_adapted_code": self.copied_or_adapted_code,
            "wholesale_rejection_reason": self.wholesale_rejection_reason,
            "revision": self.revision,
        }


@dataclass(frozen=True, slots=True)
class ModelShapeContract:
    """声明模型族状态和动作张量的规范形状。"""

    action_horizon: int
    state_dimension: int
    action_dimension: int

    def __post_init__(self) -> None:
        """要求全部形状为正整数。"""

        if any(type(value) is not int or value <= 0 for value in self.to_tuple()):
            raise ValueError("model shape dimensions must be positive integers")

    def to_tuple(self) -> tuple[int, int, int]:
        """返回 ``(H,S,A)``。"""

        return (self.action_horizon, self.state_dimension, self.action_dimension)

    def to_json_dict(self) -> dict[str, int]:
        """返回稳定 JSON 结构。"""

        return {
            "action_horizon": self.action_horizon,
            "state_dimension": self.state_dimension,
            "action_dimension": self.action_dimension,
        }


@dataclass(frozen=True, slots=True)
class ModelInputContract:
    """声明有序相机、语言和状态条件。"""

    cameras: tuple[str, ...]
    image_size: int
    language_required: bool
    state_conditioning: str
    max_language_tokens: int | None = None

    def __post_init__(self) -> None:
        """校验输入模态次序和边界。"""

        if not self.cameras or len(set(self.cameras)) != len(self.cameras):
            raise ValueError("input cameras must be non-empty and unique")
        if self.image_size <= 0 or not self.state_conditioning.strip():
            raise ValueError("input image size and state conditioning must be defined")
        if self.max_language_tokens is not None and self.max_language_tokens <= 0:
            raise ValueError("max_language_tokens must be positive")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""

        return {
            "cameras": list(self.cameras),
            "image_size": self.image_size,
            "language_required": self.language_required,
            "state_conditioning": self.state_conditioning,
            "max_language_tokens": self.max_language_tokens,
        }


@dataclass(frozen=True, slots=True)
class ModelActionContract:
    """声明动作、归一化、mask 与 horizon 策略。"""

    representation: str
    normalization: str
    horizon_policy: str
    mask_policy: str
    relative_semantics_scope: str

    def __post_init__(self) -> None:
        """拒绝未定义动作字段。"""

        for name in (
            "representation",
            "normalization",
            "horizon_policy",
            "mask_policy",
            "relative_semantics_scope",
        ):
            _require_text(getattr(self, name), name)

    def to_json_dict(self) -> dict[str, str]:
        """返回稳定 JSON 结构。"""

        return {
            "representation": self.representation,
            "normalization": self.normalization,
            "horizon_policy": self.horizon_policy,
            "mask_policy": self.mask_policy,
            "relative_semantics_scope": self.relative_semantics_scope,
        }


@dataclass(frozen=True, slots=True)
class ComponentFactoryPaths:
    """保存不触发导入的规范组件工厂身份。"""

    config: str
    processor: str | None
    backbone: str | None
    action_head: str | None
    model: str | None
    checkpoint: str | None

    def __post_init__(self) -> None:
        """校验每个工厂使用 ``module:symbol``。"""

        for name, path in (
            ("config", self.config),
            ("processor", self.processor),
            ("backbone", self.backbone),
            ("action_head", self.action_head),
            ("model", self.model),
            ("checkpoint", self.checkpoint),
        ):
            if path is not None and (":" not in path or path.startswith(":") or path.endswith(":")):
                raise ValueError(f"{name} factory must use module:symbol identity")

    def to_json_dict(self) -> dict[str, str | None]:
        """返回稳定 JSON 结构。"""

        return {
            "config": self.config,
            "processor": self.processor,
            "backbone": self.backbone,
            "action_head": self.action_head,
            "model": self.model,
            "checkpoint": self.checkpoint,
        }


def _compatibility_shape() -> ModelShapeContract:
    """为历史测试元数据提供非生产占位形状。"""

    return ModelShapeContract(1, 1, 1)


def _compatibility_inputs() -> ModelInputContract:
    """为历史测试元数据提供最小输入声明。"""

    return ModelInputContract(("compatibility_input",), 1, False, "compatibility_only")


def _compatibility_action() -> ModelActionContract:
    """为历史测试元数据提供最小动作声明。"""

    return ModelActionContract(
        "compatibility_only",
        "capability_governed",
        "compatibility_only",
        "capability_governed",
        "none",
    )


def _compatibility_factories() -> ComponentFactoryPaths:
    """为历史测试元数据提供无执行工厂声明。"""

    return ComponentFactoryPaths(
        "autovla.models.families.specification:ModelFamilyDefinition",
        None,
        None,
        None,
        None,
        None,
    )


@dataclass(frozen=True, slots=True)
class ModelFamilyDefinition:
    """模型族身份、来源、架构和运行时支持的唯一事实源。"""

    family_key: str
    display_name: str
    license: LicenseSpec
    upstream_reference: str
    embodiment: tuple[str, ...]
    env_profiles: tuple[EnvProfile, ...]
    capabilities: ModelCapabilities
    runtime_support: RuntimeSupportState = RuntimeSupportState.UNSUPPORTED
    shape: ModelShapeContract = field(default_factory=_compatibility_shape)
    inputs: ModelInputContract = field(default_factory=_compatibility_inputs)
    action: ModelActionContract = field(default_factory=_compatibility_action)
    factories: ComponentFactoryPaths = field(default_factory=_compatibility_factories)
    asset_keys: tuple[str, ...] = ("compatibility_metadata_only",)
    checkpoint_layout: str = "compatibility_metadata_only"
    supported_precisions: tuple[str, ...] = ("metadata_only",)
    supported_topologies: tuple[str, ...] = ("metadata_only",)
    local_files_only: bool = True
    optional_extra: str | None = None
    compatibility_aliases: tuple[str, ...] = ()
    reuse: tuple[OpenSourceReuseSpec, ...] = ()
    source_status: str = "architecture_defined"
    validation_status: str = "runtime_deferred"
    transform_requirements: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        """校验定义闭合、别名唯一且执行声明与工厂一致。"""

        for name in ("family_key", "display_name", "upstream_reference", "checkpoint_layout"):
            _require_text(getattr(self, name), name)
        if not self.embodiment or not self.env_profiles:
            raise ValueError("embodiment and env_profiles must not be empty")
        if not self.asset_keys or len(set(self.asset_keys)) != len(self.asset_keys):
            raise ValueError("asset_keys must be non-empty and unique")
        if not self.supported_precisions or not self.supported_topologies:
            raise ValueError("precision and topology contracts must not be empty")
        aliases = self.compatibility_aliases
        if len(set(aliases)) != len(aliases):
            raise ValueError("compatibility aliases must be unique")
        executable_factories = (
            self.factories.processor,
            self.factories.backbone,
            self.factories.action_head,
            self.factories.model,
        )
        if self.runtime_support is RuntimeSupportState.EXECUTABLE and any(
            path is None for path in executable_factories
        ):
            raise ValueError("executable family requires every component factory")
        if (
            self.runtime_support is RuntimeSupportState.ARCHITECTURE_DEFINED_RUNTIME_DEFERRED
            and any(path is not None for path in executable_factories)
        ):
            raise ValueError("runtime-deferred family must not expose executable factories")
        if not self.local_files_only:
            raise ValueError("production model definitions must remain local_files_only")

    @property
    def fingerprint(self) -> str:
        """返回定义内容的稳定 SHA256。"""

        encoded = json.dumps(
            self.to_json_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @property
    def factory_path(self) -> str | None:
        """返回组合模型工厂兼容字段。"""

        return self.factories.model

    @property
    def runtime_supported(self) -> bool:
        """返回旧布尔运行时字段。"""

        return self.runtime_support is RuntimeSupportState.EXECUTABLE

    @property
    def action_horizon(self) -> int:
        """返回兼容动作 horizon。"""

        return self.shape.action_horizon

    @property
    def max_state_dim(self) -> int:
        """返回兼容状态维度。"""

        return self.shape.state_dimension

    @property
    def max_action_dim(self) -> int:
        """返回兼容动作维度。"""

        return self.shape.action_dimension

    @property
    def modality_inputs(self) -> tuple[str, ...]:
        """返回旧输入模态摘要。"""

        return ("language", "image_views", "proprioception/state")

    @property
    def action_output(self) -> str:
        """返回旧动作输出摘要。"""

        if self.capabilities.action.representation is ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK:
            return "continuous action chunk"
        return self.action.representation

    @property
    def processor_family(self) -> str:
        """返回旧 processor 身份。"""

        return self.capabilities.processor.identity

    @property
    def backbone_family(self) -> str:
        """返回旧 backbone 身份。"""

        return self.capabilities.backbone.identity

    @property
    def action_head_family(self) -> str:
        """返回旧 action-head 身份。"""

        return self.capabilities.action_head.identity

    @property
    def runtime_status(self) -> tuple[str, ...]:
        """返回旧运行时状态摘要。"""

        if self.capabilities.execution.mode is ExecutionMode.DETERMINISTIC_TEST_ONLY:
            return ("deterministic_test_only",)
        return (self.runtime_support.value,)

    @property
    def normalization_support(self) -> str:
        """返回旧归一化摘要。"""

        if self.capabilities.normalization.mode is NormalizationMode.IDENTITY:
            return "supported_identity_only"
        if self.capabilities.normalization.mode is NormalizationMode.STATISTICS_GOVERNED:
            return "statistics_governed"
        return "unverified"

    @property
    def no_weight_load(self) -> bool:
        """兼容元数据副作用字段。"""

        return not self.capabilities.execution.permissions.asset_load

    @property
    def no_tokenizer_load(self) -> bool:
        """从能力权限派生 tokenizer 加载禁用标记。"""

        return not self.capabilities.execution.permissions.tokenizer_load

    @property
    def no_network(self) -> bool:
        """所有生产定义都禁止网络。"""

        return not self.capabilities.execution.permissions.network

    @property
    def no_checkpoint_download(self) -> bool:
        """从能力权限派生 checkpoint 加载禁用标记。"""

        return not self.capabilities.execution.permissions.checkpoint_load

    def to_json_dict(self) -> dict[str, object]:
        """返回完整稳定 JSON 结构。"""

        return {
            "family_key": self.family_key,
            "display_name": self.display_name,
            "license": self.license.to_json_dict(),
            "upstream_reference": self.upstream_reference,
            "embodiment": list(self.embodiment),
            "env_profiles": [profile.to_json_dict() for profile in self.env_profiles],
            "capabilities": self.capabilities.to_json_dict(),
            "runtime_support": self.runtime_support.value,
            "shape": self.shape.to_json_dict(),
            "inputs": self.inputs.to_json_dict(),
            "action": self.action.to_json_dict(),
            "factories": self.factories.to_json_dict(),
            "asset_keys": list(self.asset_keys),
            "checkpoint_layout": self.checkpoint_layout,
            "supported_precisions": list(self.supported_precisions),
            "supported_topologies": list(self.supported_topologies),
            "local_files_only": self.local_files_only,
            "optional_extra": self.optional_extra,
            "compatibility_aliases": list(self.compatibility_aliases),
            "reuse": [item.to_json_dict() for item in self.reuse],
            "source_status": self.source_status,
            "validation_status": self.validation_status,
            "transform_requirements": list(self.transform_requirements),
        }


# 旧公开名称保持类型身份,不再保留第二个实现。
ModelFamilySpec = ModelFamilyDefinition

__all__ = [
    "ComponentFactoryPaths",
    "LicenseSpec",
    "ModelActionContract",
    "ModelFamilyDefinition",
    "ModelFamilySpec",
    "ModelInputContract",
    "ModelShapeContract",
    "OpenSourceReuseSpec",
    "RuntimeSupportState",
]
