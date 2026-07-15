"""GR00T N1.6.1 本地双资产包模型工厂。"""

from __future__ import annotations

import importlib
import importlib.util
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Protocol, cast

from autovla.assets import EAGLE_SUPPORT_SUBDIRECTORY, Gr00tModelAssetBundle
from autovla.core.registry.errors import OptionalDependencyError

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


def _required_type(module: ModuleType, name: str) -> type[object]:
    """从延迟模块读取一个必需类并拒绝动态缺失。"""
    value: object = getattr(module, name, None)
    if not isinstance(value, type):
        raise TypeError(f"runtime module lacks required type {name}")
    return value


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


@dataclass(frozen=True, slots=True)
class Gr00tN1d6Components:
    """返回同一配置和资产包构造的模型、处理器及加载证据。"""

    model: Gr00tN1d6Model
    processor: Gr00tN1d6Processor
    checkpoint_report: CheckpointLoadReport
    base_asset_manifest: Mapping[str, object]
    upstream_layout: UpstreamCheckpointLayout
    asset_bundle_fingerprint: str


class Gr00tN1d6ModelFactory:
    """仅在双收据完整验证后构造本地 reviewed Eagle 和动作头。"""

    def __call__(self, config: Gr00tN1d6Config) -> Gr00tN1d6Components:
        """先验证 bundle/layout/dependency,再进行任何重型模型分配。"""

        bundle = config.asset_bundle
        if config.architecture_variant != "official_n1d6":
            raise ValueError("production factory supports only official_n1d6")
        if not isinstance(bundle, Gr00tModelAssetBundle):
            raise ValueError(
                "official GR00T construction requires a complete verified "
                "Gr00tModelAssetBundle before heavy side effects"
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
        return Gr00tN1d6Components(
            model=model,
            processor=processor,
            checkpoint_report=report,
            base_asset_manifest=bundle.base_checkpoint.manifest.to_dict(),
            upstream_layout=upstream_layout,
            asset_bundle_fingerprint=bundle.fingerprint,
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


__all__ = ["Gr00tN1d6Components", "Gr00tN1d6ModelFactory"]
