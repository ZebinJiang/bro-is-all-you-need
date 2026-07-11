"""AutoVLA 模型族的轻量懒注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from warnings import warn

from autovla.core.registry import ComponentRegistry, ImportStringFactory
from autovla.models.families.specification import ModelFamilySpec


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistration:
    """绑定可列举规范、可选模型工厂和 checkpoint 适配器。"""

    spec: ModelFamilySpec
    factory: ImportStringFactory[object] | None
    checkpoint_adapter: ImportStringFactory[object] | None


class ModelFamilyRegistry(ComponentRegistry[ModelFamilyRegistration]):
    """保存模型族元数据,查询和列举不会导入重型运行时。"""


def build_model_family_registry() -> ModelFamilyRegistry:
    """构造 GR00T 实现与 Pi 规范注册表。"""
    from autovla.models.families.gr00t_n1d6.registration import registration as gr00t
    from autovla.models.families.pi0.registration import registration as pi0
    from autovla.models.families.pi0_5.registration import registration as pi0_5

    registry = ModelFamilyRegistry("autovla-model-families")
    gr00t_entry = gr00t()
    registry.register(
        gr00t_entry.key,
        ModelFamilyRegistration(
            spec=gr00t_entry.spec,
            factory=ImportStringFactory(
                gr00t_entry.spec.factory_path or "",
                optional_extra="model-gr00t-n1d6",
                required_modules=(
                    "diffusers",
                    "PIL",
                    "safetensors",
                    "torch",
                    "torchvision",
                    "transformers",
                ),
                metadata=gr00t_entry.factory.metadata,
            ),
            checkpoint_adapter=ImportStringFactory(
                "autovla.models.families.gr00t_n1d6.checkpoint:Gr00tN1d6CheckpointAdapter",
                optional_extra="model-gr00t-n1d6",
                required_modules=("torch", "safetensors"),
            ),
        ),
        aliases=gr00t_entry.aliases,
    )
    for specification in (pi0(), pi0_5()):
        registry.register(
            specification.family_key,
            ModelFamilyRegistration(
                spec=specification,
                factory=None,
                checkpoint_adapter=None,
            ),
        )
    return registry


_MODEL_FAMILIES = build_model_family_registry()
_DEPRECATED_ALIASES = frozenset(("gr00t-n1d6", "gr00t_n1d6_metadata"))


def get_model_family_registration(key: str) -> ModelFamilyRegistration:
    """返回模型族注册项,旧 GR00T 键只发出弃用提示。"""
    if key in _DEPRECATED_ALIASES:
        warn(
            f"model family key {key!r} is deprecated; use 'gr00t_n1d6'",
            DeprecationWarning,
            stacklevel=2,
        )
    return _MODEL_FAMILIES.get(key)


def get_model_family_spec(key: str) -> ModelFamilySpec:
    """返回依赖轻量的模型族规范。"""
    return get_model_family_registration(key).spec


def list_model_family_keys(*, include_aliases: bool = False) -> tuple[str, ...]:
    """列举规范模型族键,可显式包含弃用别名。"""
    return _MODEL_FAMILIES.names(include_aliases=include_aliases)


def get(key: str) -> ModelFamilySpec:
    """保留历史 ``get`` 名称并返回规范模型族规格。"""
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
