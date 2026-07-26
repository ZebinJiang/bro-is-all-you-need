"""GR00T N1.7 家族唯一类型化定义。

家族包含三个保留 NVIDIA 版权和 Apache-2.0 header 的选择性适配文件;其余边界为
AutoVLA 本地实现。checkpoint 与 Cosmos 条款继续与代码许可严格分离。
"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    ActionDimensionPolicy,
    ActionDistribution,
    ActionHorizonPolicy,
    ActionMaskPolicy,
    ActionRepresentation,
    CheckpointFormat,
    ImageResolutionPolicy,
    NormalizationPolicy,
    PrecisionSupport,
    RelativeActionPolicy,
    RuntimeSupportLevel,
    StateConditioningPolicy,
    TopologySupport,
)
from autovla.models.families.gr00t_n1d7.capabilities import GR00T_N1D7_CAPABILITIES
from autovla.models.families.gr00t_n1d7.config import NVIDIA_GR00T_SOURCE_REVISION
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

_FACTORIES = ComponentFactoryPaths(
    config="autovla.models.families.gr00t_n1d7.config:Gr00tN1d7Config",
    processor="autovla.models.families.gr00t_n1d7.processor:_build_processor",
    backbone="autovla.models.families.gr00t_n1d7.backbone:_build_backbone",
    action_head="autovla.models.families.gr00t_n1d7.action_head:_build_action_head",
    model="autovla.models.families.gr00t_n1d7.factory:Gr00tN1d7ModelFactory",
    checkpoint="autovla.models.families.gr00t_n1d7.checkpoint:_build_checkpoint_adapter",
    asset_bundle="autovla.models.families.gr00t_n1d7.assets:Gr00tN1d7AssetBundle",
)

_ASSEMBLY_REQUIREMENTS = ModelAssemblyRequirements(
    factories=_FACTORIES,
    dependencies=ModelDependencyRequirements(
        (
            DependencyRequirement(
                "torch",
                DependencyClass.OPTIONAL_FAMILY,
                version_specifier="==2.9.0+cu128",
            ),
            DependencyRequirement(
                "transformers",
                DependencyClass.OPTIONAL_FAMILY,
                version_specifier="==4.57.3",
                incompatible_with=("trust_remote_code",),
            ),
            DependencyRequirement(
                "safetensors",
                DependencyClass.MANDATORY_RUNTIME,
                version_specifier="==0.7.0",
            ),
            DependencyRequirement(
                "flash_attn",
                DependencyClass.GPU_EXTENSION,
                version_specifier="==2.8.3",
            ),
            DependencyRequirement(
                "deepspeed",
                DependencyClass.GPU_EXTENSION,
                version_specifier="==0.17.6",
            ),
        )
    ),
    assets=(
        ModelAssetRequirement("base_checkpoint", "gr00t_n1d7_checkpoint"),
        ModelAssetRequirement("cosmos_backbone", "cosmos_reason2_2b_gated"),
        ModelAssetRequirement("checkpoint_license_receipt", "gr00t_n1d7_license_resolution"),
        ModelAssetRequirement("cosmos_access_receipt", "cosmos_reason2_access_receipt"),
    ),
    checkpoint=ModelCheckpointDefinition(
        CheckpointFormat.SAFETENSORS,
        "local_sharded_safetensors_backbone_and_action_head_namespaces",
    ),
    transforms=(
        TransformRequirement("processor_modality_action_config_projection"),
        TransformRequirement("canonical_se3_relative_eef", inverse_required=True),
        TransformRequirement("per_embodiment_statistics", inverse_required=True),
    ),
    precisions=(PrecisionSupport.METADATA_ONLY,),
    topologies=(TopologySupport.METADATA_ONLY,),
    runtime_level=RuntimeSupportLevel.ASSET_GATED,
    evidence=RuntimeEvidenceState(source_architecture_complete=True),
)


class Gr00tN1d7FamilyDefinition(ModelFamilyDefinition):
    """构造固定来源、动态网格且许可/资产失败关闭的家族定义。"""

    def __init__(self) -> None:
        """初始化唯一 N1.7 家族事实。不导入模型运行时。"""

        super().__init__(
            family_key="gr00t_n1d7",
            display_name="NVIDIA Isaac-GR00T N1.7",
            license=LicenseSpec(
                code_license_status="apache_2_0_verified",
                weight_license_status="conflicting_packaged_license_fail_closed",
                model_card_status="claims_nvidia_open_model_license_not_accepted_as_resolution",
                notes=(
                    "checkpoint 打包 LICENSE 与模型卡条款冲突。当前禁止执行。",
                    "Cosmos-Reason2-2B 需独立 gated access、revision、hash 和许可收据。",
                ),
            ),
            upstream_reference=(
                "https://github.com/NVIDIA/Isaac-GR00T@" + NVIDIA_GR00T_SOURCE_REVISION
            ),
            embodiment=("cross_embodiment", "official_n1d7"),
            env_profiles=(EnvProfile.metadata_only(),),
            capabilities=GR00T_N1D7_CAPABILITIES,
            runtime_support=RuntimeSupportState.ASSET_REQUIRED,
            shape=ModelShapeContract(40, 132, 132),
            inputs=ModelInputContract(
                cameras=("camera.rgb_0",),
                image_size=1,
                language_required=True,
                state_conditioning=StateConditioningPolicy.CONTINUOUS_FEATURES,
                image_resolution_policy=ImageResolutionPolicy.PROCESSOR_MANAGED,
            ),
            action=ModelActionContract(
                representation=ActionRepresentation.CONTINUOUS_NUMERIC_CHUNK,
                normalization=NormalizationPolicy.FAMILY_STATISTICS,
                horizon_policy=ActionHorizonPolicy.FIXED_BY_FAMILY,
                mask_policy=ActionMaskPolicy.STRICT_BOOL_SAME_SHAPE,
                relative_semantics_scope=RelativeActionPolicy.EMBODIMENT_TRANSFORM_PLAN,
                distribution=ActionDistribution.FLOW_MATCHING,
                dimension_policy=ActionDimensionPolicy.EMBODIMENT_WITH_FAMILY_PADDING,
            ),
            factories=_FACTORIES,
            asset_keys=(
                "gr00t_n1d7_checkpoint",
                "cosmos_reason2_2b_gated",
                "gr00t_n1d7_license_resolution",
                "cosmos_reason2_access_receipt",
            ),
            checkpoint_layout="local_sharded_safetensors_strict_index_mapping",
            supported_precisions=("metadata_only",),
            supported_topologies=("metadata_only",),
            optional_extra="model-gr00t-n1d7",
            compatibility_aliases=("gr00t-n1d7",),
            reuse=(
                OpenSourceReuseSpec(
                    upstream_project="NVIDIA Isaac-GR00T",
                    upstream_url="https://github.com/NVIDIA/Isaac-GR00T",
                    license=("Apache-2.0 code only; checkpoint and Cosmos terms separate"),
                    reuse_mode="adapted",
                    copied_or_adapted_code=True,
                    wholesale_rejection_reason=(
                        "仅适配 source_map 固定的三个家族私有文件;拒绝整体引入上游 "
                        "trainer/runtime、隐式网络和 gated 资产耦合。"
                    ),
                    revision=NVIDIA_GR00T_SOURCE_REVISION,
                ),
            ),
            source_status=(
                "attributed_adapted_regions_and_local_implementation_from_pinned_source"
            ),
            validation_status="source_only_license_cosmos_checkpoint_cuda_unvalidated",
            transform_requirements=(
                "processor_modality_action_config_projection",
                "canonical_se3_relative_eef_inverse",
                "per_embodiment_statistics_inverse",
            ),
            assembly_requirements=_ASSEMBLY_REQUIREMENTS,
        )


GR00T_N1D7_FAMILY = Gr00tN1d7FamilyDefinition()

__all__ = ["GR00T_N1D7_FAMILY", "Gr00tN1d7FamilyDefinition"]
