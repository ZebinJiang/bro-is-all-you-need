"""Pi0.5 唯一类型化家族定义与共享装配要求。

设计参考: Physical-Intelligence/openpi@15a9616a00943ada6c20a0f158e3adb39df2ccac。
源码许可为 Apache-2.0;Gemma、tokenizer、checkpoint 与派生权重需独立收据。
"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    CheckpointFormat,
    PrecisionSupport,
    RuntimeSupportLevel,
    TopologySupport,
)
from autovla.models.families.pi0_5.capabilities import build_pi05_capabilities
from autovla.models.families.pi0_5.source_map import OPENPI_REVISION, OPENPI_URL
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


class Pi05FamilyDefinition(ModelFamilyDefinition):
    """为 Pi0.5 提供具名且仍遵循共享不可变定义的类型身份。"""


_FACTORIES = ComponentFactoryPaths(
    config="autovla.models.families.pi0_5.config:Pi05Config",
    processor="autovla.models.families.pi0_5.processor:Pi05Processor",
    backbone="autovla.models.families.pi0_5.backbone:Pi05VisionLanguageBackbone",
    action_head="autovla.models.families.pi0_5.action_head:Pi05ActionExpert",
    model="autovla.models.families.pi0_5.factory:Pi05ModelFactory",
    checkpoint="autovla.models.families.pi0_5.checkpoint:Pi05CheckpointAdapter",
    asset_bundle="autovla.models.families.pi0_5.assets:Pi05AssetBundle",
    policy_bundle="autovla.models.families.pi0_5.policy:Pi05PolicyBundle",
)

PI05_SPEC = Pi05FamilyDefinition(
    family_key="pi0_5",
    display_name="Physical Intelligence Pi0.5",
    license=LicenseSpec(
        code_license_status="verified_apache_2_0_design_reference_clean_implementation",
        weight_license_status="gemma_checkpoint_and_derived_weight_terms_unresolved",
        model_card_status="official_asset_receipt_required",
        notes=(
            "OpenPI 源码许可与 Gemma、tokenizer、checkpoint 条款严格分离。",
            "AutoVLA 不复制 Transformers patch,也不执行远程代码。",
        ),
    ),
    upstream_reference=OPENPI_URL,
    embodiment=("cross_embodiment", "dataset_configured_action_semantics"),
    env_profiles=(EnvProfile.metadata_only(),),
    capabilities=build_pi05_capabilities(),
    runtime_support=RuntimeSupportState.ASSET_REQUIRED,
    shape=ModelShapeContract(50, 32, 32),
    inputs=ModelInputContract(
        cameras=("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb"),
        image_size=224,
        language_required=True,
        state_conditioning="discrete_state_in_language_tokens",
        max_language_tokens=200,
    ),
    action=ModelActionContract(
        representation="continuous_flow_matching_chunk",
        normalization="r3_quantile_q01_q99",
        horizon_policy="default_50_dataset_override_explicit",
        mask_policy="strict_bool_same_shape_B_T_D",
        relative_semantics_scope="dataset_or_embodiment_transform_plan_only",
    ),
    factories=_FACTORIES,
    asset_keys=("pi0_5_checkpoint", "pi0_5_gemma_tokenizer", "pi0_5_normalization"),
    checkpoint_layout="converted_model_safetensors_plus_conversion_manifest",
    supported_precisions=("bfloat16", "float32"),
    supported_topologies=("single_gpu",),
    optional_extra="model-pi0-5",
    compatibility_aliases=("pi05-roadmap", "pi05_metadata"),
    reuse=(
        OpenSourceReuseSpec(
            upstream_project="Physical Intelligence OpenPI",
            upstream_url="https://github.com/Physical-Intelligence/openpi",
            license="Apache-2.0 source; Gemma and checkpoint terms separate",
            reuse_mode="inspired_clean_implementation",
            copied_or_adapted_code=False,
            wholesale_rejection_reason=(
                "上游运行时耦合 JAX/Flax/Orbax 与 site-packages 补丁;M10 使用自有边界。"
            ),
            revision=OPENPI_REVISION,
        ),
    ),
    source_status="autovla_native_pytorch_architecture_implemented_asset_gated",
    validation_status=(
        "family_private_source_surface_complete_activation_blocked_pending_"
        "checkpoint_gemma_tokenizer_terms_assets_isolated_environment_conversion_runtime"
    ),
    transform_requirements=(
        "strict_image_validity_masks",
        "prompt_state_200_token_limit",
        "quantile_q01_q99",
        "inverse_output_transform_order",
    ),
    assembly_requirements=ModelAssemblyRequirements(
        factories=_FACTORIES,
        dependencies=ModelDependencyRequirements(
            (
                DependencyRequirement("torch", DependencyClass.MANDATORY_RUNTIME, ">=2.5,<2.7"),
                DependencyRequirement(
                    "safetensors", DependencyClass.MANDATORY_RUNTIME, ">=0.4,<0.6"
                ),
                DependencyRequirement("jax", DependencyClass.CONVERSION_ONLY),
                DependencyRequirement("flax", DependencyClass.CONVERSION_ONLY),
                DependencyRequirement("orbax", DependencyClass.CONVERSION_ONLY),
            )
        ),
        assets=(
            ModelAssetRequirement("checkpoint", "pi0_5_checkpoint"),
            ModelAssetRequirement("gemma_tokenizer", "pi0_5_gemma_tokenizer"),
            ModelAssetRequirement("normalization_statistics", "pi0_5_normalization"),
        ),
        checkpoint=ModelCheckpointDefinition(
            CheckpointFormat.SAFETENSORS,
            "strict_converted_safetensors_with_deterministic_manifest",
            immutable_base_asset=True,
            conversion_required=True,
        ),
        transforms=(
            TransformRequirement("strict_image_validity_masks"),
            TransformRequirement("prompt_state_200_token_limit"),
            TransformRequirement("quantile_q01_q99", inverse_required=True),
            TransformRequirement("inverse_output_transform_order", inverse_required=True),
        ),
        precisions=(PrecisionSupport.BFLOAT16, PrecisionSupport.FLOAT32),
        topologies=(TopologySupport.SINGLE_GPU,),
        runtime_level=RuntimeSupportLevel.ASSET_GATED,
        evidence=RuntimeEvidenceState(source_architecture_complete=True),
    ),
)

__all__ = ["PI05_SPEC", "Pi05FamilyDefinition"]
