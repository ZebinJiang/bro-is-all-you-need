"""模型族元数据解析为轻量、可审计的组装计划。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from autovla.core.registry import ImportStringFactory
from autovla.data.transforms import TransformPlan
from autovla.models.capabilities import PrecisionSupport, TopologySupport
from autovla.models.families.specification import (
    DependencyClass,
    ModelFamilyDefinition,
    RuntimeSupportState,
)

if TYPE_CHECKING:
    from autovla.assets.contracts import ModelAssetBundle


class ModelRuntimeSupportError(RuntimeError):
    """在数据、资产或模型副作用前报告封闭运行时状态。"""

    def __init__(self, definition: ModelFamilyDefinition) -> None:
        """记录规范键和可机器读取的支持状态。"""

        super().__init__(
            f"model family {definition.family_key!r} cannot execute: "
            f"runtime_support={definition.runtime_support.value}"
        )
        self.family_key = definition.family_key
        self.runtime_support = definition.runtime_support


@runtime_checkable
class ModelConfigIdentity(Protocol):
    """限定通用装配所需的最小不可变配置身份。"""

    @property
    def family_key(self) -> str:
        """返回规范家族键。"""

        ...

    @property
    def fingerprint(self) -> str:
        """返回稳定 SHA256 配置身份。"""

        ...


@dataclass(frozen=True, slots=True)
class AssemblyFactories:
    """保存各组件规范 import-string,不在计划解析时导入目标。"""

    processor: ImportStringFactory[object]
    backbone: ImportStringFactory[object]
    action_head: ImportStringFactory[object]
    model: ImportStringFactory[object]
    checkpoint: ImportStringFactory[object]
    asset_bundle: ImportStringFactory[object] | None = None
    policy_bundle: ImportStringFactory[object] | None = None

    def to_json_dict(self) -> dict[str, str | None]:
        """返回工厂路径身份。"""

        return {
            "processor": self.processor.factory_path,
            "backbone": self.backbone.factory_path,
            "action_head": self.action_head.factory_path,
            "model": self.model.factory_path,
            "checkpoint": self.checkpoint.factory_path,
            "asset_bundle": None if self.asset_bundle is None else self.asset_bundle.factory_path,
            "policy_bundle": (
                None if self.policy_bundle is None else self.policy_bundle.factory_path
            ),
        }


@dataclass(frozen=True, slots=True)
class ModelAssemblyPlan:
    """绑定定义、配置、资产、R3 变换和 GPU 策略的轻量计划。"""

    definition: ModelFamilyDefinition
    config: ModelConfigIdentity
    asset_bundle: ModelAssetBundle
    factories: AssemblyFactories
    transform_plan: TransformPlan
    precision: PrecisionSupport
    topology: TopologySupport
    local_files_only: bool

    def __post_init__(self) -> None:
        """校验计划仍满足定义的精度、拓扑和本地资产策略。"""

        requirements = self.definition.assembly_requirements
        if requirements is None:
            raise ValueError("model family assembly requirements are missing")
        if self.precision not in requirements.precisions:
            raise ValueError(f"unsupported precision for {self.definition.family_key}")
        if self.topology not in requirements.topologies:
            raise ValueError(f"unsupported topology for {self.definition.family_key}")
        if not self.local_files_only or not self.definition.local_files_only:
            raise ValueError("model assembly must remain local_files_only")
        if self.config.family_key != self.definition.family_key:
            raise ValueError("typed config family_key must match canonical definition")
        if self.asset_bundle.family_key != self.definition.family_key:
            raise ValueError("verified asset bundle family_key must match canonical definition")
        self.asset_bundle.validate()
        for name, fingerprint in (
            ("config", self.config.fingerprint),
            ("asset bundle", self.asset_bundle.fingerprint),
            ("transform plan", self.transform_plan.fingerprint),
        ):
            if len(fingerprint) != 64 or any(
                character not in "0123456789abcdef" for character in fingerprint
            ):
                raise ValueError(f"{name} must expose a stable SHA256 fingerprint")

    @property
    def provenance_fingerprint(self) -> str:
        """组合定义、配置类型、资产和变换计划身份。"""

        config_fingerprint = self.config.fingerprint
        payload = {
            "definition": self.definition.fingerprint,
            "config_type": f"{type(self.config).__module__}:{type(self.config).__qualname__}",
            "config": config_fingerprint,
            "asset_bundle": self.asset_bundle.fingerprint,
            "factories": self.factories.to_json_dict(),
            "transform_plan": self.transform_plan.fingerprint,
            "precision": self.precision.value,
            "topology": self.topology.value,
            "local_files_only": self.local_files_only,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def resolve_model_assembly(
    family_key: str,
    *,
    config: ModelConfigIdentity | None = None,
    asset_bundle: ModelAssetBundle | None = None,
    transform_plan: TransformPlan | None = None,
    precision: PrecisionSupport | str = PrecisionSupport.BFLOAT16,
    topology: TopologySupport | str = TopologySupport.SINGLE_GPU,
) -> ModelAssemblyPlan:
    """先关闭非执行族,再验证完整资产和变换计划,最后生成惰性组装计划。"""

    from autovla.models.registry import get_model_family_spec

    definition = get_model_family_spec(family_key)
    if definition.runtime_support is not RuntimeSupportState.EXECUTABLE:
        # 此处必须早于配置、数据、资产或模型访问。
        raise ModelRuntimeSupportError(definition)
    if config is None or asset_bundle is None or transform_plan is None:
        raise ValueError(
            "executable model assembly requires config, asset bundle and TransformPlan"
        )
    config = _require_config_identity(config)
    asset_bundle = _require_asset_bundle(asset_bundle)
    precision_value = PrecisionSupport(precision)
    topology_value = TopologySupport(topology)
    paths = definition.factories
    if any(
        path is None
        for path in (
            paths.processor,
            paths.backbone,
            paths.action_head,
            paths.model,
            paths.checkpoint,
        )
    ):
        raise ValueError("executable definition has an incomplete component factory set")
    requirements = definition.assembly_requirements
    if requirements is None:
        raise ValueError("model family assembly requirements are missing")
    required_modules = tuple(
        item.module
        for item in requirements.dependencies.items
        if item.dependency_class
        in {
            DependencyClass.MANDATORY_RUNTIME,
            DependencyClass.OPTIONAL_FAMILY,
            DependencyClass.GPU_EXTENSION,
        }
    )
    factories = AssemblyFactories(
        processor=_factory(paths.processor, definition, required_modules),
        backbone=_factory(paths.backbone, definition, required_modules),
        action_head=_factory(paths.action_head, definition, required_modules),
        model=_factory(paths.model, definition, required_modules),
        checkpoint=_factory(paths.checkpoint, definition, required_modules),
        asset_bundle=_optional_factory(paths.asset_bundle, definition, required_modules),
        policy_bundle=_optional_factory(paths.policy_bundle, definition, required_modules),
    )
    return ModelAssemblyPlan(
        definition=definition,
        config=config,
        asset_bundle=asset_bundle,
        factories=factories,
        transform_plan=transform_plan,
        precision=precision_value,
        topology=topology_value,
        local_files_only=True,
    )


def _require_config_identity(value: object) -> ModelConfigIdentity:
    """执行运行时结构校验并返回窄化配置身份。"""

    if not isinstance(value, ModelConfigIdentity):
        raise TypeError("model config must satisfy ModelConfigIdentity")
    return value


def _require_asset_bundle(value: object) -> ModelAssetBundle:
    """惰性导入家族中立协议并执行运行时结构校验。"""

    from autovla.assets.contracts import ModelAssetBundle

    if not isinstance(value, ModelAssetBundle):
        raise TypeError("asset bundle must satisfy the verified ModelAssetBundle protocol")
    return value


def _factory(
    path: str | None,
    definition: ModelFamilyDefinition,
    required_modules: tuple[str, ...],
) -> ImportStringFactory[object]:
    """由已验证的非空路径构造惰性工厂身份。"""

    if path is None:
        raise ValueError("component factory path is missing")
    return ImportStringFactory(
        path,
        optional_extra=definition.optional_extra,
        required_modules=required_modules,
        metadata={"family_key": definition.family_key, "local_files_only": True},
    )


def _optional_factory(
    path: str | None,
    definition: ModelFamilyDefinition,
    required_modules: tuple[str, ...],
) -> ImportStringFactory[object] | None:
    """为尚未迁移的兼容家族保留显式空工厂。"""

    if path is None:
        return None
    return _factory(path, definition, required_modules)


__all__ = [
    "AssemblyFactories",
    "ModelAssemblyPlan",
    "ModelConfigIdentity",
    "ModelRuntimeSupportError",
    "resolve_model_assembly",
]
