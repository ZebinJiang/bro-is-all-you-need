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
from collections.abc import Mapping
from typing import Protocol, TypeGuard, runtime_checkable

import torch
from torch import nn
from transformers.models.qwen3 import Qwen3Config, Qwen3ForCausalLM
from transformers.models.siglip2 import Siglip2VisionConfig, Siglip2VisionModel

from autovla.models._torch_typing import initialize_torch_module
from autovla.models.families.gr00t_n1d6._nvidia.eagle.configuration import LocalEagleConfig


@runtime_checkable
class _ConfigFactory(Protocol):
    """描述 Transformers 配置的静态 ``from_dict`` 入口。"""

    def __call__(self, config_dict: Mapping[str, object]) -> object:
        """从静态键值构造配置。"""
        ...


@runtime_checkable
class _TensorModule(Protocol):
    """描述接收 token ID 并返回 tensor 的模块。"""

    def __call__(self, values: torch.Tensor) -> torch.Tensor:
        """执行 tensor 前向。"""
        ...


@runtime_checkable
class _EmbeddingResolver(Protocol):
    """描述 Qwen3 输入 embedding 的获取入口。"""

    def __call__(self) -> object:
        """返回动态 embedding 模块。"""
        ...


@runtime_checkable
class _LanguageBackbone(Protocol):
    """描述 Qwen3 主干在多模态嵌入路径上的调用。"""

    def __call__(
        self,
        *,
        inputs_embeds: torch.Tensor,
        attention_mask: torch.Tensor,
        use_cache: bool,
        output_hidden_states: bool,
        return_dict: bool,
    ) -> object:
        """返回包含最后隐藏状态的动态输出。"""
        ...


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
        initialize_torch_module(super())
        if retained_language_layers <= 0:
            raise ValueError("retained_language_layers must be positive")
        self.config = config
        text_payload = _clean_transformers_config(config.text_config)
        vision_payload = _clean_transformers_config(config.vision_config)
        self.language_model = LocalQwen3LanguageModel(_qwen3_config(text_payload))
        self.vision_model = LocalSiglip2VisionModel(_siglip2_config(vision_payload))
        layers = self.language_layers()
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

    def language_layers(self) -> nn.ModuleList:
        """返回经过运行时校验的 Qwen3 层容器。"""
        backbone: object = getattr(self.language_model, "model", None)
        layers: object = getattr(backbone, "layers", None)
        if not isinstance(layers, nn.ModuleList):
            raise TypeError("Qwen3 model.layers must be a ModuleList")
        return layers

    def _pixel_shuffle(
        self,
        features: torch.Tensor,
        grid_h: int,
        grid_w: int,
    ) -> torch.Tensor:
        """按给定矩形网格拼接空间邻域通道,保持 upstream 下采样语义。"""
        if features.ndim != 3:
            raise ValueError("SigLIP2 features must have shape [B,N,D]")
        batch, tokens, channels = features.shape
        if grid_h <= 0 or grid_w <= 0 or tokens != grid_h * grid_w:
            raise ValueError("SigLIP2 token count must match the supplied vision grid")
        factor = _shuffle_factor(self.config.downsample_ratio)
        if grid_h % factor or grid_w % factor:
            raise ValueError("vision token grid is incompatible with downsample_ratio")
        values = features.reshape(
            batch,
            grid_h // factor,
            factor,
            grid_w // factor,
            factor,
            channels,
        )
        values = values.permute(0, 1, 3, 2, 4, 5).contiguous()
        return values.reshape(
            batch,
            (grid_h // factor) * (grid_w // factor),
            channels * factor * factor,
        )

    def extract_visual_features(self, pixel_values: torch.Tensor) -> torch.Tensor:
        """把 ``[B,V,C,H,W]`` 转换为 ``[B,V*N,C_text]``。"""
        if pixel_values.ndim != 5:
            raise ValueError("pixel_values must have shape [B,V,C,H,W]")
        batch_size, views, channels, height, width = pixel_values.shape
        vision_config: object = getattr(self.vision_model, "config", None)
        patch_size: object = getattr(vision_config, "patch_size", None)
        num_channels: object = getattr(vision_config, "num_channels", None)
        if type(patch_size) is not int or patch_size <= 0:
            raise ValueError("SigLIP2 patch_size must be a positive integer")
        if type(num_channels) is not int or num_channels <= 0:
            raise ValueError("SigLIP2 num_channels must be a positive integer")
        if channels != num_channels:
            raise ValueError("pixel_values channels must match SigLIP2 num_channels")
        if height % patch_size or width % patch_size:
            raise ValueError(
                "pixel_values height and width must be divisible by SigLIP2 patch_size"
            )

        grid_h = height // patch_size
        grid_w = width // patch_size
        token_count = grid_h * grid_w
        flat = pixel_values.flatten(0, 1)
        # 与 Siglip2ImageProcessor 保持相同的逐 patch 元素顺序。
        patches = flat.permute(0, 2, 3, 1).reshape(
            batch_size * views,
            grid_h,
            patch_size,
            grid_w,
            patch_size,
            channels,
        )
        patches = patches.permute(0, 1, 3, 2, 4, 5).reshape(
            batch_size * views,
            token_count,
            channels * patch_size * patch_size,
        )
        pixel_attention_mask = torch.ones(
            (batch_size * views, token_count),
            dtype=torch.bool,
            device=pixel_values.device,
        )
        spatial_shapes = torch.tensor(
            (grid_h, grid_w),
            dtype=torch.long,
            device=pixel_values.device,
        ).expand(batch_size * views, 2)
        expected_patch_shape = (
            batch_size * views,
            token_count,
            channels * patch_size * patch_size,
        )
        if patches.shape != expected_patch_shape or patches.dtype != pixel_values.dtype:
            raise RuntimeError("SigLIP2 patch tensor violates the owned input contract")
        if pixel_attention_mask.shape != expected_patch_shape[:2] or (
            pixel_attention_mask.dtype != torch.bool
        ):
            raise RuntimeError("SigLIP2 pixel attention mask violates the owned input contract")
        if spatial_shapes.shape != (batch_size * views, 2) or spatial_shapes.dtype != torch.long:
            raise RuntimeError("SigLIP2 spatial shapes violate the owned input contract")
        if not bool((spatial_shapes[:, 0] * spatial_shapes[:, 1] == token_count).all()):
            raise RuntimeError("SigLIP2 spatial shapes disagree with the patch token count")
        outputs = self.vision_model(
            pixel_values=patches,
            pixel_attention_mask=pixel_attention_mask,
            spatial_shapes=spatial_shapes,
            output_hidden_states=self.config.select_layer != -1,
            return_dict=True,
        )
        if self.config.select_layer == -1:
            features = outputs.last_hidden_state
        else:
            if outputs.hidden_states is None:
                raise RuntimeError("SigLIP2 did not return requested hidden states")
            features = outputs.hidden_states[self.config.select_layer]
        projected = self.mlp1(self._pixel_shuffle(features, grid_h, grid_w))
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
        embedding_resolver: object = getattr(self.language_model, "get_input_embeddings", None)
        if not isinstance(embedding_resolver, _EmbeddingResolver):
            raise TypeError("Qwen3 input embedding resolver must be callable")
        raw_embedding = embedding_resolver()
        if not isinstance(raw_embedding, _TensorModule):
            raise TypeError("Qwen3 input embedding must accept a tensor")
        token_embeddings = raw_embedding(input_ids)
        image_mask = input_ids == self.config.image_token_id
        for index in range(input_ids.shape[0]):
            positions = image_mask[index].nonzero(as_tuple=False).flatten()
            if positions.numel() != visual_features.shape[1]:
                raise ValueError(
                    "language image-token count must exactly match projected visual tokens"
                )
            token_embeddings[index, positions] = visual_features[index].to(token_embeddings.dtype)
        raw_backbone: object = getattr(self.language_model, "model", None)
        if not isinstance(raw_backbone, _LanguageBackbone):
            raise TypeError("Qwen3 language backbone must be callable")
        outputs = raw_backbone(
            inputs_embeds=token_embeddings,
            attention_mask=attention_mask,
            use_cache=False,
            output_hidden_states=True,
            return_dict=True,
        )
        hidden_state: object = getattr(outputs, "last_hidden_state", None)
        if not isinstance(hidden_state, torch.Tensor):
            raise TypeError("Qwen3 output must contain last_hidden_state tensor")
        return hidden_state


def _shuffle_factor(ratio: float) -> int:
    """把倒数为整数的下采样比例转换为 pixel-shuffle 因子。"""
    factor = round(1.0 / ratio)
    if factor <= 0 or not math.isclose(ratio * factor, 1.0):
        raise ValueError("downsample_ratio reciprocal must be an integer")
    return factor


def _clean_transformers_config(payload: object) -> dict[str, object]:
    """移除来源/自动分派元数据,仅保留静态模型参数。"""
    if not _is_object_mapping(payload):
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


def _is_object_mapping(payload: object) -> TypeGuard[Mapping[object, object]]:
    """收窄 Transformers 动态配置映射。"""
    return isinstance(payload, Mapping)


def _qwen3_config(payload: Mapping[str, object]) -> Qwen3Config:
    """通过静态配置工厂构造并校验 Qwen3 配置。"""
    factory: object = getattr(Qwen3Config, "from_dict", None)
    if not isinstance(factory, _ConfigFactory):
        raise TypeError("Qwen3Config.from_dict must be callable")
    config = factory(dict(payload))
    if not isinstance(config, Qwen3Config):
        raise TypeError("Qwen3Config.from_dict returned an invalid config")
    return config


def _siglip2_config(payload: Mapping[str, object]) -> Siglip2VisionConfig:
    """通过静态配置工厂构造并校验 SigLIP2 配置。"""
    factory: object = getattr(Siglip2VisionConfig, "from_dict", None)
    if not isinstance(factory, _ConfigFactory):
        raise TypeError("Siglip2VisionConfig.from_dict must be callable")
    config = factory(dict(payload))
    if not isinstance(config, Siglip2VisionConfig):
        raise TypeError("Siglip2VisionConfig.from_dict returned an invalid config")
    return config


__all__ = ["LocalEagleModel", "LocalQwen3LanguageModel", "LocalSiglip2VisionModel"]
