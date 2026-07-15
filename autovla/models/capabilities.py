"""模型族执行与输入边界的不可变结构化能力契约。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class SupportState(str, Enum):
    """声明能力证据状态。"""

    SUPPORTED = "supported"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class ComponentRole(str, Enum):
    """限制组件描述符所属角色。"""

    PROCESSOR = "processor"
    BACKBONE = "backbone"
    ACTION_HEAD = "action_head"


class StatePolicy(str, Enum):
    """声明状态输入要求。"""

    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"
    UNVERIFIED = "unverified"


class ActionRepresentation(str, Enum):
    """声明动作表示。"""

    CONTINUOUS_NUMERIC_CHUNK = "continuous_numeric_chunk"
    UNVERIFIED = "unverified"


class ActionShapePolicy(str, Enum):
    """声明动作形状来源。"""

    CONFIGURED_BATCH_HORIZON_DIM = "configured_batch_horizon_dim"
    UNVERIFIED = "unverified"


class ActionMaskPolicy(str, Enum):
    """声明动作 mask 语义。"""

    STRICT_BOOL_SAME_SHAPE = "strict_bool_same_shape"
    UNVERIFIED = "unverified"


class NormalizationMode(str, Enum):
    """声明归一化策略。"""

    IDENTITY = "identity"
    STATISTICS_GOVERNED = "statistics_governed"
    UNSPECIFIED = "unspecified"


class ExecutionMode(str, Enum):
    """声明模型族可进入的执行边界。"""

    DETERMINISTIC_TEST_ONLY = "deterministic_test_only"
    METADATA_ONLY = "metadata_only"
    PRODUCTION_GPU = "production_gpu"


@dataclass(frozen=True, slots=True)
class ComponentDescriptor:
    """以闭集角色和支持状态描述单个模型组件。"""

    role: ComponentRole
    identity: str
    support: SupportState

    def __post_init__(self) -> None:
        """拒绝空组件身份。"""
        if not self.identity.strip():
            raise ValueError(f"{self.role.value} identity must not be empty")

    def to_json_dict(self) -> dict[str, str]:
        """返回稳定 JSON 表示。"""
        return {
            "identity": self.identity,
            "role": self.role.value,
            "support": self.support.value,
        }


@dataclass(frozen=True, slots=True)
class InputCapabilities:
    """描述图像、语言和状态输入要求。"""

    image_support: SupportState
    required_cameras: tuple[str, ...]
    language_required: bool
    state_policy: StatePolicy

    def __post_init__(self) -> None:
        """校验相机名唯一且使用规范 camera.rgb_N 形式。"""
        if len(self.required_cameras) != len(set(self.required_cameras)):
            raise ValueError("required_cameras must not contain duplicates")
        for name in self.required_cameras:
            prefix = "camera.rgb_"
            if not name.startswith(prefix) or not name.removeprefix(prefix).isdigit():
                raise ValueError(f"noncanonical camera modality: {name}")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "image_support": self.image_support.value,
            "language_required": self.language_required,
            "required_cameras": list(self.required_cameras),
            "state_policy": self.state_policy.value,
        }


@dataclass(frozen=True, slots=True)
class ActionCapabilities:
    """描述动作表示、形状、horizon、维度和 mask 策略。"""

    representation: ActionRepresentation
    shape_policy: ActionShapePolicy
    mask_policy: ActionMaskPolicy
    fixed_horizon: int | None = None
    fixed_dimension: int | None = None

    def __post_init__(self) -> None:
        """校验固定动作形状成对出现且为正整数。"""
        if (self.fixed_horizon is None) != (self.fixed_dimension is None):
            raise ValueError("fixed action horizon and dimension must be declared together")
        for name, value in (
            ("fixed_horizon", self.fixed_horizon),
            ("fixed_dimension", self.fixed_dimension),
        ):
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive int")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "fixed_dimension": self.fixed_dimension,
            "fixed_horizon": self.fixed_horizon,
            "mask_policy": self.mask_policy.value,
            "representation": self.representation.value,
            "shape_policy": self.shape_policy.value,
        }


@dataclass(frozen=True, slots=True)
class NormalizationCapabilities:
    """描述归一化模式和外部统计要求。"""

    support: SupportState
    mode: NormalizationMode
    statistics_required: bool

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "mode": self.mode.value,
            "statistics_required": self.statistics_required,
            "support": self.support.value,
        }


@dataclass(frozen=True, slots=True)
class SideEffectPermissions:
    """显式声明运行时、网络和资产副作用权限。"""

    runtime_import: bool = False
    network: bool = False
    asset_load: bool = False
    checkpoint_load: bool = False
    tokenizer_load: bool = False
    real_training: bool = False

    def any_enabled(self) -> bool:
        """返回是否存在任一副作用权限。"""
        return any(
            (
                self.runtime_import,
                self.network,
                self.asset_load,
                self.checkpoint_load,
                self.tokenizer_load,
                self.real_training,
            )
        )

    def to_json_dict(self) -> dict[str, bool]:
        """返回稳定 JSON 表示。"""
        return {
            "asset_load": self.asset_load,
            "checkpoint_load": self.checkpoint_load,
            "network": self.network,
            "real_training": self.real_training,
            "runtime_import": self.runtime_import,
            "tokenizer_load": self.tokenizer_load,
        }


@dataclass(frozen=True, slots=True)
class ExecutionCapabilities:
    """描述执行模式、支持状态和副作用权限。"""

    mode: ExecutionMode
    support: SupportState
    permissions: SideEffectPermissions = SideEffectPermissions()

    @property
    def executable_test_double(self) -> bool:
        """仅对受支持的确定性 test-double 返回真。"""
        return (
            self.mode is ExecutionMode.DETERMINISTIC_TEST_ONLY
            and self.support is SupportState.SUPPORTED
        )

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "executable_test_double": self.executable_test_double,
            "mode": self.mode.value,
            "permissions": self.permissions.to_json_dict(),
            "support": self.support.value,
        }


@dataclass(frozen=True, slots=True)
class ModelCapabilities:
    """聚合模型族唯一结构化能力事实。"""

    processor: ComponentDescriptor
    backbone: ComponentDescriptor
    action_head: ComponentDescriptor
    inputs: InputCapabilities
    action: ActionCapabilities
    normalization: NormalizationCapabilities
    execution: ExecutionCapabilities

    def __post_init__(self) -> None:
        """拒绝角色错配、metadata 越权和非规范 test-double。"""
        expected_roles = (
            (self.processor, ComponentRole.PROCESSOR),
            (self.backbone, ComponentRole.BACKBONE),
            (self.action_head, ComponentRole.ACTION_HEAD),
        )
        for descriptor, role in expected_roles:
            if descriptor.role is not role:
                raise ValueError(f"{role.value} descriptor has the wrong role")
        if self.execution.mode is ExecutionMode.METADATA_ONLY:
            if any(
                descriptor.support is SupportState.SUPPORTED for descriptor, _ in expected_roles
            ):
                raise ValueError("metadata-only profiles cannot claim supported runtime components")
            if self.execution.permissions.any_enabled():
                raise ValueError("metadata-only profiles cannot allow runtime side effects")
        if self.execution.mode is ExecutionMode.DETERMINISTIC_TEST_ONLY:
            expected_cameras = ("camera.rgb_0", "camera.rgb_1", "camera.rgb_2")
            exact = (
                self.execution.support is SupportState.SUPPORTED
                and self.processor.support is SupportState.SUPPORTED
                and self.processor.identity == "identity_numpy_processor"
                and self.backbone.support is SupportState.UNSUPPORTED
                and self.backbone.identity == "none"
                and self.action_head.support is SupportState.SUPPORTED
                and self.action_head.identity == "deterministic_test_action_head"
                and self.inputs.image_support is SupportState.SUPPORTED
                and self.inputs.required_cameras == expected_cameras
                and self.inputs.language_required
                and self.inputs.state_policy is StatePolicy.REQUIRED
                and self.action.representation is ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK
                and self.action.shape_policy is ActionShapePolicy.CONFIGURED_BATCH_HORIZON_DIM
                and self.action.mask_policy is ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE
                and self.normalization.support is SupportState.SUPPORTED
                and self.normalization.mode is NormalizationMode.IDENTITY
                and not self.normalization.statistics_required
                and not self.execution.permissions.any_enabled()
            )
            if not exact:
                raise ValueError(
                    "deterministic test capability must match the exact test_double tuple"
                )

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "action": self.action.to_json_dict(),
            "action_head": self.action_head.to_json_dict(),
            "backbone": self.backbone.to_json_dict(),
            "execution": self.execution.to_json_dict(),
            "inputs": self.inputs.to_json_dict(),
            "normalization": self.normalization.to_json_dict(),
            "processor": self.processor.to_json_dict(),
        }


def build_test_double_capabilities() -> ModelCapabilities:
    """构造唯一受支持的本地 test-double 能力元组。"""
    return ModelCapabilities(
        processor=ComponentDescriptor(
            ComponentRole.PROCESSOR,
            "identity_numpy_processor",
            SupportState.SUPPORTED,
        ),
        backbone=ComponentDescriptor(
            ComponentRole.BACKBONE,
            "none",
            SupportState.UNSUPPORTED,
        ),
        action_head=ComponentDescriptor(
            ComponentRole.ACTION_HEAD,
            "deterministic_test_action_head",
            SupportState.SUPPORTED,
        ),
        inputs=InputCapabilities(
            image_support=SupportState.SUPPORTED,
            required_cameras=("camera.rgb_0", "camera.rgb_1", "camera.rgb_2"),
            language_required=True,
            state_policy=StatePolicy.REQUIRED,
        ),
        action=ActionCapabilities(
            representation=ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK,
            shape_policy=ActionShapePolicy.CONFIGURED_BATCH_HORIZON_DIM,
            mask_policy=ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE,
        ),
        normalization=NormalizationCapabilities(
            support=SupportState.SUPPORTED,
            mode=NormalizationMode.IDENTITY,
            statistics_required=False,
        ),
        execution=ExecutionCapabilities(
            mode=ExecutionMode.DETERMINISTIC_TEST_ONLY,
            support=SupportState.SUPPORTED,
        ),
    )


def build_unverified_capabilities(
    *,
    processor_identity: str,
    backbone_identity: str,
    action_head_identity: str,
    normalization_mode: NormalizationMode,
    statistics_required: bool,
    execution_mode: ExecutionMode = ExecutionMode.METADATA_ONLY,
) -> ModelCapabilities:
    """构造不授予执行权限的 metadata/roadmap 能力元组。"""
    return ModelCapabilities(
        processor=ComponentDescriptor(
            ComponentRole.PROCESSOR,
            processor_identity,
            SupportState.UNVERIFIED,
        ),
        backbone=ComponentDescriptor(
            ComponentRole.BACKBONE,
            backbone_identity,
            SupportState.UNVERIFIED,
        ),
        action_head=ComponentDescriptor(
            ComponentRole.ACTION_HEAD,
            action_head_identity,
            SupportState.UNVERIFIED,
        ),
        inputs=InputCapabilities(
            image_support=SupportState.UNVERIFIED,
            required_cameras=(),
            language_required=True,
            state_policy=StatePolicy.UNVERIFIED,
        ),
        action=ActionCapabilities(
            representation=ActionRepresentation.UNVERIFIED,
            shape_policy=ActionShapePolicy.UNVERIFIED,
            mask_policy=ActionMaskPolicy.UNVERIFIED,
        ),
        normalization=NormalizationCapabilities(
            support=SupportState.UNVERIFIED,
            mode=normalization_mode,
            statistics_required=statistics_required,
        ),
        execution=ExecutionCapabilities(
            mode=execution_mode,
            support=SupportState.UNVERIFIED,
        ),
    )


def build_gpu_family_capabilities(
    *,
    processor_identity: str,
    backbone_identity: str,
    action_head_identity: str,
    required_cameras: tuple[str, ...],
    action_horizon: int,
    action_dimension: int,
) -> ModelCapabilities:
    """构造已定义但仍受资产和依赖门控的 GPU 模型能力。"""

    return ModelCapabilities(
        processor=ComponentDescriptor(
            ComponentRole.PROCESSOR,
            processor_identity,
            SupportState.SUPPORTED,
        ),
        backbone=ComponentDescriptor(
            ComponentRole.BACKBONE,
            backbone_identity,
            SupportState.SUPPORTED,
        ),
        action_head=ComponentDescriptor(
            ComponentRole.ACTION_HEAD,
            action_head_identity,
            SupportState.SUPPORTED,
        ),
        inputs=InputCapabilities(
            image_support=SupportState.SUPPORTED,
            required_cameras=required_cameras,
            language_required=True,
            state_policy=StatePolicy.REQUIRED,
        ),
        action=ActionCapabilities(
            representation=ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK,
            shape_policy=ActionShapePolicy.CONFIGURED_BATCH_HORIZON_DIM,
            mask_policy=ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE,
            fixed_horizon=action_horizon,
            fixed_dimension=action_dimension,
        ),
        normalization=NormalizationCapabilities(
            support=SupportState.SUPPORTED,
            mode=NormalizationMode.STATISTICS_GOVERNED,
            statistics_required=True,
        ),
        execution=ExecutionCapabilities(
            mode=ExecutionMode.PRODUCTION_GPU,
            support=SupportState.SUPPORTED,
            permissions=SideEffectPermissions(
                runtime_import=True,
                asset_load=True,
                checkpoint_load=True,
                tokenizer_load=True,
                real_training=True,
            ),
        ),
    )


__all__ = [
    "ActionCapabilities",
    "ActionMaskPolicy",
    "ActionRepresentation",
    "ActionShapePolicy",
    "ComponentDescriptor",
    "ComponentRole",
    "ExecutionCapabilities",
    "ExecutionMode",
    "InputCapabilities",
    "ModelCapabilities",
    "NormalizationCapabilities",
    "NormalizationMode",
    "SideEffectPermissions",
    "StatePolicy",
    "SupportState",
    "build_gpu_family_capabilities",
    "build_test_double_capabilities",
    "build_unverified_capabilities",
]
