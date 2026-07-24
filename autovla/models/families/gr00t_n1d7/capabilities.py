"""GR00T N1.7 能力、形状和运行时证据边界。"""

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
    StatePolicy,
    SupportState,
)


def _build_capabilities() -> ModelCapabilities:
    """构造架构已定义但执行证据仍关闭的能力事实。"""

    return ModelCapabilities(
        processor=ComponentDescriptor(
            ComponentRole.PROCESSOR,
            "gr00t_n1d7_dynamic_qwen3_vl_processor",
            SupportState.UNVERIFIED,
        ),
        backbone=ComponentDescriptor(
            ComponentRole.BACKBONE,
            "local_cosmos_reason2_qwen3_vl",
            SupportState.UNVERIFIED,
        ),
        action_head=ComponentDescriptor(
            ComponentRole.ACTION_HEAD,
            "gr00t_n1d7_flow_matching_action_head",
            SupportState.UNVERIFIED,
        ),
        inputs=InputCapabilities(
            image_support=SupportState.UNVERIFIED,
            required_cameras=("camera.rgb_0",),
            language_required=True,
            state_policy=StatePolicy.REQUIRED,
        ),
        action=ActionCapabilities(
            representation=ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK,
            shape_policy=ActionShapePolicy.CONFIGURED_BATCH_HORIZON_DIM,
            mask_policy=ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE,
            fixed_horizon=40,
            fixed_dimension=132,
        ),
        normalization=NormalizationCapabilities(
            support=SupportState.UNVERIFIED,
            mode=NormalizationMode.STATISTICS_GOVERNED,
            statistics_required=True,
        ),
        execution=ExecutionCapabilities(
            mode=ExecutionMode.METADATA_ONLY,
            support=SupportState.UNVERIFIED,
        ),
    )


GR00T_N1D7_CAPABILITIES = _build_capabilities()

__all__ = ["GR00T_N1D7_CAPABILITIES"]
