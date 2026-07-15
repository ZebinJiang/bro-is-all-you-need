"""GR00T N1.6.1 本地双资产包模型工厂。"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Mapping
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

from autovla.assets import EAGLE_SUPPORT_SUBDIRECTORY
from autovla.core.registry.errors import OptionalDependencyError
from autovla.models.assembly import (
    AssemblyEvidenceIdentity,
    CheckpointLoadEvidence,
    ModelAssemblyRequest,
    ModelAssemblyResult,
    TuningFreezeEvidence,
    resolve_model_assembly,
)
from autovla.models.families.gr00t_n1d6.assets import Gr00tN1d6AssetBundle

if TYPE_CHECKING:
    from autovla.models.families.gr00t_n1d6.checkpoint import UpstreamCheckpointLayout
    from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
    from autovla.models.families.gr00t_n1d6.model import Gr00tN1d6Model
    from autovla.models.families.gr00t_n1d6.processor import Gr00tN1d6Processor
    from autovla.models.outputs import CheckpointLoadReport


class _LocalEagleConfigLike(Protocol):
    """描述工厂在重型依赖导入前使用的轻量 Eagle 配置。"""

    @property
    def visual_tokens_per_image(self) -> int:
        """返回已验证视觉 token 数。"""

        ...

    def with_family_image_size(self, image_size: int) -> "_LocalEagleConfigLike":
        """投影并验证 family 图像尺寸。"""

        ...


class _LocalEagleConfigType(Protocol):
    """描述轻量配置类的本地 JSON 构造边界。"""

    def from_local_json(self, path: str | Path) -> _LocalEagleConfigLike:
        """从本地 JSON 返回配置。"""

        ...


class _ObjectConstructor(Protocol):
    """描述延迟模型组件类的构造调用。"""

    def __call__(self, *args: object, **kwargs: object) -> object:
        """构造一个延迟导入组件。"""

        ...


class _LocalEagleProcessorType(Protocol):
    """描述 Eagle processor 的本地资产类方法。"""

    def from_local_assets(
        self,
        asset: object,
        config: _LocalEagleConfigLike,
        *,
        asset_subdirectory: str,
    ) -> object:
        """从受管本地资产构造处理器。"""

        ...


class _CheckpointAdapterLike(Protocol):
    """描述工厂使用的 checkpoint 静态检查和加载调用。"""

    def inspect_upstream_layout(self, path: object) -> object:
        """返回官方索引布局。"""

        ...

    def load_local(
        self,
        model: object,
        path: object,
        *,
        strictness: str,
    ) -> object:
        """把本地 checkpoint 加载到已构造模型。"""

        ...


class _TensorLike(Protocol):
    """描述无需复制即可读取元素数量的模型状态张量。"""

    def numel(self) -> int:
        """返回张量元素数量。"""

        ...


class _StateDictModelLike(Protocol):
    """描述 checkpoint 证据计数需要的模型状态接口。"""

    def state_dict(self) -> Mapping[str, _TensorLike]:
        """返回引用现有参数和缓冲区的状态映射。"""

        ...


def _required_type(module: ModuleType, name: str) -> type[object]:
    """从延迟模块读取一个必需类并拒绝动态缺失。"""
    value: object = getattr(module, name, None)
    if not isinstance(value, type):
        raise TypeError(f"runtime module lacks required type {name}")
    return value


def _loaded_tensor_element_count(
    model: _StateDictModelLike,
    report: "CheckpointLoadReport",
) -> int:
    """严格核对加载报告并统计已映射状态张量的元素总数。"""

    state = model.state_dict()
    groups = {
        "mapped_keys": report.mapped_keys,
        "missing_keys": report.missing_keys,
        "shape_mismatches": report.shape_mismatches,
        "unexpected_keys": report.unexpected_keys,
    }
    for field_name, keys in groups.items():
        if any(not isinstance(key, str) or not key for key in keys):
            raise ValueError(f"checkpoint report {field_name} must contain non-empty strings")
        if len(set(keys)) != len(keys):
            raise ValueError(f"checkpoint report {field_name} must contain unique keys")

    mapped = set(report.mapped_keys)
    missing = set(report.missing_keys)
    mismatched = set(report.shape_mismatches)
    unexpected = set(report.unexpected_keys)
    if mapped & missing or mapped & mismatched or missing & mismatched:
        raise ValueError("checkpoint report model-key classifications must be disjoint")

    model_keys = set(state)
    classified_model_keys = mapped | missing | mismatched
    if classified_model_keys != model_keys or unexpected & model_keys:
        raise ValueError("checkpoint report keys are inconsistent with post-load model state")

    loaded_element_count = 0
    for key in report.mapped_keys:
        element_count = state[key].numel()
        if type(element_count) is not int or element_count < 0:
            raise ValueError(f"model state tensor {key!r} returned an invalid element count")
        loaded_element_count += element_count
    return loaded_element_count


def _load_eagle_config(
    path: str | Path,
    *,
    family_image_size: int | None,
) -> _LocalEagleConfigLike:
    """绕过 Eagle 包的重型 ``__init__`` 并加载同一 canonical 子模块。"""
    module_name = "autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration"
    module = sys.modules.get(module_name)
    if module is None:
        source = Path(__file__).parent / "_nvidia/eagle/configuration.py"
        spec = importlib.util.spec_from_file_location(module_name, source)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot load local Eagle configuration module")
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        try:
            spec.loader.exec_module(module)
        except BaseException:
            sys.modules.pop(module_name, None)
            raise
    raw_type = getattr(module, "LocalEagleConfig", None)
    if not isinstance(raw_type, type):
        raise TypeError("local Eagle configuration module lacks LocalEagleConfig")
    config_type = cast(_LocalEagleConfigType, raw_type)
    config = config_type.from_local_json(path)
    return config if family_image_size is None else config.with_family_image_size(family_image_size)


def _family_request(
    request: ModelAssemblyRequest,
) -> tuple["Gr00tN1d6Config", Gr00tN1d6AssetBundle]:
    """校验组件工厂共享的请求、配置和资产包身份。"""

    if not isinstance(request, ModelAssemblyRequest):
        raise TypeError("GR00T N1.6 component factory requires ModelAssemblyRequest")
    raw_config = request.config
    if (
        type(raw_config).__module__ != "autovla.models.families.gr00t_n1d6.config"
        or type(raw_config).__qualname__ != "Gr00tN1d6Config"
    ):
        raise TypeError("GR00T N1.6 assembly requires Gr00tN1d6Config")
    if not isinstance(request.asset_bundle, Gr00tN1d6AssetBundle):
        raise TypeError("GR00T N1.6 assembly requires Gr00tN1d6AssetBundle")
    return cast("Gr00tN1d6Config", raw_config), request.asset_bundle


class _Gr00tN1d6ProcessorFactory:
    """从同一共享请求构造本地 Eagle processor。"""

    def __call__(self, request: ModelAssemblyRequest) -> object:
        """验证资产和依赖后构造处理器。"""

        config, bundle = _family_request(request)
        eagle_config = _load_eagle_config(
            bundle.eagle_root / "config.json", family_image_size=config.image_size
        )
        Gr00tN1d6ModelFactory._require_dependencies()
        processing = importlib.import_module(
            "autovla.models.families.gr00t_n1d6._nvidia.eagle.processing"
        )
        processor_module = importlib.import_module("autovla.models.families.gr00t_n1d6.processor")
        eagle_processor_type = cast(
            _LocalEagleProcessorType, _required_type(processing, "LocalEagleProcessor")
        )
        eagle_processor = eagle_processor_type.from_local_assets(
            bundle.eagle_support,
            eagle_config,
            asset_subdirectory=EAGLE_SUPPORT_SUBDIRECTORY,
        )
        constructor = cast(
            _ObjectConstructor, _required_type(processor_module, "Gr00tN1d6Processor")
        )
        return constructor(
            config,
            eagle_processor,
            visual_tokens_per_image=eagle_config.visual_tokens_per_image,
        )


class _Gr00tN1d6BackboneFactory:
    """从同一共享请求构造本地 Eagle backbone。"""

    def __call__(self, request: ModelAssemblyRequest) -> object:
        """在显式初始化上下文内构造 backbone。"""

        config, bundle = _family_request(request)
        eagle_config = _load_eagle_config(
            bundle.eagle_root / "config.json", family_image_size=config.image_size
        )
        Gr00tN1d6ModelFactory._require_dependencies()
        modeling = importlib.import_module(
            "autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling"
        )
        backbone_module = importlib.import_module("autovla.models.families.gr00t_n1d6.backbone")
        eagle_constructor = cast(_ObjectConstructor, _required_type(modeling, "LocalEagleModel"))
        constructor = cast(
            _ObjectConstructor,
            _required_type(backbone_module, "EagleVisionLanguageBackbone"),
        )
        with request.initialization_context_factory():
            eagle_model = eagle_constructor(
                eagle_config, retained_language_layers=config.retained_language_layers
            )
            return constructor(config, eagle_model)


class _Gr00tN1d6ActionHeadFactory:
    """从同一共享请求构造 flow-matching 动作头。"""

    def __call__(self, request: ModelAssemblyRequest) -> object:
        """在显式初始化上下文内构造动作头。"""

        config, _ = _family_request(request)
        Gr00tN1d6ModelFactory._require_dependencies()
        module = importlib.import_module("autovla.models.families.gr00t_n1d6.action_head")
        constructor = cast(_ObjectConstructor, _required_type(module, "Gr00tN1d6ActionHead"))
        with request.initialization_context_factory():
            return constructor(config)


class _Gr00tN1d6CheckpointAdapterFactory:
    """从同一共享请求构造 safetensors checkpoint 适配器。"""

    def __call__(self, request: ModelAssemblyRequest) -> object:
        """先校验家族请求再延迟导入适配器。"""

        _family_request(request)
        Gr00tN1d6ModelFactory._require_dependencies()
        module = importlib.import_module("autovla.models.families.gr00t_n1d6.checkpoint")
        constructor = cast(_ObjectConstructor, _required_type(module, "Gr00tN1d6CheckpointAdapter"))
        return constructor()


class Gr00tN1d6ModelFactory:
    """从共享装配请求构造并返回身份闭合的 N1.6.1 结果。"""

    def __call__(
        self,
        request: ModelAssemblyRequest,
    ) -> ModelAssemblyResult[object, object, object, object, object, object]:
        """先解析计划和静态资产布局,再在策略上下文内分配模型。"""

        if not isinstance(request, ModelAssemblyRequest):
            if getattr(request, "asset_bundle", None) is None:
                raise ValueError(
                    "official GR00T construction requires a complete verified "
                    "Gr00tModelAssetBundle before heavy side effects; "
                    "use Gr00tN1d6AssetBundle"
                )
            raise TypeError("GR00T N1.6 model factory requires ModelAssemblyRequest")
        plan = resolve_model_assembly(request)
        raw_config = request.config
        bundle = request.asset_bundle
        if (
            type(raw_config).__module__ != "autovla.models.families.gr00t_n1d6.config"
            or type(raw_config).__qualname__ != "Gr00tN1d6Config"
        ):
            raise TypeError("GR00T N1.6 assembly requires Gr00tN1d6Config")
        config = cast("Gr00tN1d6Config", raw_config)
        if config.architecture_variant != "official_n1d6":
            raise ValueError("production factory supports only official_n1d6")
        if not isinstance(bundle, Gr00tN1d6AssetBundle):
            raise ValueError(
                "official GR00T construction requires a complete verified "
                "Gr00tModelAssetBundle before heavy side effects; "
                "use Gr00tN1d6AssetBundle"
            )
        eagle_config = _load_eagle_config(
            bundle.eagle_root / "config.json",
            family_image_size=config.image_size,
        )
        visual_tokens_per_image = eagle_config.visual_tokens_per_image
        self._require_dependencies()
        checkpoint_module = importlib.import_module("autovla.models.families.gr00t_n1d6.checkpoint")
        checkpoint_constructor = cast(
            _ObjectConstructor,
            _required_type(checkpoint_module, "Gr00tN1d6CheckpointAdapter"),
        )
        checkpoint_adapter = cast(_CheckpointAdapterLike, checkpoint_constructor())
        upstream_layout = cast(
            "UpstreamCheckpointLayout",
            checkpoint_adapter.inspect_upstream_layout(bundle.base_checkpoint),
        )
        if (
            upstream_layout.key_count,
            upstream_layout.backbone_key_count,
            upstream_layout.action_head_key_count,
        ) != (1106, 633, 473):
            raise ValueError(
                "official checkpoint index must contain 1106 keys split as "
                "backbone=633/action_head=473"
            )
        processing = importlib.import_module(
            "autovla.models.families.gr00t_n1d6._nvidia.eagle.processing"
        )
        modeling = importlib.import_module(
            "autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling"
        )
        backbone_module = importlib.import_module("autovla.models.families.gr00t_n1d6.backbone")
        action_head_module = importlib.import_module(
            "autovla.models.families.gr00t_n1d6.action_head"
        )
        model_module = importlib.import_module("autovla.models.families.gr00t_n1d6.model")
        processor_module = importlib.import_module("autovla.models.families.gr00t_n1d6.processor")
        local_eagle_processor = cast(
            _LocalEagleProcessorType,
            _required_type(processing, "LocalEagleProcessor"),
        )
        local_eagle_model = cast(
            _ObjectConstructor,
            _required_type(modeling, "LocalEagleModel"),
        )
        backbone_constructor = cast(
            _ObjectConstructor,
            _required_type(backbone_module, "EagleVisionLanguageBackbone"),
        )
        action_head_constructor = cast(
            _ObjectConstructor,
            _required_type(action_head_module, "Gr00tN1d6ActionHead"),
        )
        model_constructor = cast(
            _ObjectConstructor,
            _required_type(model_module, "Gr00tN1d6Model"),
        )
        processor_constructor = cast(
            _ObjectConstructor,
            _required_type(processor_module, "Gr00tN1d6Processor"),
        )
        eagle_processor = local_eagle_processor.from_local_assets(
            bundle.eagle_support,
            eagle_config,
            asset_subdirectory=EAGLE_SUPPORT_SUBDIRECTORY,
        )
        with request.initialization_context_factory():
            eagle_model = local_eagle_model(
                eagle_config,
                retained_language_layers=config.retained_language_layers,
            )
            backbone = backbone_constructor(config, eagle_model)
            action_head = action_head_constructor(config)
            model = cast(
                "Gr00tN1d6Model",
                model_constructor(backbone, action_head),
            )
            processor = cast(
                "Gr00tN1d6Processor",
                processor_constructor(
                    config,
                    eagle_processor,
                    visual_tokens_per_image=visual_tokens_per_image,
                ),
            )
        report = cast(
            "CheckpointLoadReport",
            checkpoint_adapter.load_local(
                model,
                bundle.base_checkpoint,
                strictness="allow_known_optional",
            ),
        )
        loaded_parameter_count = _loaded_tensor_element_count(model, report)
        identity = AssemblyEvidenceIdentity.from_plan(plan)
        trainable_parameter_count = sum(
            parameter.numel() for parameter in model.parameters() if parameter.requires_grad
        )
        frozen_parameter_count = sum(
            parameter.numel() for parameter in model.parameters() if not parameter.requires_grad
        )
        return ModelAssemblyResult(
            plan=plan,
            processor=processor,
            backbone=backbone,
            action_head=action_head,
            model=model,
            checkpoint_adapter=checkpoint_adapter,
            policy_bundle=None,
            checkpoint_load=CheckpointLoadEvidence(
                identity=identity,
                adapter_identity=(
                    "autovla.models.families.gr00t_n1d6.checkpoint:" "Gr00tN1d6CheckpointAdapter"
                ),
                checkpoint_fingerprint=bundle.base_checkpoint.identity,
                strictness=report.strictness,
                loaded_parameter_count=loaded_parameter_count,
                missing_keys=report.missing_keys,
                unexpected_keys=report.unexpected_keys,
                known_optional_missing_keys=tuple(
                    key for key in report.missing_keys if key == "action_head.mask_token"
                ),
            ),
            tuning_freeze=TuningFreezeEvidence(
                identity=identity,
                strategy="official_top4_llm_and_action_head",
                trainable_components=("backbone.top_llm_layers", "action_head"),
                frozen_components=("backbone.visual", "backbone.lower_llm_layers"),
                trainable_parameter_count=trainable_parameter_count,
                frozen_parameter_count=frozen_parameter_count,
            ),
        )

    @staticmethod
    def _require_dependencies() -> None:
        """在构造前给出单一 optional-extra 错误。"""

        missing = tuple(
            name
            for name in ("PIL", "safetensors", "torch", "torchvision", "transformers")
            if importlib.util.find_spec(name) is None
        )
        if missing:
            raise OptionalDependencyError(
                "GR00T N1.6.1 construction requires missing modules "
                f"{', '.join(missing)}; install the 'model-gr00t-n1d6' extra"
            )


__all__ = ["Gr00tN1d6ModelFactory"]
