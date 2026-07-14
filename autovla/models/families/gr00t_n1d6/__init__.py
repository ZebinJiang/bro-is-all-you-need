"""GR00T N1.6.1 延迟导出;包导入不会加载 torch 或 Transformers。"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

_EXPORTS = {
    "EagleVisionLanguageBackbone": ".backbone",
    "EmbodimentConditioner": ".embodiment",
    "Gr00tN1d6ActionHead": ".action_head",
    "Gr00tN1d6CheckpointAdapter": ".checkpoint",
    "CheckpointKeyRule": ".checkpoint",
    "CheckpointLoadPolicy": ".checkpoint",
    "AutoVLAParameterLayout": ".checkpoint",
    "UpstreamCheckpointLayout": ".checkpoint",
    "Gr00tN1d6Components": ".factory",
    "Gr00tN1d6Config": ".config",
    "PerHorizonFeatureStatistics": ".config",
    "Gr00tN1d6Model": ".model",
    "Gr00tN1d6ModelFactory": ".factory",
    "Gr00tN1d6ModelSpec": ".specification",
    "Gr00tN1d6Processor": ".processor",
}

__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend(sorted(_EXPORTS))


def __getattr__(name: str) -> object:
    """仅在访问具体运行时符号时导入其模块。"""
    try:
        module_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定的延迟导出目录。"""
    return sorted(set(globals()) | set(__all__))
