# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# Licensed under the NVIDIA License; see licenses/NVIDIA-ISAAC-GROOT-N1D6.txt.
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a: gr00t/model/modules/dit.py.
"""N1.6.1 交替视觉语言扩散 Transformer。"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from autovla.models._torch_typing import initialize_torch_module


class TimestepEncoder(nn.Module):
    """把离散扩散时间编码到 DiT 内部宽度。"""

    def __init__(self, embedding_dim: int, frequency_dim: int = 256) -> None:
        """构造固定频率投影和两层时间 MLP。"""
        initialize_torch_module(super())
        if embedding_dim <= 0 or frequency_dim < 4 or frequency_dim % 2:
            raise ValueError(
                "time embedding dimensions must be positive and frequency_dim even >= 4"
            )
        self.frequency_dim = frequency_dim
        self.linear1 = nn.Linear(frequency_dim, embedding_dim)
        self.linear2 = nn.Linear(embedding_dim, embedding_dim)

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        """返回 ``[B,C]`` 时间条件。"""
        if timesteps.ndim != 1:
            raise ValueError("timesteps must have shape [B]")
        half = self.frequency_dim // 2
        exponent = (
            -math.log(10000.0)
            * torch.arange(
                half,
                dtype=torch.float32,
                device=timesteps.device,
            )
            / (half - 1)
        )
        arguments = timesteps.float().unsqueeze(1) * exponent.exp().unsqueeze(0)
        encoded = torch.cat((arguments.cos(), arguments.sin()), dim=1)
        encoded = encoded.to(dtype=self.linear1.weight.dtype)
        return self.linear2(F.silu(self.linear1(encoded)))


class AdaptiveLayerNorm(nn.Module):
    """使用时间条件缩放和平移序列特征。"""

    def __init__(self, width: int, epsilon: float = 1e-5) -> None:
        """构造无仿射归一化和条件投影。"""
        initialize_torch_module(super())
        self.norm = nn.LayerNorm(width, eps=epsilon, elementwise_affine=False)
        self.linear = nn.Linear(width, 2 * width)

    def forward(self, values: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        """应用时间条件归一化。"""
        scale, shift = self.linear(F.silu(condition)).chunk(2, dim=-1)
        return self.norm(values) * (1.0 + scale.unsqueeze(1)) + shift.unsqueeze(1)


class GeluFeedForward(nn.Module):
    """复现官方 diffusers ``gelu-approximate`` 前馈层。"""

    def __init__(self, width: int, dropout: float) -> None:
        """构造四倍中间宽度和官方双 dropout 顺序。"""
        initialize_torch_module(super())
        inner = 4 * width
        self.proj_in = nn.Linear(width, inner)
        self.dropout = nn.Dropout(dropout)
        self.proj_out = nn.Linear(inner, width)
        self.final_dropout = nn.Dropout(dropout)

    def forward(self, values: torch.Tensor) -> torch.Tensor:
        """依次执行近似 GELU、中间 dropout、输出投影和最终 dropout。"""
        hidden_states = F.gelu(self.proj_in(values), approximate="tanh")
        hidden_states = self.dropout(hidden_states)
        return self.final_dropout(self.proj_out(hidden_states))


class TransformerBlock(nn.Module):
    """支持自注意力或视觉语言交叉注意力的 AdaLN block。"""

    def __init__(
        self,
        width: int,
        num_heads: int,
        *,
        cross_attention_dim: int,
        dropout: float,
        cross_attention: bool,
    ) -> None:
        """按 block 类型构造注意力参数。"""
        initialize_torch_module(super())
        self.cross_attention = cross_attention
        self.norm1 = AdaptiveLayerNorm(width)
        self.attn1 = nn.MultiheadAttention(
            width,
            num_heads,
            dropout=dropout,
            batch_first=True,
            kdim=cross_attention_dim if cross_attention else width,
            vdim=cross_attention_dim if cross_attention else width,
        )
        self.norm2 = nn.LayerNorm(width, eps=1e-5, elementwise_affine=False)
        self.ff = GeluFeedForward(width, dropout)

    def forward(
        self,
        hidden_states: torch.Tensor,
        condition: torch.Tensor,
        *,
        encoder_hidden_states: torch.Tensor | None,
        encoder_attention_mask: torch.Tensor | None,
    ) -> torch.Tensor:
        """执行注意力残差和前馈残差。"""
        query = self.norm1(hidden_states, condition)
        if self.cross_attention:
            if encoder_hidden_states is None or encoder_attention_mask is None:
                raise ValueError("cross-attention block requires encoder states and mask")
            key_value = encoder_hidden_states
            key_padding_mask = ~encoder_attention_mask
        else:
            key_value = query
            key_padding_mask = None
        attended, _ = self.attn1(
            query,
            key_value,
            key_value,
            key_padding_mask=key_padding_mask,
            need_weights=False,
        )
        hidden_states = hidden_states + attended
        hidden_states = hidden_states + self.ff(self.norm2(hidden_states))
        return hidden_states


class AlternateVisionLanguageDiffusionTransformer(nn.Module):
    """交替执行文本交叉、图像交叉和自注意力的 N1.6.1 DiT。"""

    def __init__(
        self,
        *,
        num_layers: int,
        num_attention_heads: int,
        attention_head_dim: int,
        output_dim: int,
        cross_attention_dim: int,
        dropout: float,
        attend_text_every_n_blocks: int,
    ) -> None:
        """构造固定深度交替 block 和输出 AdaLN。"""
        initialize_torch_module(super())
        if num_layers <= 0 or num_layers % 2:
            raise ValueError("num_layers must be positive and even")
        if attend_text_every_n_blocks <= 0:
            raise ValueError("attend_text_every_n_blocks must be positive")
        self.width = num_attention_heads * attention_head_dim
        self.attend_text_every_n_blocks = attend_text_every_n_blocks
        self.time_encoder = TimestepEncoder(self.width)
        self.transformer_blocks = nn.ModuleList(
            TransformerBlock(
                self.width,
                num_attention_heads,
                cross_attention_dim=cross_attention_dim,
                dropout=dropout,
                cross_attention=index % 2 == 0,
            )
            for index in range(num_layers)
        )
        self.norm_out = nn.LayerNorm(self.width, elementwise_affine=False)
        self.proj_out_1 = nn.Linear(self.width, 2 * self.width)
        self.proj_out_2 = nn.Linear(self.width, output_dim)

    def forward(
        self,
        hidden_states: torch.Tensor,
        encoder_hidden_states: torch.Tensor,
        *,
        timestep: torch.Tensor,
        image_mask: torch.Tensor,
        backbone_attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """返回 ``[B,T,output_dim]`` 状态动作表示。"""
        if hidden_states.ndim != 3 or hidden_states.shape[-1] != self.width:
            raise ValueError("hidden_states width does not match configured DiT width")
        if image_mask.shape != backbone_attention_mask.shape:
            raise ValueError("image and backbone masks must share [B,S] shape")
        if image_mask.dtype != torch.bool or backbone_attention_mask.dtype != torch.bool:
            raise TypeError("DiT encoder masks must be strict torch.bool")
        condition = self.time_encoder(timestep)
        text_mask = backbone_attention_mask & ~image_mask
        visual_mask = backbone_attention_mask & image_mask
        for index, block in enumerate(self.transformer_blocks):
            current_mask: torch.Tensor | None = None
            encoder: torch.Tensor | None = None
            if index % 2 == 0:
                encoder = encoder_hidden_states
                cross_index = index // 2
                current_mask = (
                    text_mask if cross_index % self.attend_text_every_n_blocks == 0 else visual_mask
                )
                # 空分区会令注意力产生 NaN,回退到所有有效 token。
                empty_rows = ~current_mask.any(dim=1)
                if bool(empty_rows.any()):
                    current_mask = current_mask.clone()
                    current_mask[empty_rows] = backbone_attention_mask[empty_rows]
            hidden_states = block(
                hidden_states,
                condition,
                encoder_hidden_states=encoder,
                encoder_attention_mask=current_mask,
            )
        shift, scale = self.proj_out_1(F.silu(condition)).chunk(2, dim=-1)
        normalized = self.norm_out(hidden_states)
        normalized = normalized * (1.0 + scale.unsqueeze(1)) + shift.unsqueeze(1)
        return self.proj_out_2(normalized)


__all__ = [
    "AdaptiveLayerNorm",
    "AlternateVisionLanguageDiffusionTransformer",
    "TimestepEncoder",
    "TransformerBlock",
]
