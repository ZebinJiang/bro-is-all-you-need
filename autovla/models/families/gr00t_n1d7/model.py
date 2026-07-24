"""GR00T N1.7 组合 PyTorch 模型。"""

from __future__ import annotations

import torch

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.families.gr00t_n1d7.action_head import Gr00tN1d7ActionHead
from autovla.models.families.gr00t_n1d7.backbone import (
    CosmosReason2VisionLanguageBackbone,
)
from autovla.models.families.gr00t_n1d7.config import Gr00tN1d7Config
from autovla.models.interfaces.model import VisionLanguageActionModel
from autovla.models.outputs import ActionPrediction, ModelInputBatch, ModelOutput


class Gr00tN1d7Model(VisionLanguageActionModel):
    """在唯一前向路径中组合 Qwen3-VL 与 flow-matching 动作头。"""

    def __init__(
        self,
        config: Gr00tN1d7Config,
        backbone: CosmosReason2VisionLanguageBackbone,
        action_head: Gr00tN1d7ActionHead,
    ) -> None:
        """保存共享同一不可变配置的参数组件。"""

        initialize_torch_module(super())
        if backbone.config != config or action_head.config != config:
            raise ValueError("model components must share one immutable N1.7 config")
        self.config = config
        self.backbone = backbone
        self.action_head = action_head

    @property
    def tensor_contract(self) -> dict[str, object]:
        """返回训练和预测共享的张量边界。"""

        return {
            "state": "[B,T,132]",
            "actions": "[B,40,132]",
            "action_mask": "bool[B,40,132]",
            "image_grid_thw": "int[N,3]",
            "vl_hidden_width": 2048,
            "output": "[B,40,132]",
        }

    def forward(self, batch: ModelInputBatch) -> ModelOutput:
        """执行骨干和逐元素归一化 flow-matching 损失。"""

        backbone = self.backbone(batch)
        action_head = self.action_head.compute_loss(backbone, batch)
        return ModelOutput(action_head.loss, backbone, action_head)

    def predict_actions(
        self,
        batch: ModelInputBatch,
        *,
        generator: torch.Generator | None = None,
    ) -> ActionPrediction:
        """执行骨干与恰好四步 Euler 动作生成。"""

        with torch.no_grad():
            return self.action_head.predict_actions(
                self.backbone(batch), batch, generator=generator
            )


__all__ = ["Gr00tN1d7Model"]
