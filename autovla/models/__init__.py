"""AutoVLA 模型注册表与能力元数据的轻量懒加载导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.models.capabilities import (
        ActionCapabilities,
        ActionMaskPolicy,
        ActionRepresentation,
        ActionShapePolicy,
        ComponentDescriptor,
        ComponentRole,
        ExecutionCapabilities,
        ExecutionMode,
        InputCapabilities,
        ModelCapabilities,
        NormalizationCapabilities,
        NormalizationMode,
        SideEffectPermissions,
        StatePolicy,
        SupportState,
    )
    from autovla.models.contracts import (
        ModelAssetMetadata,
        ModelAssetsUnavailableError,
        ModelZooEntry,
        ReleaseReference,
    )
    from autovla.models.family import (
        LicenseSpec,
        ModelFamilyRegistry,
        ModelFamilySpec,
        OpenSourceReuseSpec,
    )
    from autovla.models.gr00t.batch_adapter import Gr00tN1D6DryRunBatchAdapter
    from autovla.models.gr00t.metadata import GR00T_N1D6_FAMILY_SPEC
    from autovla.models.gr00t_n1d6.adapter import (
        GR00T_N1D6_ENTRY,
        Gr00tN1D6AdapterSkeleton,
        build_gr00t_n1d6_adapter_skeleton,
    )
    from autovla.models.pi.metadata import PI_ROADMAP_FAMILY_SPECS
    from autovla.models.registry import (
        GR00T_N1D6_METADATA_SPEC,
        GR00T_SERIES_CANDIDATES,
        PI0_METADATA_SPEC,
        PI05_METADATA_SPEC,
        PI_SERIES_CANDIDATES,
        TEST_DOUBLE_FAMILY_SPEC,
        build_model_zoo_registry,
        get,
        get_model_family_spec,
        get_model_zoo_entry,
        list_model_family_candidates,
        list_model_family_keys,
        list_model_zoo_keys,
    )

_CAPABILITIES = "autovla.models.capabilities"
_CONTRACTS = "autovla.models.contracts"
_FAMILY = "autovla.models.family"
_REGISTRY = "autovla.models.registry"
_EXPORTS = {
    "ActionCapabilities": _CAPABILITIES,
    "ActionMaskPolicy": _CAPABILITIES,
    "ActionRepresentation": _CAPABILITIES,
    "ActionShapePolicy": _CAPABILITIES,
    "ComponentDescriptor": _CAPABILITIES,
    "ComponentRole": _CAPABILITIES,
    "ExecutionCapabilities": _CAPABILITIES,
    "ExecutionMode": _CAPABILITIES,
    "GR00T_N1D6_ENTRY": "autovla.models.gr00t_n1d6.adapter",
    "GR00T_N1D6_FAMILY_SPEC": "autovla.models.gr00t.metadata",
    "GR00T_N1D6_METADATA_SPEC": _REGISTRY,
    "GR00T_SERIES_CANDIDATES": _REGISTRY,
    "Gr00tN1D6AdapterSkeleton": "autovla.models.gr00t_n1d6.adapter",
    "Gr00tN1D6DryRunBatchAdapter": "autovla.models.gr00t.batch_adapter",
    "InputCapabilities": _CAPABILITIES,
    "LicenseSpec": _FAMILY,
    "ModelAssetMetadata": _CONTRACTS,
    "ModelAssetsUnavailableError": _CONTRACTS,
    "ModelCapabilities": _CAPABILITIES,
    "ModelFamilyRegistry": _FAMILY,
    "ModelFamilySpec": _FAMILY,
    "ModelZooEntry": _CONTRACTS,
    "NormalizationCapabilities": _CAPABILITIES,
    "NormalizationMode": _CAPABILITIES,
    "OpenSourceReuseSpec": _FAMILY,
    "PI0_METADATA_SPEC": _REGISTRY,
    "PI05_METADATA_SPEC": _REGISTRY,
    "PI_ROADMAP_FAMILY_SPECS": "autovla.models.pi.metadata",
    "PI_SERIES_CANDIDATES": _REGISTRY,
    "ReleaseReference": _CONTRACTS,
    "SideEffectPermissions": _CAPABILITIES,
    "StatePolicy": _CAPABILITIES,
    "SupportState": _CAPABILITIES,
    "TEST_DOUBLE_FAMILY_SPEC": _REGISTRY,
    "build_gr00t_n1d6_adapter_skeleton": "autovla.models.gr00t_n1d6.adapter",
    "build_model_zoo_registry": _REGISTRY,
    "get": _REGISTRY,
    "get_model_family_spec": _REGISTRY,
    "get_model_zoo_entry": _REGISTRY,
    "list_model_family_candidates": _REGISTRY,
    "list_model_family_keys": _REGISTRY,
    "list_model_zoo_keys": _REGISTRY,
}

__all__ = [
    "GR00T_N1D6_ENTRY",
    "GR00T_N1D6_FAMILY_SPEC",
    "GR00T_N1D6_METADATA_SPEC",
    "GR00T_SERIES_CANDIDATES",
    "PI0_METADATA_SPEC",
    "PI05_METADATA_SPEC",
    "PI_ROADMAP_FAMILY_SPECS",
    "PI_SERIES_CANDIDATES",
    "TEST_DOUBLE_FAMILY_SPEC",
    "ActionCapabilities",
    "ActionMaskPolicy",
    "ActionRepresentation",
    "ActionShapePolicy",
    "ComponentDescriptor",
    "ComponentRole",
    "ExecutionCapabilities",
    "ExecutionMode",
    "Gr00tN1D6AdapterSkeleton",
    "Gr00tN1D6DryRunBatchAdapter",
    "InputCapabilities",
    "LicenseSpec",
    "ModelAssetMetadata",
    "ModelAssetsUnavailableError",
    "ModelCapabilities",
    "ModelFamilyRegistry",
    "ModelFamilySpec",
    "ModelZooEntry",
    "NormalizationCapabilities",
    "NormalizationMode",
    "OpenSourceReuseSpec",
    "ReleaseReference",
    "SideEffectPermissions",
    "StatePolicy",
    "SupportState",
    "build_gr00t_n1d6_adapter_skeleton",
    "build_model_zoo_registry",
    "get",
    "get_model_family_spec",
    "get_model_zoo_entry",
    "list_model_family_candidates",
    "list_model_family_keys",
    "list_model_zoo_keys",
]


def __getattr__(name: str) -> object:
    """按需解析模型公共导出并避免重型运行时初始化。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共导出名称。"""
    return sorted(set(globals()) | set(__all__))
