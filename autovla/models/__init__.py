"""AutoVLA M5 模型接口及弃用兼容/测试名称的轻量懒导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.models.capabilities import ActionCapabilities as ActionCapabilities
    from autovla.models.capabilities import ActionMaskPolicy as ActionMaskPolicy
    from autovla.models.capabilities import ActionRepresentation as ActionRepresentation
    from autovla.models.capabilities import ActionShapePolicy as ActionShapePolicy
    from autovla.models.capabilities import ComponentDescriptor as ComponentDescriptor
    from autovla.models.capabilities import ComponentRole as ComponentRole
    from autovla.models.capabilities import ExecutionCapabilities as ExecutionCapabilities
    from autovla.models.capabilities import ExecutionMode as ExecutionMode
    from autovla.models.capabilities import InputCapabilities as InputCapabilities
    from autovla.models.capabilities import ModelCapabilities as ModelCapabilities
    from autovla.models.capabilities import (
        NormalizationCapabilities as NormalizationCapabilities,
    )
    from autovla.models.capabilities import NormalizationMode as NormalizationMode
    from autovla.models.capabilities import SideEffectPermissions as SideEffectPermissions
    from autovla.models.capabilities import StatePolicy as StatePolicy
    from autovla.models.capabilities import SupportState as SupportState
    from autovla.models.contracts import ModelAssetMetadata as ModelAssetMetadata
    from autovla.models.contracts import (
        ModelAssetsUnavailableError as ModelAssetsUnavailableError,
    )
    from autovla.models.contracts import ModelZooEntry as ModelZooEntry
    from autovla.models.contracts import ReleaseReference as ReleaseReference
    from autovla.models.families.specification import (
        ModelFamilyDefinition as ModelFamilyDefinition,
    )
    from autovla.models.families.specification import ModelFamilySpec as ModelFamilySpec
    from autovla.models.families.specification import (
        RuntimeSupportState as RuntimeSupportState,
    )
    from autovla.models.family import LicenseSpec as LicenseSpec
    from autovla.models.family import OpenSourceReuseSpec as OpenSourceReuseSpec
    from autovla.models.gr00t.batch_adapter import (
        Gr00tN1D6DryRunBatchAdapter as Gr00tN1D6DryRunBatchAdapter,
    )
    from autovla.models.gr00t.metadata import GR00T_N1D6_FAMILY_SPEC as GR00T_N1D6_FAMILY_SPEC
    from autovla.models.gr00t_n1d6.adapter import GR00T_N1D6_ENTRY as GR00T_N1D6_ENTRY
    from autovla.models.gr00t_n1d6.adapter import (
        Gr00tN1D6AdapterSkeleton as Gr00tN1D6AdapterSkeleton,
    )
    from autovla.models.gr00t_n1d6.adapter import (
        build_gr00t_n1d6_adapter_skeleton as build_gr00t_n1d6_adapter_skeleton,
    )
    from autovla.models.interfaces import ActionHead as ActionHead
    from autovla.models.interfaces import ModelCheckpointAdapter as ModelCheckpointAdapter
    from autovla.models.interfaces import ModelProcessor as ModelProcessor
    from autovla.models.interfaces import VisionLanguageActionModel as VisionLanguageActionModel
    from autovla.models.interfaces import VisionLanguageBackbone as VisionLanguageBackbone
    from autovla.models.pi.metadata import PI_ROADMAP_FAMILY_SPECS as PI_ROADMAP_FAMILY_SPECS
    from autovla.models.registry import ModelFamilyRegistration as ModelFamilyRegistration
    from autovla.models.registry import ModelFamilyRegistry as ModelFamilyRegistry
    from autovla.models.registry import get as get
    from autovla.models.registry import (
        get_model_family_registration as get_model_family_registration,
    )
    from autovla.models.registry import get_model_family_spec as get_model_family_spec
    from autovla.models.registry import list_model_family_keys as list_model_family_keys
    from autovla.testing.models.legacy_registry import (
        GR00T_N1D6_METADATA_SPEC as GR00T_N1D6_METADATA_SPEC,
    )
    from autovla.testing.models.legacy_registry import (
        GR00T_SERIES_CANDIDATES as GR00T_SERIES_CANDIDATES,
    )
    from autovla.testing.models.legacy_registry import PI0_METADATA_SPEC as PI0_METADATA_SPEC
    from autovla.testing.models.legacy_registry import PI05_METADATA_SPEC as PI05_METADATA_SPEC
    from autovla.testing.models.legacy_registry import (
        PI_SERIES_CANDIDATES as PI_SERIES_CANDIDATES,
    )
    from autovla.testing.models.legacy_registry import (
        TEST_DOUBLE_FAMILY_SPEC as TEST_DOUBLE_FAMILY_SPEC,
    )
    from autovla.testing.models.legacy_registry import (
        build_model_zoo_registry as build_model_zoo_registry,
    )
    from autovla.testing.models.legacy_registry import (
        get_model_zoo_entry as get_model_zoo_entry,
    )
    from autovla.testing.models.legacy_registry import (
        list_model_family_candidates as list_model_family_candidates,
    )
    from autovla.testing.models.legacy_registry import list_model_zoo_keys as list_model_zoo_keys

_LEGACY_REGISTRY = "autovla.testing.models.legacy_registry"
_EXPORTS = {
    "ActionCapabilities": "autovla.models.capabilities",
    "ActionHead": "autovla.models.interfaces",
    "ActionMaskPolicy": "autovla.models.capabilities",
    "ActionRepresentation": "autovla.models.capabilities",
    "ActionShapePolicy": "autovla.models.capabilities",
    "ComponentDescriptor": "autovla.models.capabilities",
    "ComponentRole": "autovla.models.capabilities",
    "ExecutionCapabilities": "autovla.models.capabilities",
    "ExecutionMode": "autovla.models.capabilities",
    "GR00T_N1D6_ENTRY": "autovla.models.gr00t_n1d6.adapter",
    "GR00T_N1D6_FAMILY_SPEC": "autovla.models.gr00t.metadata",
    "GR00T_N1D6_METADATA_SPEC": _LEGACY_REGISTRY,
    "GR00T_SERIES_CANDIDATES": _LEGACY_REGISTRY,
    "Gr00tN1D6AdapterSkeleton": "autovla.models.gr00t_n1d6.adapter",
    "Gr00tN1D6DryRunBatchAdapter": "autovla.models.gr00t.batch_adapter",
    "InputCapabilities": "autovla.models.capabilities",
    "LicenseSpec": "autovla.models.family",
    "ModelAssetMetadata": "autovla.models.contracts",
    "ModelAssetsUnavailableError": "autovla.models.contracts",
    "ModelCapabilities": "autovla.models.capabilities",
    "ModelCheckpointAdapter": "autovla.models.interfaces",
    "ModelFamilyRegistration": "autovla.models.registry",
    "ModelFamilyRegistry": "autovla.models.registry",
    "ModelFamilyDefinition": "autovla.models.families.specification",
    "ModelFamilySpec": "autovla.models.families.specification",
    "ModelProcessor": "autovla.models.interfaces",
    "ModelZooEntry": "autovla.models.contracts",
    "NormalizationCapabilities": "autovla.models.capabilities",
    "NormalizationMode": "autovla.models.capabilities",
    "OpenSourceReuseSpec": "autovla.models.family",
    "PI0_METADATA_SPEC": _LEGACY_REGISTRY,
    "PI05_METADATA_SPEC": _LEGACY_REGISTRY,
    "PI_ROADMAP_FAMILY_SPECS": "autovla.models.pi.metadata",
    "PI_SERIES_CANDIDATES": _LEGACY_REGISTRY,
    "ReleaseReference": "autovla.models.contracts",
    "RuntimeSupportState": "autovla.models.families.specification",
    "SideEffectPermissions": "autovla.models.capabilities",
    "StatePolicy": "autovla.models.capabilities",
    "SupportState": "autovla.models.capabilities",
    "TEST_DOUBLE_FAMILY_SPEC": _LEGACY_REGISTRY,
    "VisionLanguageActionModel": "autovla.models.interfaces",
    "VisionLanguageBackbone": "autovla.models.interfaces",
    "build_gr00t_n1d6_adapter_skeleton": "autovla.models.gr00t_n1d6.adapter",
    "build_model_zoo_registry": _LEGACY_REGISTRY,
    "get": "autovla.models.registry",
    "get_model_family_registration": "autovla.models.registry",
    "get_model_family_spec": "autovla.models.registry",
    "get_model_zoo_entry": _LEGACY_REGISTRY,
    "list_model_family_candidates": _LEGACY_REGISTRY,
    "list_model_family_keys": "autovla.models.registry",
    "list_model_zoo_keys": _LEGACY_REGISTRY,
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
    "ActionHead",
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
    "ModelCheckpointAdapter",
    "ModelFamilyDefinition",
    "ModelFamilyRegistration",
    "ModelFamilyRegistry",
    "ModelFamilySpec",
    "ModelProcessor",
    "ModelZooEntry",
    "NormalizationCapabilities",
    "NormalizationMode",
    "OpenSourceReuseSpec",
    "ReleaseReference",
    "RuntimeSupportState",
    "SideEffectPermissions",
    "StatePolicy",
    "SupportState",
    "VisionLanguageActionModel",
    "VisionLanguageBackbone",
    "build_gr00t_n1d6_adapter_skeleton",
    "build_model_zoo_registry",
    "get",
    "get_model_family_registration",
    "get_model_family_spec",
    "get_model_zoo_entry",
    "list_model_family_candidates",
    "list_model_family_keys",
    "list_model_zoo_keys",
]


def __getattr__(name: str) -> object:
    """按需解析生产或弃用兼容模型导出并避免重型运行时初始化。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共名称,其中旧模型族名称仅用于弃用兼容/测试。"""
    return sorted(set(globals()) | set(__all__))
