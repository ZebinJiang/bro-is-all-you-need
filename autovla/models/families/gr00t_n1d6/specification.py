"""GR00T N1.6.1 规范模型族定义。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    CheckpointFormat,
    PrecisionSupport,
    RuntimeSupportLevel,
    TopologySupport,
    build_gpu_family_capabilities,
)
from autovla.models.families.specification import (
    ComponentFactoryPaths,
    DependencyClass,
    DependencyRequirement,
    LicenseSpec,
    ModelActionContract,
    ModelAssemblyRequirements,
    ModelAssetRequirement,
    ModelCheckpointDefinition,
    ModelDependencyRequirements,
    ModelFamilyDefinition,
    ModelInputContract,
    ModelShapeContract,
    OpenSourceReuseSpec,
    RuntimeEvidenceState,
    RuntimeSupportState,
    TransformRequirement,
)

NVIDIA_GR00T_REVISION = "5dc80c4afd726b34faad1d8f7e007a13b34e4c88"
NVIDIA_GR00T_CHECKPOINT_REVISION = "d0814e7ecb19202e7c8468b46098b0b7ef3a6d61"


class Gr00tN1d6FamilyDefinition(ModelFamilyDefinition):
    """提供 N1.6.1 的精确家族定义类型,不创建第二套字段。"""

    __slots__ = ()


_FACTORIES = ComponentFactoryPaths(
    config="autovla.models.families.gr00t_n1d6.config:Gr00tN1d6Config",
    processor="autovla.models.families.gr00t_n1d6.factory:_Gr00tN1d6ProcessorFactory",
    backbone="autovla.models.families.gr00t_n1d6.factory:_Gr00tN1d6BackboneFactory",
    action_head="autovla.models.families.gr00t_n1d6.factory:_Gr00tN1d6ActionHeadFactory",
    model="autovla.models.families.gr00t_n1d6.factory:Gr00tN1d6ModelFactory",
    checkpoint=("autovla.models.families.gr00t_n1d6.factory:_Gr00tN1d6CheckpointAdapterFactory"),
    asset_bundle="autovla.models.families.gr00t_n1d6.assets:Gr00tN1d6AssetBundle",
)


GR00T_N1D6_SPEC = Gr00tN1d6FamilyDefinition(
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
    factories=_FACTORIES,
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
    source_status="source_architecture_complete_asset_gated",
    validation_status="c1_c2r7_checkpoint_validated_blocked_c3_data_runtime_unverified",
    transform_requirements=(
        "r3_transform_plan",
        "axis_aware_state_action_statistics",
        "per_horizon_relative_action_statistics",
        "separate_padding_and_action_masks",
    ),
    assembly_requirements=ModelAssemblyRequirements(
        factories=_FACTORIES,
        dependencies=ModelDependencyRequirements(
            (
                DependencyRequirement("torch", DependencyClass.MANDATORY_RUNTIME),
                DependencyRequirement("transformers", DependencyClass.OPTIONAL_FAMILY),
                DependencyRequirement("safetensors", DependencyClass.OPTIONAL_FAMILY),
                DependencyRequirement("torchvision", DependencyClass.OPTIONAL_FAMILY),
                DependencyRequirement("PIL", DependencyClass.OPTIONAL_FAMILY),
                DependencyRequirement("flash_attn", DependencyClass.GPU_EXTENSION),
            )
        ),
        assets=(
            ModelAssetRequirement("base_checkpoint", "gr00t_n1d6"),
            ModelAssetRequirement("eagle_support", "gr00t_n1d6_eagle_support"),
        ),
        checkpoint=ModelCheckpointDefinition(
            CheckpointFormat.SAFETENSORS,
            "strict_local_sharded_safetensors_backbone_and_action_head_namespaces",
        ),
        transforms=(
            TransformRequirement("per_embodiment_normalization", inverse_required=True),
            TransformRequirement("relative_joint_action", inverse_required=True),
            TransformRequirement("canonical_se3_relative_action", inverse_required=True),
            TransformRequirement("state_action_padding", inverse_required=True),
            TransformRequirement("strict_action_mask"),
        ),
        precisions=(PrecisionSupport.BFLOAT16, PrecisionSupport.FLOAT32),
        topologies=(
            TopologySupport.SINGLE_GPU,
            TopologySupport.DISTRIBUTED_DATA_PARALLEL,
            TopologySupport.DEEPSPEED_ZERO_1,
            TopologySupport.DEEPSPEED_ZERO_2,
            TopologySupport.DEEPSPEED_ZERO_3,
        ),
        runtime_level=RuntimeSupportLevel.ASSET_GATED,
        evidence=RuntimeEvidenceState(
            source_architecture_complete=True,
            assembly_eligible=True,
            official_asset_bundle_available=True,
            official_checkpoint_load_validated=True,
            official_checkpoint_loaded_tensor_count=1010,
            checkpoint_load_device="one_a100",
            accepted_evidence=(
                "C1_ASSET_RECEIPT_ACCEPTED",
                "C2R7_ONE_A100_STRICT_CHECKPOINT_LOAD_ACCEPTED",
            ),
        ),
    ),
)

# 子类名保留为同一类型身份,避免形成第二事实源。
Gr00tN1d6ModelSpec = Gr00tN1d6FamilyDefinition

__all__ = [
    "GR00T_N1D6_SPEC",
    "NVIDIA_GR00T_CHECKPOINT_REVISION",
    "NVIDIA_GR00T_REVISION",
    "Gr00tN1d6FamilyDefinition",
    "Gr00tN1d6ModelSpec",
]
