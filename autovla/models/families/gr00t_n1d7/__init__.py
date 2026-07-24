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

if TYPE_CHECKING:
    from .action_head import Gr00tN1d7ActionHead as Gr00tN1d7ActionHead
    from .assets import Gr00tN1d7AssetBundle as Gr00tN1d7AssetBundle
    from .backbone import (
        CosmosReason2VisionLanguageBackbone as CosmosReason2VisionLanguageBackbone,
    )
    from .checkpoint import Gr00tN1d7CheckpointAdapter as Gr00tN1d7CheckpointAdapter
    from .config import Gr00tN1d7Config as Gr00tN1d7Config
    from .factory import Gr00tN1d7ModelFactory as Gr00tN1d7ModelFactory
    from .family import Gr00tN1d7FamilyDefinition as Gr00tN1d7FamilyDefinition
    from .model import Gr00tN1d7Model as Gr00tN1d7Model
    from .processor import Gr00tN1d7Processor as Gr00tN1d7Processor

__all__ = [
    "CosmosReason2VisionLanguageBackbone",
    "Gr00tN1d7ActionHead",
    "Gr00tN1d7AssetBundle",
    "Gr00tN1d7CheckpointAdapter",
    "Gr00tN1d7Config",
    "Gr00tN1d7FamilyDefinition",
    "Gr00tN1d7Model",
    "Gr00tN1d7ModelFactory",
    "Gr00tN1d7Processor",
]


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
