"""模型族唯一不可变定义及轻量架构契约。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import TypeAlias

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    ActionDimensionPolicy,
    ActionDistribution,
    ActionHorizonPolicy,
    ActionMaskPolicy,
    ActionRepresentation,
    CheckpointFormat,
    ExecutionMode,
    ImageResolutionPolicy,
    ModelCapabilities,
    NormalizationMode,
    NormalizationPolicy,
    PrecisionSupport,
    RelativeActionPolicy,
    RuntimeSupportLevel,
    StateConditioningPolicy,
    TopologySupport,
)

LicenseState: TypeAlias = str
ReuseMode: TypeAlias = str


def _require_text(value: str, name: str) -> None:
    """要求标识文本非空。"""

    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _require_exact_bool(value: object, name: str) -> None:
    """要求公开布尔契约拒绝整数和其他真值对象。"""

    if type(value) is not bool:
        raise TypeError(f"{name} must be an exact bool")


def _project_state_conditioning(value: str) -> StateConditioningPolicy:
    """把 M9 已注册字段窄投影为闭合集。"""

    mapping = {
        "compatibility_only": StateConditioningPolicy.UNVERIFIED,
        "continuous_last_state_with_embodiment_projection": (
            StateConditioningPolicy.CONTINUOUS_FEATURES
        ),
        "discrete_state_in_language_tokens": StateConditioningPolicy.DISCRETE_LANGUAGE_TOKENS,
        "continuous_state_projection": StateConditioningPolicy.CONTINUOUS_FEATURES,
        "continuous_state_suffix_token": StateConditioningPolicy.CONTINUOUS_FEATURES,
        "continuous_state_in_fast_token_prefix": StateConditioningPolicy.CONTINUOUS_FEATURES,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported state conditioning policy: {value}") from exc


def _project_action_representation(
    value: str,
) -> tuple[ActionRepresentation, ActionDistribution]:
    """把历史表示文本拆为表示与分布两个正交闭集。"""

    mapping = {
        "compatibility_only": (
            ActionRepresentation.UNVERIFIED,
            ActionDistribution.UNVERIFIED,
        ),
        "continuous_flow_matching_chunk": (
            ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK,
            ActionDistribution.FLOW_MATCHING,
        ),
        "autoregressive_fast_action_tokens": (
            ActionRepresentation.DISCRETE_TOKEN_SEQUENCE,
            ActionDistribution.AUTOREGRESSIVE_CATEGORICAL,
        ),
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported action representation: {value}") from exc


def _project_normalization(value: str) -> NormalizationPolicy:
    """把历史归一化名称投影到跨家族策略。"""

    mapping = {
        "capability_governed": NormalizationPolicy.UNVERIFIED,
        "r3_axis_aware_per_embodiment_statistics": NormalizationPolicy.FAMILY_STATISTICS,
        "r3_quantile_q01_q99": NormalizationPolicy.QUANTILE_STATISTICS,
        "r3_mean_std": NormalizationPolicy.MEAN_STD_STATISTICS,
        "r3_mean_std_zscore": NormalizationPolicy.MEAN_STD_STATISTICS,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported normalization policy: {value}") from exc


def _project_horizon(value: str) -> ActionHorizonPolicy:
    """把历史 horizon 文本投影到封闭来源策略。"""

    mapping = {
        "compatibility_only": ActionHorizonPolicy.UNVERIFIED,
        "fixed_50": ActionHorizonPolicy.FIXED_BY_FAMILY,
        "default_50_dataset_override_explicit": ActionHorizonPolicy.DATASET_CONFIGURED,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported action horizon policy: {value}") from exc


def _project_mask(value: str) -> ActionMaskPolicy:
    """把历史 mask 文本投影到可组合语义。"""

    mapping = {
        "capability_governed": ActionMaskPolicy.UNVERIFIED,
        "strict_bool_same_shape_B_T_D": ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE,
        "dataset_padding_and_statistics_contract": ActionMaskPolicy.DATASET_PADDING_VALIDITY,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported action mask policy: {value}") from exc


def _project_relative_action(value: str) -> RelativeActionPolicy:
    """把历史相对动作范围投影到共享策略。"""

    mapping = {
        "none": RelativeActionPolicy.ABSOLUTE,
        "per_embodiment_per_modality_fixed_last_state_reference": (
            RelativeActionPolicy.CURRENT_STATE
        ),
        "dataset_or_embodiment_transform_plan_only": RelativeActionPolicy.EMBODIMENT_TRANSFORM_PLAN,
    }
    try:
        return mapping[value]
    except KeyError as exc:
        raise ValueError(f"unsupported relative action policy: {value}") from exc


class RuntimeSupportState(str, Enum):
    """描述模型族运行时支持的封闭状态。"""

    EXECUTABLE = "executable"
    ARCHITECTURE_DEFINED_RUNTIME_DEFERRED = "architecture_defined_runtime_deferred"
    ASSET_REQUIRED = "asset_required"
    OPTIONAL_DEPENDENCY_REQUIRED = "optional_dependency_required"
    UNSUPPORTED = "unsupported"


class DependencyClass(str, Enum):
    """区分模型族依赖在生产生命周期中的用途。"""

    MANDATORY_RUNTIME = "mandatory_runtime"
    OPTIONAL_FAMILY = "optional_family"
    REFERENCE_ONLY = "reference_only"
    CONVERSION_ONLY = "conversion_only"
    GPU_EXTENSION = "gpu_extension"


@dataclass(frozen=True, slots=True)
class DependencyRequirement:
    """声明一个模块的用途、版本边界与显式不兼容项。"""

    module: str
    dependency_class: DependencyClass
    version_specifier: str | None = None
    incompatible_with: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """拒绝空模块、重复冲突和自冲突。"""

        _require_text(self.module, "dependency module")
        if type(self.dependency_class) is not DependencyClass:
            raise TypeError("dependency_class must use DependencyClass")
        if self.version_specifier is not None:
            _require_text(self.version_specifier, "dependency version_specifier")
        if len(set(self.incompatible_with)) != len(self.incompatible_with):
            raise ValueError("dependency incompatibilities must be unique")
        if self.module in self.incompatible_with:
            raise ValueError("dependency cannot be incompatible with itself")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定依赖声明。"""

        return {
            "module": self.module,
            "dependency_class": self.dependency_class.value,
            "version_specifier": self.version_specifier,
            "incompatible_with": list(self.incompatible_with),
        }


@dataclass(frozen=True, slots=True)
class ModelDependencyRequirements:
    """保存模型族拥有的闭合依赖集合。"""

    items: tuple[DependencyRequirement, ...] = ()

    def __post_init__(self) -> None:
        """要求模块身份唯一, 避免覆盖式依赖解释。"""

        if type(self.items) is not tuple or any(
            type(item) is not DependencyRequirement for item in self.items
        ):
            raise TypeError("model dependencies must be DependencyRequirement tuples")
        modules = tuple(item.module for item in self.items)
        if len(set(modules)) != len(modules):
            raise ValueError("model dependency modules must be unique")

    def for_class(self, value: DependencyClass) -> tuple[DependencyRequirement, ...]:
        """按依赖用途返回稳定子集。"""

        return tuple(item for item in self.items if item.dependency_class is value)

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定依赖集合。"""

        return {"items": [item.to_json_dict() for item in self.items]}


@dataclass(frozen=True, slots=True)
class ModelAssetRequirement:
    """声明家族资产角色与是否为执行硬门。"""

    role: str
    asset_key: str
    required_for_runtime: bool = True

    def __post_init__(self) -> None:
        """拒绝空资产身份。"""

        _require_text(self.role, "asset role")
        _require_text(self.asset_key, "asset key")
        _require_exact_bool(self.required_for_runtime, "required_for_runtime")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定资产需求。"""

        return {
            "role": self.role,
            "asset_key": self.asset_key,
            "required_for_runtime": self.required_for_runtime,
        }


@dataclass(frozen=True, slots=True)
class ModelCheckpointDefinition:
    """声明 checkpoint 格式、命名空间布局及转换边界。"""

    checkpoint_format: CheckpointFormat
    layout: str
    immutable_base_asset: bool = True
    conversion_required: bool = False

    def __post_init__(self) -> None:
        """要求 checkpoint 布局可审计。"""

        _require_text(self.layout, "checkpoint layout")
        if type(self.checkpoint_format) is not CheckpointFormat:
            raise TypeError("checkpoint_format must use CheckpointFormat")
        _require_exact_bool(self.immutable_base_asset, "immutable_base_asset")
        _require_exact_bool(self.conversion_required, "conversion_required")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 checkpoint 声明。"""

        return {
            "format": self.checkpoint_format.value,
            "layout": self.layout,
            "immutable_base_asset": self.immutable_base_asset,
            "conversion_required": self.conversion_required,
        }


@dataclass(frozen=True, slots=True)
class TransformRequirement:
    """声明共享变换语义键及逆变换要求。"""

    semantic_key: str
    inverse_required: bool = False

    def __post_init__(self) -> None:
        """拒绝空变换语义键。"""

        _require_text(self.semantic_key, "transform semantic key")
        _require_exact_bool(self.inverse_required, "inverse_required")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定变换需求。"""

        return {
            "semantic_key": self.semantic_key,
            "inverse_required": self.inverse_required,
        }


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceState:
    """分别记录来源、装配资格与证据支持的运行就绪状态。"""

    source_architecture_complete: bool = False
    assembly_eligible: bool = False
    runtime_ready: bool = False
    official_asset_bundle_available: bool = False
    official_checkpoint_load_validated: bool = False
    official_checkpoint_loaded_tensor_count: int = 0
    official_checkpoint_missing_key_count: int = 0
    official_checkpoint_unexpected_key_count: int = 0
    official_checkpoint_shape_mismatch_count: int = 0
    checkpoint_load_device: str | None = None
    accepted_evidence: tuple[str, ...] = ()
    single_gpu_validated: bool = False
    ddp_validated: bool = False
    deepspeed_zero_1_validated: bool = False
    deepspeed_zero_2_validated: bool = False
    deepspeed_zero_3_validated: bool = False
    cross_node_validated: bool = False
    inference_validated: bool = False

    def __post_init__(self) -> None:
        """关闭布尔、计数与证据依赖,避免来源完整性冒充运行就绪。"""

        for name in (
            "source_architecture_complete",
            "assembly_eligible",
            "runtime_ready",
            "official_asset_bundle_available",
            "official_checkpoint_load_validated",
            "single_gpu_validated",
            "ddp_validated",
            "deepspeed_zero_1_validated",
            "deepspeed_zero_2_validated",
            "deepspeed_zero_3_validated",
            "cross_node_validated",
            "inference_validated",
        ):
            value = getattr(self, name)
            _require_exact_bool(value, name)
        counts = (
            self.official_checkpoint_loaded_tensor_count,
            self.official_checkpoint_missing_key_count,
            self.official_checkpoint_unexpected_key_count,
            self.official_checkpoint_shape_mismatch_count,
        )
        if any(type(value) is not int or value < 0 for value in counts):
            raise ValueError("checkpoint evidence counts must be non-negative integers")
        if len(set(self.accepted_evidence)) != len(self.accepted_evidence) or any(
            not item.strip() for item in self.accepted_evidence
        ):
            raise ValueError("accepted_evidence must contain unique non-empty identifiers")
        if self.assembly_eligible and not (
            self.source_architecture_complete and self.official_asset_bundle_available
        ):
            raise ValueError("assembly eligibility requires complete source and verified assets")
        if self.runtime_ready and not self.assembly_eligible:
            raise ValueError("runtime readiness requires assembly eligibility")
        if self.official_checkpoint_load_validated:
            if not self.assembly_eligible or self.official_checkpoint_loaded_tensor_count <= 0:
                raise ValueError("validated checkpoint load requires eligible assembly and tensors")
            if any(counts[1:]):
                raise ValueError("validated checkpoint load must be strict and mismatch-free")
            if self.checkpoint_load_device is None or not self.checkpoint_load_device.strip():
                raise ValueError("validated checkpoint load requires a device identity")
        elif self.checkpoint_load_device is not None or any(counts):
            raise ValueError("unvalidated checkpoint load must not publish device or counts")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定证据状态。"""

        return {
            "source_architecture_complete": self.source_architecture_complete,
            "assembly_eligible": self.assembly_eligible,
            "runtime_ready": self.runtime_ready,
            "official_asset_bundle_available": self.official_asset_bundle_available,
            "official_checkpoint_load_validated": self.official_checkpoint_load_validated,
            "official_checkpoint_loaded_tensor_count": self.official_checkpoint_loaded_tensor_count,
            "official_checkpoint_missing_key_count": self.official_checkpoint_missing_key_count,
            "official_checkpoint_unexpected_key_count": (
                self.official_checkpoint_unexpected_key_count
            ),
            "official_checkpoint_shape_mismatch_count": (
                self.official_checkpoint_shape_mismatch_count
            ),
            "checkpoint_load_device": self.checkpoint_load_device,
            "accepted_evidence": list(self.accepted_evidence),
            "single_gpu_validated": self.single_gpu_validated,
            "ddp_validated": self.ddp_validated,
            "deepspeed_zero_1_validated": self.deepspeed_zero_1_validated,
            "deepspeed_zero_2_validated": self.deepspeed_zero_2_validated,
            "deepspeed_zero_3_validated": self.deepspeed_zero_3_validated,
            "cross_node_validated": self.cross_node_validated,
            "inference_validated": self.inference_validated,
        }


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
        _require_exact_bool(self.copied_or_adapted_code, "copied_or_adapted_code")
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
    state_conditioning: StateConditioningPolicy | str
    max_language_tokens: int | None = None
    image_resolution_policy: ImageResolutionPolicy = ImageResolutionPolicy.FIXED_BY_FAMILY

    def __post_init__(self) -> None:
        """校验输入模态次序和边界。"""

        if type(self.cameras) is not tuple or any(type(item) is not str for item in self.cameras):
            raise TypeError("input cameras must be a tuple of strings")
        if not self.cameras or len(set(self.cameras)) != len(self.cameras):
            raise ValueError("input cameras must be non-empty and unique")
        if type(self.image_size) is not int or self.image_size <= 0:
            raise ValueError("input image size must be defined")
        _require_exact_bool(self.language_required, "language_required")
        object.__setattr__(
            self,
            "state_conditioning",
            _validated_state_conditioning(self.state_conditioning),
        )
        if self.max_language_tokens is not None and (
            type(self.max_language_tokens) is not int or self.max_language_tokens <= 0
        ):
            raise ValueError("max_language_tokens must be positive")
        if type(self.image_resolution_policy) is not ImageResolutionPolicy:
            raise TypeError("image_resolution_policy must use ImageResolutionPolicy")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 结构。"""

        state_conditioning = _validated_state_conditioning(self.state_conditioning)

        return {
            "cameras": list(self.cameras),
            "image_size": self.image_size,
            "language_required": self.language_required,
            "state_conditioning": state_conditioning.value,
            "max_language_tokens": self.max_language_tokens,
            "image_resolution_policy": self.image_resolution_policy.value,
        }


@dataclass(frozen=True, slots=True)
class ModelActionContract:
    """声明动作、归一化、mask 与 horizon 策略。"""

    representation: ActionRepresentation | str
    normalization: NormalizationPolicy | str
    horizon_policy: ActionHorizonPolicy | str
    mask_policy: ActionMaskPolicy | str
    relative_semantics_scope: RelativeActionPolicy | str
    distribution: ActionDistribution = ActionDistribution.UNVERIFIED
    dimension_policy: ActionDimensionPolicy = ActionDimensionPolicy.UNVERIFIED

    def __post_init__(self) -> None:
        """拒绝未定义动作字段。"""

        legacy_representation = self.representation
        if type(legacy_representation) is str:
            representation, distribution = _project_action_representation(legacy_representation)
            object.__setattr__(self, "representation", representation)
            if self.distribution is ActionDistribution.UNVERIFIED:
                object.__setattr__(self, "distribution", distribution)
        if type(self.normalization) is str:
            object.__setattr__(self, "normalization", _project_normalization(self.normalization))
        if type(self.horizon_policy) is str:
            object.__setattr__(self, "horizon_policy", _project_horizon(self.horizon_policy))
        if type(self.mask_policy) is str:
            object.__setattr__(self, "mask_policy", _project_mask(self.mask_policy))
        if type(self.relative_semantics_scope) is str:
            object.__setattr__(
                self,
                "relative_semantics_scope",
                _project_relative_action(self.relative_semantics_scope),
            )
        if self.dimension_policy is ActionDimensionPolicy.UNVERIFIED:
            object.__setattr__(
                self,
                "dimension_policy",
                ActionDimensionPolicy.EMBODIMENT_WITH_FAMILY_PADDING,
            )
        _validate_action_contract_enums(self)

    def to_json_dict(self) -> dict[str, str]:
        """返回稳定 JSON 结构。"""

        representation = _validated_action_representation(self.representation)
        normalization = _validated_normalization(self.normalization)
        horizon_policy = _validated_horizon_policy(self.horizon_policy)
        mask_policy = _validated_mask_policy(self.mask_policy)
        relative_policy = _validated_relative_policy(self.relative_semantics_scope)

        return {
            "representation": representation.value,
            "distribution": self.distribution.value,
            "normalization": normalization.value,
            "horizon_policy": horizon_policy.value,
            "dimension_policy": self.dimension_policy.value,
            "mask_policy": mask_policy.value,
            "relative_semantics_scope": relative_policy.value,
        }


def _validated_state_conditioning(
    value: StateConditioningPolicy | str,
) -> StateConditioningPolicy:
    """投影旧字符串并拒绝所有其他运行时值。"""

    if type(value) is str:
        return _project_state_conditioning(value)
    if type(value) is not StateConditioningPolicy:
        raise TypeError("state_conditioning must use StateConditioningPolicy")
    return value


def _validated_action_representation(
    value: ActionRepresentation | str,
) -> ActionRepresentation:
    """返回已关闭的动作表示。"""

    if type(value) is not ActionRepresentation:
        raise TypeError("representation must use ActionRepresentation")
    return value


def _validated_normalization(value: NormalizationPolicy | str) -> NormalizationPolicy:
    """返回已关闭的归一化策略。"""

    if type(value) is not NormalizationPolicy:
        raise TypeError("normalization must use NormalizationPolicy")
    return value


def _validated_horizon_policy(value: ActionHorizonPolicy | str) -> ActionHorizonPolicy:
    """返回已关闭的 horizon 策略。"""

    if type(value) is not ActionHorizonPolicy:
        raise TypeError("horizon_policy must use ActionHorizonPolicy")
    return value


def _validated_mask_policy(value: ActionMaskPolicy | str) -> ActionMaskPolicy:
    """返回已关闭的 mask 策略。"""

    if type(value) is not ActionMaskPolicy:
        raise TypeError("mask_policy must use ActionMaskPolicy")
    return value


def _validated_relative_policy(value: RelativeActionPolicy | str) -> RelativeActionPolicy:
    """返回已关闭的相对动作策略。"""

    if type(value) is not RelativeActionPolicy:
        raise TypeError("relative_semantics_scope must use RelativeActionPolicy")
    return value


def _validate_action_contract_enums(contract: ModelActionContract) -> None:
    """集中校验动作契约的全部闭集字段。"""

    _validated_action_representation(contract.representation)
    _validated_normalization(contract.normalization)
    _validated_horizon_policy(contract.horizon_policy)
    _validated_mask_policy(contract.mask_policy)
    _validated_relative_policy(contract.relative_semantics_scope)
    if type(contract.distribution) is not ActionDistribution:
        raise TypeError("distribution must use ActionDistribution")
    if type(contract.dimension_policy) is not ActionDimensionPolicy:
        raise TypeError("dimension_policy must use ActionDimensionPolicy")


@dataclass(frozen=True, slots=True)
class ComponentFactoryPaths:
    """保存不触发导入的规范组件工厂身份。"""

    config: str
    processor: str | None
    backbone: str | None
    action_head: str | None
    model: str | None
    checkpoint: str | None
    asset_bundle: str | None = None
    policy_bundle: str | None = None

    def __post_init__(self) -> None:
        """校验每个工厂使用 ``module:symbol``。"""

        for name, path in (
            ("config", self.config),
            ("processor", self.processor),
            ("backbone", self.backbone),
            ("action_head", self.action_head),
            ("model", self.model),
            ("checkpoint", self.checkpoint),
            ("asset_bundle", self.asset_bundle),
            ("policy_bundle", self.policy_bundle),
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
            "asset_bundle": self.asset_bundle,
            "policy_bundle": self.policy_bundle,
        }


@dataclass(frozen=True, slots=True)
class ModelAssemblyRequirements:
    """聚合家族拥有的工厂、依赖、资产、变换和运行时证据。"""

    factories: ComponentFactoryPaths
    dependencies: ModelDependencyRequirements
    assets: tuple[ModelAssetRequirement, ...]
    checkpoint: ModelCheckpointDefinition
    transforms: tuple[TransformRequirement, ...]
    precisions: tuple[PrecisionSupport, ...]
    topologies: tuple[TopologySupport, ...]
    runtime_level: RuntimeSupportLevel
    evidence: RuntimeEvidenceState = RuntimeEvidenceState()

    def __post_init__(self) -> None:
        """拒绝重复资产、变换、精度和拓扑声明。"""

        groups = (
            tuple(item.role for item in self.assets),
            tuple(item.semantic_key for item in self.transforms),
            self.precisions,
            self.topologies,
        )
        if any(len(group) != len(set(group)) for group in groups):
            raise ValueError("assembly requirements must use unique identities")
        if not self.precisions or not self.topologies:
            raise ValueError("assembly requirements need precision and topology contracts")
        if any(type(item) is not PrecisionSupport for item in self.precisions):
            raise TypeError("assembly precisions must use PrecisionSupport")
        if any(type(item) is not TopologySupport for item in self.topologies):
            raise TypeError("assembly topologies must use TopologySupport")
        if type(self.runtime_level) is not RuntimeSupportLevel:
            raise TypeError("assembly runtime_level must use RuntimeSupportLevel")
        if type(self.evidence) is not RuntimeEvidenceState:
            raise TypeError("assembly evidence must use RuntimeEvidenceState")

    def to_json_dict(self) -> dict[str, object]:
        """返回完整稳定装配要求。"""

        return {
            "factories": self.factories.to_json_dict(),
            "dependencies": self.dependencies.to_json_dict(),
            "assets": [item.to_json_dict() for item in self.assets],
            "checkpoint": self.checkpoint.to_json_dict(),
            "transforms": [item.to_json_dict() for item in self.transforms],
            "precisions": [item.value for item in self.precisions],
            "topologies": [item.value for item in self.topologies],
            "runtime_level": self.runtime_level.value,
            "evidence": self.evidence.to_json_dict(),
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


def _project_precision(value: str) -> PrecisionSupport:
    """把现有精度字段窄投影到闭合集。"""

    if value == "metadata_only":
        return PrecisionSupport.METADATA_ONLY
    try:
        return PrecisionSupport(value)
    except ValueError as exc:
        raise ValueError(f"unsupported precision contract: {value}") from exc


def _project_topology(value: str) -> TopologySupport:
    """把现有拓扑字段窄投影到闭合集。"""

    if value in {"architecture_metadata_only", "metadata_only"}:
        return TopologySupport.METADATA_ONLY
    try:
        return TopologySupport(value)
    except ValueError as exc:
        raise ValueError(f"unsupported topology contract: {value}") from exc


def _project_runtime_level(value: RuntimeSupportState) -> RuntimeSupportLevel:
    """把历史运行时状态投影到证据级别。"""

    mapping = {
        # 历史 executable 只表示可进入本地装配, 不能替代 M10 官方资产实测证据。
        RuntimeSupportState.EXECUTABLE: RuntimeSupportLevel.ASSET_GATED,
        RuntimeSupportState.ARCHITECTURE_DEFINED_RUNTIME_DEFERRED: (
            RuntimeSupportLevel.ARCHITECTURE_ONLY
        ),
        RuntimeSupportState.ASSET_REQUIRED: RuntimeSupportLevel.ASSET_GATED,
        RuntimeSupportState.OPTIONAL_DEPENDENCY_REQUIRED: RuntimeSupportLevel.DEPENDENCY_GATED,
        RuntimeSupportState.UNSUPPORTED: RuntimeSupportLevel.UNSUPPORTED,
    }
    return mapping[value]


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
    assembly_requirements: ModelAssemblyRequirements | None = None

    def __post_init__(self) -> None:
        """校验定义闭合、别名唯一且执行声明与工厂一致。"""

        for name in ("family_key", "display_name", "upstream_reference", "checkpoint_layout"):
            _require_text(getattr(self, name), name)
        _require_exact_bool(self.local_files_only, "local_files_only")
        if type(self.runtime_support) is not RuntimeSupportState:
            raise TypeError("runtime_support must use RuntimeSupportState")
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
        if self.assembly_requirements is None:
            checkpoint_format = (
                CheckpointFormat.SAFETENSORS
                if "safetensors" in self.checkpoint_layout
                else CheckpointFormat.METADATA_ONLY
            )
            projected = ModelAssemblyRequirements(
                factories=self.factories,
                dependencies=ModelDependencyRequirements(),
                assets=tuple(
                    ModelAssetRequirement(role=key, asset_key=key) for key in self.asset_keys
                ),
                checkpoint=ModelCheckpointDefinition(
                    checkpoint_format=checkpoint_format,
                    layout=self.checkpoint_layout,
                    conversion_required="conversion" in self.checkpoint_layout,
                ),
                transforms=tuple(
                    TransformRequirement(item, inverse_required="inverse" in item)
                    for item in self.transform_requirements
                ),
                precisions=tuple(_project_precision(item) for item in self.supported_precisions),
                topologies=tuple(_project_topology(item) for item in self.supported_topologies),
                runtime_level=_project_runtime_level(self.runtime_support),
            )
            object.__setattr__(self, "assembly_requirements", projected)
        elif self.assembly_requirements.factories != self.factories:
            raise ValueError("assembly factory paths must match the canonical family factories")

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
        """返回证据支持的运行就绪状态,不再把可装配性当作运行证明。"""

        requirements = self.assembly_requirements
        return requirements is not None and requirements.evidence.runtime_ready

    @property
    def assembly_eligible(self) -> bool:
        """返回来源与本地资产是否足以进入共享装配。"""

        requirements = self.assembly_requirements
        return requirements is not None and requirements.evidence.assembly_eligible

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

        requirements = self.assembly_requirements
        if requirements is None:
            raise RuntimeError("assembly requirements projection was not finalized")

        return {
            "family_key": self.family_key,
            "display_name": self.display_name,
            "license": self.license.to_json_dict(),
            "upstream_reference": self.upstream_reference,
            "embodiment": list(self.embodiment),
            "env_profiles": [profile.to_json_dict() for profile in self.env_profiles],
            "capabilities": self.capabilities.to_json_dict(),
            "runtime_support": self.runtime_support.value,
            "assembly_eligible": requirements.evidence.assembly_eligible,
            "runtime_ready": requirements.evidence.runtime_ready,
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
            "assembly_requirements": requirements.to_json_dict(),
        }


@dataclass(frozen=True, slots=True)
class ModelZooContract:
    """声明 M10 活跃、延后家族及后端决策字面量。"""

    active_family_keys: tuple[str, ...] = ("gr00t_n1d6", "gr00t_n1d7", "pi0_5")
    deferred_family_keys: tuple[str, ...] = ("pi0", "pi0_fast")
    backend_decision: str = "NO_BACKEND_WINNER"

    def __post_init__(self) -> None:
        """拒绝家族集合重叠或决策字面量漂移。"""

        if self.active_family_keys != ("gr00t_n1d6", "gr00t_n1d7", "pi0_5"):
            raise ValueError("M10 active family keys are a closed ordered contract")
        if self.deferred_family_keys != ("pi0", "pi0_fast"):
            raise ValueError("M10 deferred family keys are a closed ordered contract")
        if set(self.active_family_keys) & set(self.deferred_family_keys):
            raise ValueError("active and deferred model families must be disjoint")
        if self.backend_decision != "NO_BACKEND_WINNER":
            raise ValueError("backend decision must preserve NO_BACKEND_WINNER")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定模型动物园契约。"""

        return {
            "active_family_keys": list(self.active_family_keys),
            "deferred_family_keys": list(self.deferred_family_keys),
            "backend_decision": self.backend_decision,
        }


M10_MODEL_ZOO_CONTRACT = ModelZooContract()


# 旧公开名称保持类型身份,不再保留第二个实现。
ModelFamilySpec = ModelFamilyDefinition

__all__ = [
    "M10_MODEL_ZOO_CONTRACT",
    "ComponentFactoryPaths",
    "DependencyClass",
    "DependencyRequirement",
    "LicenseSpec",
    "ModelActionContract",
    "ModelAssemblyRequirements",
    "ModelAssetRequirement",
    "ModelCheckpointDefinition",
    "ModelDependencyRequirements",
    "ModelFamilyDefinition",
    "ModelFamilySpec",
    "ModelInputContract",
    "ModelShapeContract",
    "ModelZooContract",
    "OpenSourceReuseSpec",
    "RuntimeEvidenceState",
    "RuntimeSupportState",
    "TransformRequirement",
]
