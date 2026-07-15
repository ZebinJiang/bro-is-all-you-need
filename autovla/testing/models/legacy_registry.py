"""测试命名空间中的历史模型动物园兼容实现。"""

from __future__ import annotations

from dataclasses import replace

from autovla.core.registry import Registry
from autovla.core.runtime import EnvProfile
from autovla.models.capabilities import (
    NormalizationMode,
    build_test_double_capabilities,
    build_unverified_capabilities,
)
from autovla.models.contracts import ModelZooEntry
from autovla.models.family import LicenseSpec, ModelFamilySpec
from autovla.models.gr00t.metadata import GR00T_N1D6_FAMILY_SPEC
from autovla.models.gr00t_n1d6.adapter import GR00T_N1D6_ENTRY
from autovla.models.pi.metadata import PI_ROADMAP_FAMILY_SPECS

GR00T_SERIES_CANDIDATES = (
    "gr00t-n1d6",
    "gr00t-n1d6.1",
    "qwen-gr00t-bridge-reference",
)
PI_SERIES_CANDIDATES = (
    "pi0-roadmap",
    "pi0.5-roadmap",
    "qwen-pi-bridge-reference",
)
TEST_DOUBLE_FAMILY_SPEC = ModelFamilySpec(
    family_key="test_double",
    display_name="Deterministic local test policy",
    license=LicenseSpec(
        code_license_status="verified_permissive",
        weight_license_status="verified_permissive",
        model_card_status="verified_permissive",
        notes=("Synthetic local policy; no model assets exist or are loaded.",),
    ),
    upstream_reference="AutoVLA-owned deterministic test double",
    embodiment=("synthetic_fixture_only",),
    env_profiles=(EnvProfile.local_cpu_smoke(),),
    capabilities=build_test_double_capabilities(),
)
GR00T_N1D6_METADATA_SPEC = replace(
    GR00T_N1D6_FAMILY_SPEC,
    family_key="gr00t_n1d6_metadata",
    capabilities=build_unverified_capabilities(
        processor_identity="gr00t_n1d6_processor",
        backbone_identity="gr00t_n1d6_backbone",
        action_head_identity="gr00t_n1d6_flow_diffusion_action_head",
        normalization_mode=NormalizationMode.STATISTICS_GOVERNED,
        statistics_required=True,
    ),
)
PI0_METADATA_SPEC = replace(PI_ROADMAP_FAMILY_SPECS[0], family_key="pi0_metadata")
PI05_METADATA_SPEC = replace(PI_ROADMAP_FAMILY_SPECS[-1], family_key="pi05_metadata")


def build_model_zoo_registry() -> Registry[ModelZooEntry]:
    """构造历史模型动物园元数据注册表。"""
    registry: Registry[ModelZooEntry] = Registry("autovla-model-zoo-compat")
    registry.register(GR00T_N1D6_ENTRY.model_registry_key, GR00T_N1D6_ENTRY)
    return registry


def get_model_zoo_entry(model_registry_key: str) -> ModelZooEntry:
    """按历史模型注册键返回元数据条目。"""
    return build_model_zoo_registry().get(model_registry_key)


def list_model_family_candidates() -> dict[str, tuple[str, ...]]:
    """返回历史路线图候选族。"""
    return {
        "gr00t": GR00T_SERIES_CANDIDATES,
        "pi": PI_SERIES_CANDIDATES,
    }


def list_model_zoo_keys() -> tuple[str, ...]:
    """返回历史模型动物园键。"""
    return build_model_zoo_registry().names()


__all__ = [
    "GR00T_N1D6_METADATA_SPEC",
    "GR00T_SERIES_CANDIDATES",
    "PI0_METADATA_SPEC",
    "PI05_METADATA_SPEC",
    "PI_SERIES_CANDIDATES",
    "TEST_DOUBLE_FAMILY_SPEC",
    "build_model_zoo_registry",
    "get_model_zoo_entry",
    "list_model_family_candidates",
    "list_model_zoo_keys",
]
