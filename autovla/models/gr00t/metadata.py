"""GR00T-N1D6 AutoVLA-native 模型族元数据。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    NormalizationMode,
    build_unverified_capabilities,
)
from autovla.models.family import LicenseSpec, ModelFamilySpec, OpenSourceReuseSpec

GR00T_N1D6_FAMILY_SPEC = ModelFamilySpec(
    family_key="gr00t-n1d6",
    display_name="GR00T N1.6 / N1D6 native family",
    license=LicenseSpec(
        code_license_status="requires_upstream_verification",
        weight_license_status="requires_model_license_review",
        model_card_status="requires_model_card_review",
        notes=(
            "GR00T code and model weights are governed separately.",
            "No model card or checkpoint compatibility is claimed by metadata lookup.",
        ),
    ),
    upstream_reference="NVIDIA Isaac-GR00T / GR00T-N1.6",
    embodiment=("cross_embodiment", "humanoid_or_robot_family_metadata_only"),
    env_profiles=(
        EnvProfile.metadata_only(),
        EnvProfile.local_cpu_smoke(),
        EnvProfile.model_gr00t_n1d6_future(),
    ),
    capabilities=build_unverified_capabilities(
        processor_identity="gr00t_n1d6_processor",
        backbone_identity="gr00t_n1d6_backbone",
        action_head_identity="gr00t_n1d6_flow_diffusion_action_head",
        normalization_mode=NormalizationMode.STATISTICS_GOVERNED,
        statistics_required=True,
    ),
    reuse=(
        OpenSourceReuseSpec(
            upstream_project="NVIDIA Isaac-GR00T",
            upstream_url="https://github.com/NVIDIA/Isaac-GR00T",
            license="Apache-2.0 code license; model weights separate",
            reuse_mode="inspired",
            copied_or_adapted_code=False,
            wholesale_rejection_reason=(
                "AutoVLA registry lookup must not import GR00T runtime or load checkpoints."
            ),
        ),
    ),
)
