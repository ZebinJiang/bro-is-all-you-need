"""模型族规范键、兼容别名和轻量工厂身份注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping
from warnings import warn

from autovla.core.registry import ImportStringFactory
from autovla.models.families.gr00t_n1d6.specification import GR00T_N1D6_SPEC
from autovla.models.families.pi0.specification import PI0_SPEC
from autovla.models.families.pi0_5.specification import PI0_5_SPEC
from autovla.models.families.pi0_fast.specification import PI0_FAST_SPEC
from autovla.models.families.specification import ModelFamilyDefinition


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistration:
    """绑定一个规范定义和惰性组合/检查点工厂。"""

    spec: ModelFamilyDefinition
    factory: ImportStringFactory[object] | None
    checkpoint_adapter: ImportStringFactory[object] | None


class ModelFamilyRegistry:
    """不导入 Torch/Transformers/JAX/Flax 的不可变模型族注册表。"""

    def __init__(self, definitions: tuple[ModelFamilyDefinition, ...]) -> None:
        """冻结规范键、注册项和单向兼容别名。"""

        canonical = {definition.family_key: definition for definition in definitions}
        if len(canonical) != len(definitions):
            raise ValueError("duplicate canonical model family key")
        aliases: dict[str, str] = {}
        for definition in definitions:
            for alias in definition.compatibility_aliases:
                if alias in canonical or alias in aliases:
                    raise ValueError(f"duplicate model family alias: {alias!r}")
                aliases[alias] = definition.family_key
        registrations = {key: _registration(definition) for key, definition in canonical.items()}
        self._definitions: Mapping[str, ModelFamilyDefinition] = MappingProxyType(canonical)
        self._aliases: Mapping[str, str] = MappingProxyType(aliases)
        self._registrations: Mapping[str, ModelFamilyRegistration] = MappingProxyType(registrations)

    def canonical_key(self, key: str) -> str:
        """解析规范键;兼容键只发警告且不生成新对象。"""

        if key in self._definitions:
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

    def definition(self, key: str) -> ModelFamilyDefinition:
        """返回规范定义对象,别名严格保持对象身份。"""

        return self._definitions[self.canonical_key(key)]

    def registration(self, key: str) -> ModelFamilyRegistration:
        """返回同一规范定义对应的惰性工厂记录。"""

        return self._registrations[self.canonical_key(key)]

    def keys(self, *, include_aliases: bool = False) -> tuple[str, ...]:
        """列出四个生产键,可选追加弃用别名。"""

        keys = set(self._definitions)
        if include_aliases:
            keys.update(self._aliases)
        return tuple(sorted(keys))


def _registration(definition: ModelFamilyDefinition) -> ModelFamilyRegistration:
    """从规范定义构造不解析目标模块的工厂身份。"""

    if definition.factories.model is None:
        return ModelFamilyRegistration(definition, None, None)
    required = (
        ("PIL", "safetensors", "torch", "torchvision", "transformers")
        if definition.family_key == "gr00t_n1d6"
        else ()
    )
    factory: ImportStringFactory[object] = ImportStringFactory(
        definition.factories.model,
        optional_extra=definition.optional_extra,
        required_modules=required,
        metadata={
            "family_key": definition.family_key,
            "local_files_only": definition.local_files_only,
            "asset_keys": definition.asset_keys,
            "runtime_support": definition.runtime_support.value,
        },
    )
    checkpoint: ImportStringFactory[object] | None = (
        None
        if definition.factories.checkpoint is None
        else ImportStringFactory(
            definition.factories.checkpoint,
            optional_extra=definition.optional_extra,
            required_modules=("torch", "safetensors"),
        )
    )
    return ModelFamilyRegistration(definition, factory, checkpoint)


def build_model_family_registry() -> ModelFamilyRegistry:
    """构造四个生产模型族的规范注册表。"""

    return ModelFamilyRegistry((GR00T_N1D6_SPEC, PI0_SPEC, PI0_FAST_SPEC, PI0_5_SPEC))


_MODEL_FAMILIES = build_model_family_registry()


def get_model_family_registration(key: str) -> ModelFamilyRegistration:
    """返回模型族轻量注册项。"""

    return _MODEL_FAMILIES.registration(key)


def get_model_family_spec(key: str) -> ModelFamilyDefinition:
    """返回模型族唯一不可变定义。"""

    return _MODEL_FAMILIES.definition(key)


def list_model_family_keys(*, include_aliases: bool = False) -> tuple[str, ...]:
    """列举规范生产键;兼容键仅在显式请求时出现。"""

    return _MODEL_FAMILIES.keys(include_aliases=include_aliases)


def get(key: str) -> ModelFamilyDefinition:
    """保留历史查询名并返回规范定义。"""

    return get_model_family_spec(key)


ModelFactory = ImportStringFactory[object]
ModelProcessorFactory = ImportStringFactory[object]

__all__ = [
    "ModelFactory",
    "ModelFamilyRegistration",
    "ModelFamilyRegistry",
    "ModelProcessorFactory",
    "build_model_family_registry",
    "get",
    "get_model_family_registration",
    "get_model_family_spec",
    "list_model_family_keys",
]
