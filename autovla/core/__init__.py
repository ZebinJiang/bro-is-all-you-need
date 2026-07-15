"""AutoVLA 核心层延迟公共接口, 不包含数值后端依赖。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    name: ("autovla.core.semantics", name)
    for name in (
        "AlignmentMode",
        "AlignmentPlan",
        "AlignmentPolicy",
        "AxisName",
        "MaskKind",
        "MaskSemantics",
        "MaskTruth",
        "TensorLayout",
        "resolve_alignment",
    )
}

__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend(sorted(_EXPORTS))


def __getattr__(name: str) -> object:
    """按需解析核心语义对象并保留实现对象身份。"""
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute = target
    value = getattr(import_module(module_name), attribute)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共名称集合。"""
    return sorted(set(globals()) | set(__all__))
