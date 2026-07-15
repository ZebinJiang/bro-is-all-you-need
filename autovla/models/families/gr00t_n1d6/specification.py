"""GR00T N1.6.1 规范模型族定义。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import build_gpu_family_capabilities
from autovla.models.families.specification import (
    ComponentFactoryPaths,
    LicenseSpec,
    ModelActionContract,
    ModelFamilyDefinition,
    ModelInputContract,
    ModelShapeContract,
    OpenSourceReuseSpec,
    RuntimeSupportState,
)

NVIDIA_GR00T_REVISION = "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"

GR00T_N1D6_SPEC = ModelFamilyDefinition(
    family_key="gr00t_n1d6",
    display_name="NVIDIA Isaac-GR00T N1.6.1",
    license=LicenseSpec(
        code_license_status="restricted_nvidia_noncommercial_research",
        weight_license_status="separate_nvidia_weight_terms_verified_local_receipt",
        model_card_status="separate_model_card_terms",
        notes=(
            "源码许可、Eagle 支持数据条款和模型权重许可分别记录。",
            "本地 NVIDIA 派生实现保留来源和限制性许可头。",
        ),
    ),
    upstream_reference=("https://github.com/NVIDIA/Isaac-GR00T@" + NVIDIA_GR00T_REVISION),
    embodiment=("cross_embodiment", "official_n1d6"),
    env_profiles=(EnvProfile.metadata_only(), EnvProfile.model_gr00t_n1d6_future()),
    capabilities=build_gpu_family_capabilities(
        processor_identity="gr00t_n1d6_processor",
        backbone_identity="local_reviewed_eagle_backbone",
        action_head_identity="gr00t_n1d6_flow_matching_action_head",
        required_cameras=("camera.rgb_0", "camera.rgb_1", "camera.rgb_2"),
        action_horizon=50,
        action_dimension=128,
    ),
    runtime_support=RuntimeSupportState.EXECUTABLE,
    shape=ModelShapeContract(50, 128, 128),
    inputs=ModelInputContract(
        cameras=("camera.rgb_0", "camera.rgb_1", "camera.rgb_2"),
        image_size=448,
        language_required=True,
        state_conditioning="continuous_last_state_with_embodiment_projection",
    ),
    action=ModelActionContract(
        representation="continuous_flow_matching_chunk",
        normalization="r3_axis_aware_per_embodiment_statistics",
        horizon_policy="fixed_50",
        mask_policy="strict_bool_same_shape_B_T_D",
        relative_semantics_scope="per_embodiment_per_modality_fixed_last_state_reference",
    ),
    factories=ComponentFactoryPaths(
        config="autovla.models.families.gr00t_n1d6.config:Gr00tN1d6Config",
        processor="autovla.models.families.gr00t_n1d6.processor:Gr00tN1d6Processor",
        backbone="autovla.models.families.gr00t_n1d6.backbone:EagleVisionLanguageBackbone",
        action_head="autovla.models.families.gr00t_n1d6.action_head:Gr00tN1d6ActionHead",
        model="autovla.models.families.gr00t_n1d6.factory:Gr00tN1d6ModelFactory",
        checkpoint=("autovla.models.families.gr00t_n1d6.checkpoint:Gr00tN1d6CheckpointAdapter"),
    ),
    asset_keys=("gr00t_n1d6", "gr00t_n1d6_eagle_support"),
    checkpoint_layout="local_safetensors_backbone_and_action_head_namespaces",
    supported_precisions=("bfloat16", "float32"),
    supported_topologies=(
        "single_gpu",
        "distributed_data_parallel",
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
    ),
    optional_extra="model-gr00t-n1d6",
    compatibility_aliases=("gr00t-n1d6", "gr00t_n1d6_metadata"),
    reuse=(
        OpenSourceReuseSpec(
            upstream_project="NVIDIA Isaac-GR00T",
            upstream_url="https://github.com/NVIDIA/Isaac-GR00T",
            license="LicenseRef-NVIDIA-Isaac-GR00T-N1D6",
            reuse_mode="adapted",
            copied_or_adapted_code=True,
            wholesale_rejection_reason=("仅保留已审查隔离实现;禁止上游包、远程代码和任意 pickle。"),
            revision=NVIDIA_GR00T_REVISION,
        ),
    ),
    source_status="source_implementation_complete_asset_gated",
    validation_status="bounded_runtime_deferred",
    transform_requirements=(
        "r3_transform_plan",
        "axis_aware_state_action_statistics",
        "per_horizon_relative_action_statistics",
        "separate_padding_and_action_masks",
    ),
)

# 子类名保留为同一类型身份,避免形成第二事实源。
Gr00tN1d6ModelSpec = ModelFamilyDefinition

__all__ = ["GR00T_N1D6_SPEC", "NVIDIA_GR00T_REVISION", "Gr00tN1d6ModelSpec"]
