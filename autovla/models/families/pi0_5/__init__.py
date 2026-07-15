"""Pi0.5 家族的轻量公开入口,运行依赖均按需导入。"""

from __future__ import annotations

from importlib import import_module

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

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> object:
    """按需加载家族组件,避免元数据导入触发 Torch 或转换依赖。"""

    try:
        module_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(f"{__name__}.{module_name}"), name)
