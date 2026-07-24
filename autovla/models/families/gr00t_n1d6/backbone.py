"""AutoVLA 本地 Eagle 视觉语言骨干。"""

from __future__ import annotations

import torch

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.families.gr00t_n1d6._nvidia.eagle.modeling import LocalEagleModel
from autovla.models.families.gr00t_n1d6.config import Gr00tN1d6Config
from autovla.models.interfaces.backbone import VisionLanguageBackbone
from autovla.models.outputs import BackboneOutput, ModelInputBatch


class EagleVisionLanguageBackbone(VisionLanguageBackbone):
    """使用 owned Eagle/Qwen3/SigLIP2 类提取 ``[B,S,2048]`` 特征。"""

    def __init__(self, config: Gr00tN1d6Config, model: LocalEagleModel) -> None:
        """保存本地 Eagle 实例并应用最终 tune/freeze 策略。"""
        initialize_torch_module(super())
        self.config = config
        self.model = model
        self._apply_tune_policy()

    def _apply_tune_policy(self) -> None:
        """先冻结全部,再按显式 granular 策略选择性解冻。"""
        self.requires_grad_(False)
        if self.config.tune_backbone:
            if self.config.tune_llm:
                self.model.language_model.requires_grad_(True)
            if self.config.tune_visual:
                self.model.vision_model.requires_grad_(True)
                self.model.mlp1.requires_grad_(True)
        if self.config.tune_top_llm_layers:
            layers = self.model.language_layers()
            if self.config.tune_top_llm_layers > len(layers):
                raise ValueError("tune_top_llm_layers exceeds retained Qwen3 layers")
            for layer in layers[-self.config.tune_top_llm_layers :]:
                layer.requires_grad_(True)
        if self.config.trainable_parameters_fp32:
            for parameter in self.parameters():
                if parameter.requires_grad:
                    parameter.data = parameter.data.float()

    def train(self, mode: bool = True) -> "EagleVisionLanguageBackbone":
        """切换模式并强制冻结子模块保持 eval。"""
        super().train(mode)
        if mode:
            if not self.config.tune_llm:
                self.model.language_model.eval()
                if self.config.tune_top_llm_layers:
                    for layer in self.model.language_layers()[-self.config.tune_top_llm_layers :]:
                        layer.train(True)
            if not self.config.tune_visual:
                self.model.vision_model.eval()
                self.model.mlp1.eval()
        return self

    def forward(self, batch: ModelInputBatch) -> BackboneOutput:
        """连接有序相机并返回类型化 Eagle 特征和 token 掩码。"""
        pixel_values = torch.cat(tuple(batch.images[name] for name in batch.camera_order), dim=1)
        features = self.model(
            input_ids=batch.input_ids,
            attention_mask=batch.attention_mask,
            pixel_values=pixel_values,
        )
        image_mask = batch.input_ids == self.model.config.image_token_id
        return BackboneOutput(
            features=features,
            attention_mask=batch.attention_mask.bool(),
            image_mask=image_mask,
        )


__all__ = ["EagleVisionLanguageBackbone"]
