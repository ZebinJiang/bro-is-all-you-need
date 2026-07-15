"""GR00T N1.7 延迟公共接口。包导入不加载 Torch/Transformers。"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

_EXPORTS = {
    "CosmosReason2VisionLanguageBackbone": ".backbone",
    "Gr00tN1d7ActionHead": ".action_head",
    "Gr00tN1d7AssetBundle": ".assets",
    "Gr00tN1d7CheckpointAdapter": ".checkpoint",
    "Gr00tN1d7Config": ".config",
    "Gr00tN1d7FamilyDefinition": ".family",
    "Gr00tN1d7Model": ".model",
    "Gr00tN1d7ModelFactory": ".factory",
    "Gr00tN1d7Processor": ".processor",
}

__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend(sorted(_EXPORTS))


def __getattr__(name: str) -> object:
    """仅在访问具体符号时导入对应轻量模块。"""

    try:
        module_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    module = importlib.import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定的九类公共目录。"""

    return sorted(set(globals()) | set(__all__))
