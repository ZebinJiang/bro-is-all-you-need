"""定义互不混用的掩码类别和真假语义。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from autovla.core.semantics.axes import TensorLayout


class MaskKind(str, Enum):
    """列出数据到损失路径中的独立掩码概念。"""

    TEMPORAL = "temporal"
    ACTION_DIMENSION = "action_dimension"
    STATISTICS = "statistics"
    PADDING = "padding"
    LOSS = "loss"
    CAMERA = "camera"
    FRAME = "frame"


class MaskTruth(str, Enum):
    """声明布尔真值表示有效还是 padding。"""

    TRUE_IS_VALID = "true_is_valid"
    TRUE_IS_PADDING = "true_is_padding"


@dataclass(frozen=True, slots=True)
class MaskSemantics:
    """绑定掩码类别、布局和真值解释。"""

    kind: MaskKind
    layout: TensorLayout
    truth: MaskTruth = MaskTruth.TRUE_IS_VALID

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "kind": self.kind.value,
            "layout": self.layout.to_json_dict(),
            "truth": self.truth.value,
        }


__all__ = ["MaskKind", "MaskSemantics", "MaskTruth"]
