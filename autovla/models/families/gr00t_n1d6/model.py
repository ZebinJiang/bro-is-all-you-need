"""GR00T N1.6.1 组合模型。"""

from __future__ import annotations

import torch

from autovla.models.families.gr00t_n1d6.action_head import Gr00tN1d6ActionHead
from autovla.models.families.gr00t_n1d6.backbone import EagleVisionLanguageBackbone
from autovla.models.interfaces.model import VisionLanguageActionModel
from autovla.models.outputs import ActionPrediction, ModelInputBatch, ModelOutput


class Gr00tN1d6Model(VisionLanguageActionModel):
    """仅组合 Eagle 骨干与 N1.6.1 动作头。"""

    def __init__(
        self,
        backbone: EagleVisionLanguageBackbone,
        action_head: Gr00tN1d6ActionHead,
    ) -> None:
        """保存两个独立参数组件。"""
        super().__init__()
        self.backbone = backbone
        self.action_head = action_head

    def forward(self, batch: ModelInputBatch) -> ModelOutput:
        """执行骨干和 masked flow-matching 训练路径。"""
        backbone_output = self.backbone(batch)
        action_output = self.action_head.compute_loss(backbone_output, batch)
        return ModelOutput(
            loss=action_output.loss,
            backbone=backbone_output,
            action_head=action_output,
        )

    @torch.no_grad()
    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """返回归一化动作;物理单位恢复由 processor 完成。"""
        backbone_output = self.backbone(batch)
        return self.action_head.predict_actions(
            backbone_output,
            batch,
            generator=generator,
        )


__all__ = ["Gr00tN1d6Model"]
