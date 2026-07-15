"""三个 Pi 家族共用的静态定义构造器。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import NormalizationMode, build_unverified_capabilities
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

OPENPI_REVISION = "15a9616a00943ada6c20a0f158e3adb39df2ccac"


def build_pi_definition(
    *,
    family_key: str,
    display_name: str,
    config_type: type[object],
    max_language_tokens: int,
    state_conditioning: str,
    normalization: str,
    aliases: tuple[str, ...],
) -> ModelFamilyDefinition:
    """构造无运行时工厂、无 JAX/Flax 副作用的完整 Pi 定义。"""

    return ModelFamilyDefinition(
        family_key=family_key,
        display_name=display_name,
        license=LicenseSpec(
            code_license_status="verified_apache_2_0_source",
            weight_license_status="separate_weight_and_gemma_terms_unresolved",
            model_card_status="separate_model_card_review_required",
            notes=("OpenPI 源码许可不代表 Gemma 或模型权重许可。",),
        ),
        upstream_reference="https://github.com/Physical-Intelligence/openpi@" + OPENPI_REVISION,
        embodiment=("cross_embodiment", "dataset_configured_action_semantics"),
        env_profiles=(EnvProfile.metadata_only(),),
        capabilities=build_unverified_capabilities(
            processor_identity=f"{family_key}_processor_contract",
            backbone_identity=f"{family_key}_paligemma_contract",
            action_head_identity=f"{family_key}_action_head_contract",
            normalization_mode=NormalizationMode.STATISTICS_GOVERNED,
            statistics_required=True,
        ),
        runtime_support=RuntimeSupportState.ARCHITECTURE_DEFINED_RUNTIME_DEFERRED,
        shape=ModelShapeContract(50, 32, 32),
        inputs=ModelInputContract(
            cameras=("base_0_rgb", "left_wrist_0_rgb", "right_wrist_0_rgb"),
            image_size=224,
            language_required=True,
            state_conditioning=state_conditioning,
            max_language_tokens=max_language_tokens,
        ),
        action=ModelActionContract(
            representation=(
                "autoregressive_fast_action_tokens"
                if family_key == "pi0_fast"
                else "continuous_flow_matching_chunk"
            ),
            normalization=normalization,
            horizon_policy="default_50_dataset_override_explicit",
            mask_policy="dataset_padding_and_statistics_contract",
            relative_semantics_scope="dataset_or_embodiment_transform_plan_only",
        ),
        factories=ComponentFactoryPaths(
            config=f"{config_type.__module__}:{config_type.__name__}",
            processor=None,
            backbone=None,
            action_head=None,
            model=None,
            checkpoint=None,
        ),
        asset_keys=(f"{family_key}_checkpoint", f"{family_key}_normalization_assets"),
        checkpoint_layout="local_params_or_model_safetensors_plus_assets_norm_stats",
        supported_precisions=("bfloat16",),
        supported_topologies=("architecture_metadata_only",),
        compatibility_aliases=aliases,
        reuse=(
            OpenSourceReuseSpec(
                upstream_project="OpenPI",
                upstream_url="https://github.com/Physical-Intelligence/openpi",
                license="Apache-2.0 source; Gemma and weights separate",
                reuse_mode="inspired",
                copied_or_adapted_code=False,
                wholesale_rejection_reason=(
                    "M9 不引入 JAX、Flax、Orbax、OpenPI 或云端下载运行时。"
                ),
                revision=OPENPI_REVISION,
            ),
        ),
        source_status="architecture_complete_from_pinned_source",
        validation_status="runtime_deferred_no_autovla_runtime",
        transform_requirements=(
            "r3_transform_plan",
            "dataset_specific_relative_action_mask",
            "explicit_normalization_statistics",
            "inverse_output_transform_order",
        ),
    )


__all__ = ["OPENPI_REVISION", "build_pi_definition"]
