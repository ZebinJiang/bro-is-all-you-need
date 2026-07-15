"""模型族元数据解析为轻量、可审计的组装计划。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from autovla.assets import Gr00tModelAssetBundle
from autovla.core.registry import ImportStringFactory
from autovla.data.transforms import TransformPlan
from autovla.models.families.specification import (
    ModelFamilyDefinition,
    RuntimeSupportState,
)
from autovla.models.registry import get_model_family_spec


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


@dataclass(frozen=True, slots=True)
class AssemblyFactories:
    """保存各组件规范 import-string,不在计划解析时导入目标。"""

    processor: ImportStringFactory[object]
    backbone: ImportStringFactory[object]
    action_head: ImportStringFactory[object]
    model: ImportStringFactory[object]
    checkpoint: ImportStringFactory[object]

    def to_json_dict(self) -> dict[str, str]:
        """返回工厂路径身份。"""

        return {
            "processor": self.processor.factory_path,
            "backbone": self.backbone.factory_path,
            "action_head": self.action_head.factory_path,
            "model": self.model.factory_path,
            "checkpoint": self.checkpoint.factory_path,
        }


@dataclass(frozen=True, slots=True)
class ModelAssemblyPlan:
    """绑定定义、配置、资产、R3 变换和 GPU 策略的轻量计划。"""

    definition: ModelFamilyDefinition
    config: object
    asset_bundle: Gr00tModelAssetBundle
    factories: AssemblyFactories
    transform_plan: TransformPlan
    precision: str
    topology: str
    local_files_only: bool

    def __post_init__(self) -> None:
        """校验计划仍满足定义的精度、拓扑和本地资产策略。"""

        if self.precision not in self.definition.supported_precisions:
            raise ValueError(f"unsupported precision for {self.definition.family_key}")
        if self.topology not in self.definition.supported_topologies:
            raise ValueError(f"unsupported topology for {self.definition.family_key}")
        if not self.local_files_only or not self.definition.local_files_only:
            raise ValueError("model assembly must remain local_files_only")
        family_key = getattr(self.config, "family_key", None)
        if family_key != self.definition.family_key:
            raise ValueError("typed config family_key must match canonical definition")

    @property
    def provenance_fingerprint(self) -> str:
        """组合定义、配置类型、资产和变换计划身份。"""

        config_fingerprint = getattr(self.config, "fingerprint", None)
        if not isinstance(config_fingerprint, str) or len(config_fingerprint) != 64:
            raise ValueError("typed config must expose a stable SHA256 fingerprint")
        payload = {
            "definition": self.definition.fingerprint,
            "config_type": f"{type(self.config).__module__}:{type(self.config).__qualname__}",
            "config": config_fingerprint,
            "asset_bundle": self.asset_bundle.fingerprint,
            "factories": self.factories.to_json_dict(),
            "transform_plan": self.transform_plan.fingerprint,
            "precision": self.precision,
            "topology": self.topology,
            "local_files_only": self.local_files_only,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def resolve_model_assembly(
    family_key: str,
    *,
    config: object | None = None,
    asset_bundle: Gr00tModelAssetBundle | None = None,
    transform_plan: TransformPlan | None = None,
    precision: str = "bfloat16",
    topology: str = "single_gpu",
) -> ModelAssemblyPlan:
    """先关闭非执行族,再验证完整资产和变换计划,最后生成惰性组装计划。"""

    definition = get_model_family_spec(family_key)
    if definition.runtime_support is not RuntimeSupportState.EXECUTABLE:
        # 此处必须早于配置、数据、资产或模型访问。
        raise ModelRuntimeSupportError(definition)
    if config is None or asset_bundle is None or transform_plan is None:
        raise ValueError(
            "executable model assembly requires config, asset bundle and TransformPlan"
        )
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
    required_modules = ("torch", "transformers")
    factories = AssemblyFactories(
        processor=_factory(paths.processor, definition, required_modules),
        backbone=_factory(paths.backbone, definition, required_modules),
        action_head=_factory(paths.action_head, definition, ("torch",)),
        model=_factory(paths.model, definition, required_modules),
        checkpoint=_factory(paths.checkpoint, definition, ("torch", "safetensors")),
    )
    return ModelAssemblyPlan(
        definition=definition,
        config=config,
        asset_bundle=asset_bundle,
        factories=factories,
        transform_plan=transform_plan,
        precision=precision,
        topology=topology,
        local_files_only=True,
    )


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


__all__ = [
    "AssemblyFactories",
    "ModelAssemblyPlan",
    "ModelRuntimeSupportError",
    "resolve_model_assembly",
]
