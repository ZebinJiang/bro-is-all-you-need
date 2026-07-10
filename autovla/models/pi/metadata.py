"""π / OpenPI roadmap-only 模型族元数据。"""

from __future__ import annotations

from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    NormalizationMode,
    build_unverified_capabilities,
)
from autovla.models.family import LicenseSpec, ModelFamilySpec, OpenSourceReuseSpec


def _pi_spec(family_key: str, display_name: str) -> ModelFamilySpec:
    """构造不导入 JAX/Flax 的 π roadmap 元数据。"""
    return ModelFamilySpec(
        family_key=family_key,
        display_name=display_name,
        license=LicenseSpec(
            code_license_status="requires_upstream_verification",
            weight_license_status="requires_model_license_review",
            model_card_status="requires_model_card_review",
            notes=("OpenPI runtime support is roadmap-only in this task.",),
        ),
        upstream_reference="Physical Intelligence OpenPI",
        embodiment=("cross_embodiment", "roadmap_only"),
        env_profiles=(EnvProfile.metadata_only(),),
        capabilities=build_unverified_capabilities(
            processor_identity=f"{family_key}_processor",
            backbone_identity=f"{family_key}_backbone",
            action_head_identity=f"{family_key}_policy_action_head",
            normalization_mode=NormalizationMode.UNSPECIFIED,
            statistics_required=False,
        ),
        reuse=(
            OpenSourceReuseSpec(
                upstream_project="OpenPI",
                upstream_url="https://github.com/Physical-Intelligence/openpi",
                license="Apache-2.0",
                reuse_mode="inspired",
                copied_or_adapted_code=False,
                wholesale_rejection_reason="JAX/Flax runtime must not enter AutoVLA core.",
            ),
        ),
    )


PI_ROADMAP_FAMILY_SPECS = (
    _pi_spec("pi0-roadmap", "π0 roadmap family"),
    _pi_spec("pi0-fast-roadmap", "π0-FAST roadmap family"),
    _pi_spec("pi05-roadmap", "π0.5 roadmap family"),
)
