# --------------------------------------------------------
# NVIDIA
# Copyright (c) 2025 NVIDIA
# Licensed under The MIT License [see LICENSE for details]
# --------------------------------------------------------
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a:
# gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/modeling_eagle3_vl.py.
"""直接拥有 Qwen3/SigLIP2 实例的本地 Eagle 模型。"""

from __future__ import annotations

import math

import torch
from torch import nn
from transformers import Qwen3Config, Qwen3ForCausalLM, Siglip2VisionConfig, Siglip2VisionModel

from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig


class LocalQwen3LanguageModel(Qwen3ForCausalLM):
    """显式 Qwen3 类,禁止 AutoModel/auto_map 动态分派。"""


class LocalSiglip2VisionModel(Siglip2VisionModel):
    """显式 SigLIP2 类,禁止 checkpoint 提供 Python 实现。"""


class LocalEagleModel(nn.Module):
    """组合本地配置构造的 SigLIP2、投影器和 Qwen3。

    输入图像形状为 ``[B,V,C,H,W]``。视觉 token 经 pixel-shuffle 下采样和
    MLP 投影后替换语言序列中的显式 image-token 位置。
    """

    def __init__(self, config: LocalEagleConfig, *, retained_language_layers: int) -> None:
        """直接构造受控类并截断未使用的语言层。"""
        super().__init__()
        if retained_language_layers <= 0:
            raise ValueError("retained_language_layers must be positive")
        self.config = config
        text_payload = _clean_transformers_config(config.text_config)
        vision_payload = _clean_transformers_config(config.vision_config)
        self.language_model = LocalQwen3LanguageModel(Qwen3Config(**text_payload))
        self.vision_model = LocalSiglip2VisionModel(Siglip2VisionConfig(**vision_payload))
        layers = self.language_model.model.layers
        if retained_language_layers > len(layers):
            raise ValueError("retained language layer count exceeds Qwen3 config")
        del layers[retained_language_layers:]
        hidden_size: object = vision_payload.get("hidden_size", 1152)
        if type(hidden_size) is not int or hidden_size <= 0:
            raise ValueError("vision hidden_size must be a positive integer")
        vision_width = hidden_size
        shuffle_factor = _shuffle_factor(config.downsample_ratio)
        connector_input = vision_width * shuffle_factor * shuffle_factor
        self.mlp1 = nn.Sequential(
            nn.LayerNorm(connector_input),
            nn.Linear(connector_input, config.projector_hidden_size),
            nn.GELU(),
            nn.Linear(config.projector_hidden_size, config.output_size),
        )

    def _pixel_shuffle(self, features: torch.Tensor) -> torch.Tensor:
        """按空间邻域拼接通道,保持 upstream downsample 语义。"""
        batch, tokens, channels = features.shape
        side = math.isqrt(tokens)
        if side * side != tokens:
            raise ValueError("SigLIP2 token count must form a square grid")
        factor = _shuffle_factor(self.config.downsample_ratio)
        if side % factor:
            raise ValueError("vision token grid is incompatible with downsample_ratio")
        values = features.reshape(batch, side // factor, factor, side // factor, factor, channels)
        values = values.permute(0, 1, 3, 2, 4, 5).contiguous()
        return values.reshape(batch, (side // factor) ** 2, channels * factor * factor)

    def extract_visual_features(self, pixel_values: torch.Tensor) -> torch.Tensor:
        """把 ``[B,V,C,H,W]`` 转换为 ``[B,V*N,C_text]``。"""
        if pixel_values.ndim != 5:
            raise ValueError("pixel_values must have shape [B,V,C,H,W]")
        batch_size, views = pixel_values.shape[:2]
        flat = pixel_values.flatten(0, 1)
        outputs = self.vision_model(
            pixel_values=flat,
            output_hidden_states=self.config.select_layer != -1,
            return_dict=True,
        )
        if self.config.select_layer == -1:
            features = outputs.last_hidden_state
        else:
            if outputs.hidden_states is None:
                raise RuntimeError("SigLIP2 did not return requested hidden states")
            features = outputs.hidden_states[self.config.select_layer]
        projected = self.mlp1(self._pixel_shuffle(features))
        return projected.reshape(batch_size, views * projected.shape[1], projected.shape[2])

    def forward(
        self,
        *,
        input_ids: torch.Tensor,
        attention_mask: torch.Tensor,
        pixel_values: torch.Tensor,
    ) -> torch.Tensor:
        """返回最后保留语言层的多模态特征 ``[B,S,2048]``。"""
        if input_ids.ndim != 2 or attention_mask.shape != input_ids.shape:
            raise ValueError("input_ids and attention_mask must share [B,S] shape")
        visual_features = self.extract_visual_features(pixel_values)
        token_embeddings = self.language_model.get_input_embeddings()(input_ids)
        image_mask = input_ids == self.config.image_token_id
        for index in range(input_ids.shape[0]):
            positions = image_mask[index].nonzero(as_tuple=False).flatten()
            if positions.numel() != visual_features.shape[1]:
                raise ValueError(
                    "language image-token count must exactly match projected visual tokens"
                )
            token_embeddings[index, positions] = visual_features[index].to(token_embeddings.dtype)
        outputs = self.language_model.model(
            inputs_embeds=token_embeddings,
            attention_mask=attention_mask,
            use_cache=False,
            output_hidden_states=True,
            return_dict=True,
        )
        return outputs.last_hidden_state


def _shuffle_factor(ratio: float) -> int:
    """把倒数为整数的下采样比例转换为 pixel-shuffle 因子。"""
    factor = round(1.0 / ratio)
    if factor <= 0 or not math.isclose(ratio * factor, 1.0):
        raise ValueError("downsample_ratio reciprocal must be an integer")
    return factor


def _clean_transformers_config(payload: object) -> dict[str, object]:
    """移除来源/自动分派元数据,仅保留静态模型参数。"""
    if not isinstance(payload, dict) and not hasattr(payload, "items"):
        raise TypeError("transformers sub-config must be a mapping")
    ignored = {
        "_attn_implementation_autoset",
        "_name_or_path",
        "architectures",
        "auto_map",
        "torch_dtype",
        "transformers_version",
    }
    return {str(key): value for key, value in payload.items() if str(key) not in ignored}


__all__ = ["LocalEagleModel", "LocalQwen3LanguageModel", "LocalSiglip2VisionModel"]
