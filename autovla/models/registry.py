"""M10 模型族清单、惰性定义解析和组件工厂注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from types import MappingProxyType
from typing import Mapping
from warnings import warn

from autovla.core.registry import ImportStringFactory
from autovla.models.families.specification import (
    DependencyClass,
    ModelFamilyDefinition,
)


class ModelFamilyLifecycleState(str, Enum):
    """描述家族是否属于当前活跃生产动物园。"""

    ACTIVE = "active"
    DEFERRED_BY_USER_PRIORITY = "DEFERRED_BY_USER_PRIORITY"


@dataclass(frozen=True, slots=True)
class ModelFamilyCatalogEntry:
    """保存不会导入家族实现的清单身份。"""

    family_key: str
    definition_path: str
    lifecycle: ModelFamilyLifecycleState
    compatibility_aliases: tuple[str, ...] = ()
    runtime_profile_id: str = ""
    asset_gate: str = ""
    accepted_evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验键、导入路径和别名保持闭合。"""

        if not self.family_key or self.family_key != self.family_key.strip():
            raise ValueError("model family key must be canonical non-empty text")
        module_name, separator, symbol = self.definition_path.partition(":")
        if not separator or not module_name or not symbol:
            raise ValueError("definition_path must use module:symbol")
        if type(self.lifecycle) is not ModelFamilyLifecycleState:
            raise TypeError("lifecycle must use ModelFamilyLifecycleState")
        if len(set(self.compatibility_aliases)) != len(self.compatibility_aliases):
            raise ValueError("model family aliases must be unique")
        if not self.runtime_profile_id.strip() or not self.asset_gate.strip():
            raise ValueError("active model family runtime profile and asset gate are required")
        if len(set(self.accepted_evidence_ids)) != len(self.accepted_evidence_ids) or any(
            not item.strip() for item in self.accepted_evidence_ids
        ):
            raise ValueError("accepted evidence ids must be non-empty and unique")

    @property
    def active(self) -> bool:
        """返回该家族是否属于 M10 活跃集合。"""

        return self.lifecycle is ModelFamilyLifecycleState.ACTIVE


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistration:
    """绑定一个规范定义和惰性组合/检查点工厂。"""

    spec: ModelFamilyDefinition
    factory: ImportStringFactory[object] | None
    checkpoint_adapter: ImportStringFactory[object] | None
    asset_bundle: ImportStringFactory[object] | None
    runtime_bundle: ImportStringFactory[object]
    runtime_profile_id: str
    lifecycle: ModelFamilyLifecycleState


_CATALOG = (
    ModelFamilyCatalogEntry(
        "gr00t_n1d6",
        "autovla.models.families.gr00t_n1d6.specification:GR00T_N1D6_SPEC",
        ModelFamilyLifecycleState.ACTIVE,
        ("gr00t-n1d6", "gr00t_n1d6_metadata"),
        "gr00t_n1d6_runtime",
        "BLOCKED_C3_DATA",
        (
            "M11_N1D6_EXECUTABLE_SOURCE_ACCEPTED",
            "M11_WAVE4_N1D6_ASSET_BUNDLE_ACCEPTED",
            "C2R7_ONE_A100_STRICT_CHECKPOINT_LOAD_ACCEPTED",
        ),
    ),
    ModelFamilyCatalogEntry(
        "gr00t_n1d7",
        "autovla.models.families.gr00t_n1d7.family:GR00T_N1D7_FAMILY",
        ModelFamilyLifecycleState.ACTIVE,
        ("gr00t-n1d7",),
        "gr00t_n1d7_runtime",
        "BLOCKED_LICENSE",
        ("M11_N1D7_EXECUTABLE_SOURCE_ACCEPTED",),
    ),
    ModelFamilyCatalogEntry(
        "pi0_5",
        "autovla.models.families.pi0_5.family:PI05_SPEC",
        ModelFamilyLifecycleState.ACTIVE,
        ("pi05-roadmap", "pi05_metadata"),
        "pi0_5_runtime",
        "BLOCKED_LICENSE",
        ("M11_PI05_EXECUTABLE_SOURCE_ACCEPTED",),
    ),
    ModelFamilyCatalogEntry(
        "pi0",
        "autovla.models.families.pi0.specification:PI0_SPEC",
        ModelFamilyLifecycleState.DEFERRED_BY_USER_PRIORITY,
        ("pi0-roadmap", "pi0_metadata"),
        "deferred",
        "DEFERRED_BY_USER_PRIORITY",
    ),
    ModelFamilyCatalogEntry(
        "pi0_fast",
        "autovla.models.families.pi0_fast.specification:PI0_FAST_SPEC",
        ModelFamilyLifecycleState.DEFERRED_BY_USER_PRIORITY,
        ("pi0-fast-roadmap",),
        "deferred",
        "DEFERRED_BY_USER_PRIORITY",
    ),
)


class ModelFamilyRegistry:
    """不导入 Torch/Transformers/JAX/Flax 的惰性模型族注册表。"""

    def __init__(self, entries: tuple[ModelFamilyCatalogEntry, ...] = _CATALOG) -> None:
        """冻结清单键、别名和按需解析缓存。"""

        catalog = {entry.family_key: entry for entry in entries}
        if len(catalog) != len(entries):
            raise ValueError("duplicate canonical model family key")
        aliases: dict[str, str] = {}
        for entry in entries:
            for alias in entry.compatibility_aliases:
                if alias in catalog or alias in aliases:
                    raise ValueError(f"duplicate model family alias: {alias!r}")
                aliases[alias] = entry.family_key
        self._catalog: Mapping[str, ModelFamilyCatalogEntry] = MappingProxyType(catalog)
        self._aliases: Mapping[str, str] = MappingProxyType(aliases)
        self._definitions: dict[str, ModelFamilyDefinition] = {}
        self._registrations: dict[str, ModelFamilyRegistration] = {}

    def canonical_key(self, key: str) -> str:
        """解析规范键;兼容键只发警告且不生成新对象。"""

        if key in self._catalog:
            return key
        try:
            canonical = self._aliases[key]
        except KeyError as exc:
            raise KeyError(f"unknown model family: {key!r}") from exc
        warn(
            f"model family key {key!r} is deprecated; use {canonical!r}",
            DeprecationWarning,
            stacklevel=3,
        )
        return canonical

    def catalog_entry(self, key: str) -> ModelFamilyCatalogEntry:
        """返回不触发家族导入的活跃/延后清单记录。"""

        return self._catalog[self.canonical_key(key)]

    def definition(self, key: str) -> ModelFamilyDefinition:
        """只在明确查询时导入一个家族的唯一规范定义。"""

        canonical = self.canonical_key(key)
        cached = self._definitions.get(canonical)
        if cached is not None:
            return cached
        entry = self._catalog[canonical]
        module_name, _, symbol = entry.definition_path.partition(":")
        definition = getattr(import_module(module_name), symbol)
        if not isinstance(definition, ModelFamilyDefinition):
            raise TypeError(f"model family definition has invalid type: {entry.definition_path}")
        if definition.family_key != canonical:
            raise ValueError("model family definition key does not match its catalog entry")
        self._definitions[canonical] = definition
        return definition

    def registration(self, key: str) -> ModelFamilyRegistration:
        """按需返回同一规范定义对应的惰性组件工厂记录。"""

        canonical = self.canonical_key(key)
        cached = self._registrations.get(canonical)
        if cached is not None:
            return cached
        entry = self._catalog[canonical]
        registration = _registration(self.definition(canonical), entry.lifecycle)
        self._registrations[canonical] = registration
        return registration

    def keys(
        self,
        *,
        include_deferred: bool = False,
        include_aliases: bool = False,
    ) -> tuple[str, ...]:
        """默认列出三个活跃键,可显式加入延后家族及兼容别名。"""

        selected = {key for key, entry in self._catalog.items() if include_deferred or entry.active}
        if include_aliases:
            selected.update(
                alias for alias, canonical in self._aliases.items() if canonical in selected
            )
        return tuple(sorted(selected))

    def entries(self, *, include_deferred: bool = False) -> tuple[ModelFamilyCatalogEntry, ...]:
        """按规范键返回不导入家族模块的稳定清单。"""

        return tuple(
            self._catalog[key]
            for key in sorted(self._catalog)
            if include_deferred or self._catalog[key].active
        )


def _registration(
    definition: ModelFamilyDefinition,
    lifecycle: ModelFamilyLifecycleState,
) -> ModelFamilyRegistration:
    """从家族拥有的依赖和工厂路径构造惰性注册项。"""

    runtime_bundle: ImportStringFactory[object] = ImportStringFactory(
        "autovla.models.assembly.runtime:ModelRuntimeBundle",
        metadata={
            "family_key": definition.family_key,
            "contract": "canonical_model_runtime_bundle",
        },
    )
    catalog_entry = next(item for item in _CATALOG if item.family_key == definition.family_key)
    if definition.factories.model is None:
        return ModelFamilyRegistration(
            definition,
            None,
            None,
            None,
            runtime_bundle,
            catalog_entry.runtime_profile_id,
            lifecycle,
        )
    requirements = definition.assembly_requirements
    if requirements is None:
        raise ValueError("model family assembly requirements are missing")
    runtime_classes = {DependencyClass.MANDATORY_RUNTIME, DependencyClass.OPTIONAL_FAMILY}
    required_modules = tuple(
        sorted(
            item.module
            for item in requirements.dependencies.items
            if item.dependency_class in runtime_classes
        )
    )
    factory: ImportStringFactory[object] = ImportStringFactory(
        definition.factories.model,
        optional_extra=definition.optional_extra,
        required_modules=required_modules,
        metadata={
            "family_key": definition.family_key,
            "local_files_only": definition.local_files_only,
            "asset_keys": definition.asset_keys,
            "runtime_support": requirements.runtime_level.value,
            "lifecycle": lifecycle.value,
        },
    )
    checkpoint_modules = tuple(
        module for module in ("safetensors", "torch") if module in required_modules
    )
    checkpoint: ImportStringFactory[object] | None = (
        None
        if definition.factories.checkpoint is None
        else ImportStringFactory(
            definition.factories.checkpoint,
            optional_extra=definition.optional_extra,
            required_modules=checkpoint_modules,
        )
    )
    asset_bundle: ImportStringFactory[object] | None = (
        None
        if definition.factories.asset_bundle is None
        else ImportStringFactory(
            definition.factories.asset_bundle,
            optional_extra=definition.optional_extra,
            metadata={"family_key": definition.family_key, "verified_receipts_required": True},
        )
    )
    return ModelFamilyRegistration(
        definition,
        factory,
        checkpoint,
        asset_bundle,
        runtime_bundle,
        catalog_entry.runtime_profile_id,
        lifecycle,
    )


def build_model_family_registry() -> ModelFamilyRegistry:
    """构造 M10 三活跃、两延后的惰性模型族注册表。"""

    return ModelFamilyRegistry()


_MODEL_FAMILIES = build_model_family_registry()


def get_model_family_catalog_entry(key: str) -> ModelFamilyCatalogEntry:
    """返回不触发家族运行时导入的清单记录。"""

    return _MODEL_FAMILIES.catalog_entry(key)


def get_model_family_registration(key: str) -> ModelFamilyRegistration:
    """返回模型族轻量注册项。"""

    return _MODEL_FAMILIES.registration(key)


def get_model_family_spec(key: str) -> ModelFamilyDefinition:
    """返回模型族唯一不可变定义。"""

    return _MODEL_FAMILIES.definition(key)


def list_model_family_catalog(
    *, include_deferred: bool = False
) -> tuple[ModelFamilyCatalogEntry, ...]:
    """列出不触发家族导入的活跃或完整清单。"""

    return _MODEL_FAMILIES.entries(include_deferred=include_deferred)


def list_model_family_keys(
    *,
    include_deferred: bool = False,
    include_aliases: bool = False,
) -> tuple[str, ...]:
    """默认列出活跃键;延后家族与兼容键均需显式请求。"""

    return _MODEL_FAMILIES.keys(
        include_deferred=include_deferred,
        include_aliases=include_aliases,
    )


def get(key: str) -> ModelFamilyDefinition:
    """保留历史查询名并返回规范定义。"""

    return get_model_family_spec(key)


ModelFactory = ImportStringFactory[object]
ModelProcessorFactory = ImportStringFactory[object]

__all__ = [
    "ModelFactory",
    "ModelFamilyCatalogEntry",
    "ModelFamilyLifecycleState",
    "ModelFamilyRegistration",
    "ModelFamilyRegistry",
    "ModelProcessorFactory",
    "build_model_family_registry",
    "get",
    "get_model_family_catalog_entry",
    "get_model_family_registration",
    "get_model_family_spec",
    "list_model_family_catalog",
    "list_model_family_keys",
]
