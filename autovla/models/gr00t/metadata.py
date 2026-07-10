"""GR00T-N1D6 AutoVLA-native 模型族元数据。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
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
    modality_inputs=("language", "image_views", "proprioception/state"),
    action_output="continuous action chunk",
    action_head_family="flow_matching_or_diffusion_transformer",
    embodiment=("cross_embodiment", "humanoid_or_robot_family_metadata_only"),
    runtime_status=(
        "metadata_only",
        "dryrun_adapter_supported",
        "upstream_runtime_not_loaded",
    ),
    env_profiles=(
        EnvProfile.metadata_only(),
        EnvProfile.local_cpu_smoke(),
        EnvProfile.model_gr00t_n1d6_future(),
    ),
    processor_family="gr00t_metadata_only_processor",
    backbone_family="gr00t_n1d6_metadata_only_backbone",
    normalization_support="unverified_statistics_governed",
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
