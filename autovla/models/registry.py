"""AutoVLA 模型动物园注册表。"""

from __future__ import annotations

from dataclasses import replace

from autovla.core.registry import Registry
from autovla.core.runtime import EnvProfile
from autovla.models.contracts import ModelZooEntry
from autovla.models.family import LicenseSpec, ModelFamilyRegistry, ModelFamilySpec
from autovla.models.gr00t import GR00T_N1D6_FAMILY_SPEC
from autovla.models.gr00t_n1d6 import GR00T_N1D6_ENTRY
from autovla.models.pi import PI_ROADMAP_FAMILY_SPECS

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


def build_model_zoo_registry() -> Registry[ModelZooEntry]:
    """构造急切的模型动物园注册表,不执行懒加载或导入重型运行时。"""
    registry: Registry[ModelZooEntry] = Registry("autovla-model-zoo")
    registry.register(GR00T_N1D6_ENTRY.model_registry_key, GR00T_N1D6_ENTRY)
    return registry


_MODEL_ZOO = build_model_zoo_registry()
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
    modality_inputs=("language", "three_rgb_cameras", "state"),
    action_output="deterministic numeric action chunk",
    action_head_family="deterministic_test_action_head",
    embodiment=("synthetic_fixture_only",),
    runtime_status=("deterministic_test_only",),
    env_profiles=(EnvProfile.local_cpu_smoke(),),
    processor_family="identity_numpy_processor",
    backbone_family="no_backbone_test_double",
    normalization_support="supported_identity_only",
)
GR00T_N1D6_METADATA_SPEC = replace(
    GR00T_N1D6_FAMILY_SPEC,
    family_key="gr00t_n1d6_metadata",
    runtime_status=("metadata_only", "no_import"),
)
PI0_METADATA_SPEC = replace(
    PI_ROADMAP_FAMILY_SPECS[0],
    family_key="pi0_metadata",
    runtime_status=("metadata_only", "no_import"),
)
PI05_METADATA_SPEC = replace(
    PI_ROADMAP_FAMILY_SPECS[-1],
    family_key="pi05_metadata",
    runtime_status=("metadata_only", "no_import"),
)
_MODEL_FAMILY_REGISTRY = ModelFamilyRegistry(
    entries=(
        GR00T_N1D6_FAMILY_SPEC,
        *PI_ROADMAP_FAMILY_SPECS,
        TEST_DOUBLE_FAMILY_SPEC,
        GR00T_N1D6_METADATA_SPEC,
        PI0_METADATA_SPEC,
        PI05_METADATA_SPEC,
    )
)


def get_model_zoo_entry(model_registry_key: str) -> ModelZooEntry:
    """按模型注册键返回模型动物园元数据条目。"""
    return _MODEL_ZOO.get(model_registry_key)


def list_model_zoo_keys() -> tuple[str, ...]:
    """返回已注册模型键。"""
    return _MODEL_ZOO.names()


def list_model_family_candidates() -> dict[str, tuple[str, ...]]:
    """返回路线图候选族,仅供文档和 readiness manifest 使用。"""
    return {
        "gr00t": GR00T_SERIES_CANDIDATES,
        "pi": PI_SERIES_CANDIDATES,
    }


def get(model_registry_key: str) -> ModelFamilySpec:
    """按模型族 key 返回 metadata-only 模型族契约。"""
    return _MODEL_FAMILY_REGISTRY.get(model_registry_key)


def get_model_family_spec(model_registry_key: str) -> ModelFamilySpec:
    """按模型族 key 返回 metadata-only 模型族契约。"""
    return _MODEL_FAMILY_REGISTRY.get(model_registry_key)


def list_model_family_keys() -> tuple[str, ...]:
    """返回 AutoVLA-native 模型族 key。"""
    return _MODEL_FAMILY_REGISTRY.keys()
