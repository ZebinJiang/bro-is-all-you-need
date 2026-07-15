"""GR00T N1.7 组合模型的无执行结构。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
from autovla.models.families.gr00t_n1d7.backbone import (
    CosmosReason2VisionLanguageBackbone,
)
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config


@dataclass(frozen=True, slots=True)
class Gr00tN1d7Model:
    """组合同一 artifact 配置的骨干和动作头。不执行 forward。"""

    config: Gr00tN1d7Config
    backbone: CosmosReason2VisionLanguageBackbone
    action_head: Gr00tN1d7ActionHead

    def __post_init__(self) -> None:
        """拒绝组件配置身份漂移。"""

        if self.backbone.config != self.config or self.action_head.config != self.config:
            raise ValueError("model components must share one immutable N1.7 config")

    @property
    def tensor_contract(self) -> dict[str, object]:
        """返回后续 CUDA 实现必须满足的张量边界。"""

        return {
            "state": "[B,132]",
            "actions": "[B,40,132]",
            "action_mask": "bool[B,40,132]",
            "image_grid_thw": "int[N,3]",
            "vl_hidden_width": 2048,
            "output": "[B,40,132]",
        }


__all__ = ["Gr00tN1d7Model"]
