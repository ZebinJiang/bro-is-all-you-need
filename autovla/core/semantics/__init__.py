"""AutoVLA 张量语义公共接口, 不导入 NumPy 或 Torch。"""

from autovla.core.semantics.alignment import (
    AlignmentMode,
    AlignmentPlan,
    AlignmentPolicy,
    resolve_alignment,
)
from autovla.core.semantics.axes import AxisName, TensorLayout
from autovla.core.semantics.masks import MaskKind, MaskSemantics, MaskTruth

__all__ = [
    "AlignmentMode",
    "AlignmentPlan",
    "AlignmentPolicy",
    "AxisName",
    "MaskKind",
    "MaskSemantics",
    "MaskTruth",
    "TensorLayout",
    "resolve_alignment",
]
