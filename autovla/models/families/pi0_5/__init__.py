"""Pi0.5 家族的轻量公开入口,运行依赖均按需导入。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    "Pi05Config": "config",
    "Pi05Processor": "processor",
    "Pi05VisionLanguageBackbone": "backbone",
    "Pi05ActionExpert": "action_head",
    "Pi05Model": "model",
    "Pi05ModelFactory": "factory",
    "Pi05CheckpointAdapter": "checkpoint",
    "Pi05AssetBundle": "assets",
    "Pi05CheckpointConverter": "conversion",
    "Pi05FamilyDefinition": "family",
}

if TYPE_CHECKING:
    from .action_head import Pi05ActionExpert as Pi05ActionExpert
    from .assets import Pi05AssetBundle as Pi05AssetBundle
    from .backbone import Pi05VisionLanguageBackbone as Pi05VisionLanguageBackbone
    from .checkpoint import Pi05CheckpointAdapter as Pi05CheckpointAdapter
    from .config import Pi05Config as Pi05Config
    from .conversion import Pi05CheckpointConverter as Pi05CheckpointConverter
    from .factory import Pi05ModelFactory as Pi05ModelFactory
    from .family import Pi05FamilyDefinition as Pi05FamilyDefinition
    from .model import Pi05Model as Pi05Model
    from .processor import Pi05Processor as Pi05Processor

__all__ = [
    "Pi05ActionExpert",
    "Pi05AssetBundle",
    "Pi05CheckpointAdapter",
    "Pi05CheckpointConverter",
    "Pi05Config",
    "Pi05FamilyDefinition",
    "Pi05Model",
    "Pi05ModelFactory",
    "Pi05Processor",
    "Pi05VisionLanguageBackbone",
]


def __getattr__(name: str) -> object:
    """按需加载家族组件,避免元数据导入触发 Torch 或转换依赖。"""

    try:
        module_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    value = getattr(import_module(f"{__name__}.{module_name}"), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共目录,不触发任何家族运行依赖。"""

    return sorted(set(globals()) | set(__all__))
