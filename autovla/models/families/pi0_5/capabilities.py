"""构造 Pi0.5 的闭合能力声明,不执行模型或资产加载。"""

from autovla.models.capabilities import (
    ActionCapabilities,
    ActionMaskPolicy,
    ActionRepresentation,
    ActionShapePolicy,
    ComponentDescriptor,
    ComponentRole,
    ExecutionCapabilities,
    ExecutionMode,
    InputCapabilities,
    ModelCapabilities,
    NormalizationCapabilities,
    NormalizationMode,
    SideEffectPermissions,
    StatePolicy,
    SupportState,
)


def build_pi05_capabilities() -> ModelCapabilities:
    """声明架构已实现但官方资产和运行证据仍未闭合的 GPU 能力。"""

    return ModelCapabilities(
        processor=ComponentDescriptor(
            ComponentRole.PROCESSOR, "pi05_processor", SupportState.SUPPORTED
        ),
        backbone=ComponentDescriptor(
            ComponentRole.BACKBONE, "pi05_joint_prefix_expert", SupportState.SUPPORTED
        ),
        action_head=ComponentDescriptor(
            ComponentRole.ACTION_HEAD, "pi05_adarms_flow_expert", SupportState.SUPPORTED
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
            fixed_horizon=50,
            fixed_dimension=32,
        ),
        normalization=NormalizationCapabilities(
            support=SupportState.SUPPORTED,
            mode=NormalizationMode.STATISTICS_GOVERNED,
            statistics_required=True,
        ),
        execution=ExecutionCapabilities(
            mode=ExecutionMode.PRODUCTION_GPU,
            support=SupportState.UNVERIFIED,
            permissions=SideEffectPermissions(
                runtime_import=True,
                asset_load=True,
                checkpoint_load=True,
                tokenizer_load=True,
                real_training=True,
            ),
        ),
    )


__all__ = ["build_pi05_capabilities"]
