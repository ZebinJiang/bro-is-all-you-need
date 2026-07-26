# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Adapted from NVIDIA/Isaac-GR00T.
# Source revision: 9c7e746b2cd37a810070a98ef41d290a07e806c2
# Source path: gr00t/model/modules/dit.py
# Source blob: 4bb9994d3c89a738a830c5af927b1cd24d2854a5
# Source dependency: diffusers==0.35.1
# Local changes: removes ModelMixin/ConfigMixin side effects, adds Python 3.10
# typing and fail-closed validation, while retaining the official parameter
# modules, names, masks, positional flow, and timestep-conditioned tensor flow.

"""官方 AlternateVLDiT 与 SelfAttentionTransformer 的家族私有适配。"""

from __future__ import annotations

import os
from contextlib import nullcontext
from typing import ContextManager

import torch
from diffusers.models.attention import Attention, FeedForward
from diffusers.models.embeddings import (
    SinusoidalPositionalEmbedding,
    TimestepEmbedding,
    Timesteps,
)
from torch import nn
from torch.nn import functional as F

from autovla.models._torch_typing import initialize_torch_module


def _sdpa_context() -> ContextManager[None]:
    """在 Spark sm121 或显式请求时复用上游 math-SDPA 回退。"""

    override = os.environ.get("GR00T_DIT_SDPA_MODE")
    use_math = override == "math"
    if override not in {None, "math", "default"}:
        raise ValueError("GR00T_DIT_SDPA_MODE must be 'math' or 'default'")
    if override is None and torch.cuda.is_available():
        use_math = torch.cuda.get_device_capability() == (12, 1)
    if not use_math:
        return nullcontext()
    return torch.backends.cuda.sdp_kernel(
        enable_flash=False,
        enable_math=True,
        enable_mem_efficient=False,
        enable_cudnn=False,
    )


class TimestepEncoder(nn.Module):
    """保留官方 ``time_proj`` 与 ``timestep_embedder`` 容器命名。"""

    def __init__(self, embedding_dim: int) -> None:
        """构造 Diffusers 0.35.1 的固定频率和两层时间 MLP。"""

        initialize_torch_module(super())
        self.time_proj = Timesteps(
            num_channels=256,
            flip_sin_to_cos=True,
            downscale_freq_shift=1,
        )
        self.timestep_embedder = TimestepEmbedding(
            in_channels=256,
            time_embed_dim=embedding_dim,
        )

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        """返回 ``[B,W]`` 时间条件。"""

        if timesteps.ndim != 1:
            raise ValueError("DiT timesteps must have shape [B]")
        dtype = next(self.parameters()).dtype
        return self.timestep_embedder(self.time_proj(timesteps).to(dtype))


class AdaLayerNorm(nn.Module):
    """按时间条件缩放和平移无仿射 LayerNorm。"""

    def __init__(
        self,
        embedding_dim: int,
        norm_elementwise_affine: bool = False,
        norm_eps: float = 1e-5,
    ) -> None:
        """保留官方 ``silu``/``linear``/``norm`` 命名。"""

        initialize_torch_module(super())
        self.silu = nn.SiLU()
        self.linear = nn.Linear(embedding_dim, 2 * embedding_dim)
        self.norm = nn.LayerNorm(
            embedding_dim,
            eps=norm_eps,
            elementwise_affine=norm_elementwise_affine,
        )

    def forward(self, values: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        """应用 timestep-conditioned AdaNorm。"""

        scale, shift = self.linear(self.silu(condition)).chunk(2, dim=1)
        return self.norm(values) * (1.0 + scale[:, None]) + shift[:, None]


class BasicTransformerBlock(nn.Module):
    """保留官方 Diffusers attention/feed-forward 参数图和完整 tensor flow。"""

    def __init__(
        self,
        width: int,
        heads: int,
        head_dim: int,
        *,
        cross_attention_dim: int | None,
        dropout: float,
        attention_bias: bool,
        norm_type: str,
        norm_affine: bool,
        norm_epsilon: float,
        final_dropout: bool,
        positional_embeddings: str | None,
        max_positional_embeddings: int,
    ) -> None:
        """构造自注意力或交叉注意力 block。"""

        initialize_torch_module(super())
        if positional_embeddings not in {None, "sinusoidal"}:
            raise ValueError("official N1.7 supports only sinusoidal positional embeddings")
        if norm_type == "ada_norm":
            self.norm1: nn.Module = AdaLayerNorm(width)
        elif norm_type == "layer_norm":
            self.norm1 = nn.LayerNorm(
                width,
                eps=norm_epsilon,
                elementwise_affine=norm_affine,
            )
        else:
            raise ValueError("official N1.7 supports only ada_norm or layer_norm")
        self.pos_embed = (
            SinusoidalPositionalEmbedding(width, max_seq_length=max_positional_embeddings)
            if positional_embeddings == "sinusoidal"
            else None
        )
        self.attn1 = Attention(
            query_dim=width,
            heads=heads,
            dim_head=head_dim,
            dropout=dropout,
            bias=attention_bias,
            cross_attention_dim=cross_attention_dim,
            upcast_attention=False,
            out_bias=True,
        )
        self.norm3 = nn.LayerNorm(
            width,
            eps=norm_epsilon,
            elementwise_affine=norm_affine,
        )
        self.ff = FeedForward(
            width,
            dropout=dropout,
            activation_fn="gelu-approximate",
            final_dropout=final_dropout,
            inner_dim=None,
            bias=True,
        )
        self.final_dropout = nn.Dropout(dropout) if final_dropout else None
        self.norm_type = norm_type

    def forward(
        self,
        hidden_states: torch.Tensor,
        *,
        attention_mask: torch.Tensor | None = None,
        encoder_hidden_states: torch.Tensor | None = None,
        encoder_attention_mask: torch.Tensor | None = None,
        condition: torch.Tensor | None = None,
    ) -> torch.Tensor:
        """执行官方 attention、额外 final dropout 和前馈残差。"""

        if self.norm_type == "ada_norm":
            if condition is None or not isinstance(self.norm1, AdaLayerNorm):
                raise ValueError("AdaNorm block requires timestep condition")
            normalized = self.norm1(hidden_states, condition)
        else:
            normalized = self.norm1(hidden_states)
        if self.pos_embed is not None:
            normalized = self.pos_embed(normalized)
        with _sdpa_context():
            attended = self.attn1(
                normalized,
                encoder_hidden_states=encoder_hidden_states,
                attention_mask=(
                    encoder_attention_mask if encoder_hidden_states is not None else attention_mask
                ),
            )
        if self.final_dropout is not None:
            attended = self.final_dropout(attended)
        hidden_states = hidden_states + attended
        return hidden_states + self.ff(self.norm3(hidden_states))


class AlternateVLDiT(nn.Module):
    """复现 N1.7 交替文本交叉、动作自注意力和图像交叉流。"""

    def __init__(
        self,
        *,
        num_attention_heads: int,
        attention_head_dim: int,
        output_dim: int,
        num_layers: int,
        dropout: float,
        attention_bias: bool,
        norm_type: str,
        norm_elementwise_affine: bool,
        norm_eps: float,
        final_dropout: bool,
        positional_embeddings: str | None,
        max_positional_embeddings: int,
        interleave_self_attention: bool,
        cross_attention_dim: int,
        attend_text_every_n_blocks: int,
    ) -> None:
        """构造官方 AlternateVLDiT 参数图。"""

        initialize_torch_module(super())
        if num_layers <= 0 or num_layers % 2 or not interleave_self_attention:
            raise ValueError("AlternateVLDiT requires a positive even interleaved depth")
        if attend_text_every_n_blocks <= 0:
            raise ValueError("attend_text_every_n_blocks must be positive")
        self.inner_dim = num_attention_heads * attention_head_dim
        self.attend_text_every_n_blocks = attend_text_every_n_blocks
        self.timestep_encoder = TimestepEncoder(self.inner_dim)
        self.transformer_blocks = nn.ModuleList(
            BasicTransformerBlock(
                self.inner_dim,
                num_attention_heads,
                attention_head_dim,
                cross_attention_dim=cross_attention_dim if index % 2 == 0 else None,
                dropout=dropout,
                attention_bias=attention_bias,
                norm_type=norm_type,
                norm_affine=norm_elementwise_affine,
                norm_epsilon=norm_eps,
                final_dropout=final_dropout,
                positional_embeddings=positional_embeddings,
                max_positional_embeddings=max_positional_embeddings,
            )
            for index in range(num_layers)
        )
        self.norm_out = nn.LayerNorm(self.inner_dim, eps=1e-6, elementwise_affine=False)
        self.proj_out_1 = nn.Linear(self.inner_dim, 2 * self.inner_dim)
        self.proj_out_2 = nn.Linear(self.inner_dim, output_dim)

    def forward(
        self,
        hidden_states: torch.Tensor,
        encoder_hidden_states: torch.Tensor,
        timestep: torch.Tensor,
        *,
        image_mask: torch.Tensor,
        backbone_attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """按官方精确 mask 序列执行交替 block。"""

        if hidden_states.ndim != 3 or hidden_states.shape[-1] != self.inner_dim:
            raise ValueError("AlternateVLDiT hidden width mismatch")
        if (
            image_mask.shape != backbone_attention_mask.shape
            or image_mask.dtype != torch.bool
            or backbone_attention_mask.dtype != torch.bool
        ):
            raise TypeError("image and backbone masks must be strict bool[B,S]")
        image_attention_mask = image_mask & backbone_attention_mask
        non_image_attention_mask = (~image_mask) & backbone_attention_mask
        condition = self.timestep_encoder(timestep)
        for index, block in enumerate(self.transformer_blocks):
            if index % 2:
                hidden_states = block(hidden_states, condition=condition)
                continue
            current_mask = (
                non_image_attention_mask
                if index % (2 * self.attend_text_every_n_blocks) == 0
                else image_attention_mask
            )
            hidden_states = block(
                hidden_states,
                encoder_hidden_states=encoder_hidden_states,
                encoder_attention_mask=current_mask,
                condition=condition,
            )
        shift, scale = self.proj_out_1(F.silu(condition)).chunk(2, dim=1)
        normalized = self.norm_out(hidden_states)
        normalized = normalized * (1.0 + scale[:, None]) + shift[:, None]
        return self.proj_out_2(normalized)


class SelfAttentionTransformer(nn.Module):
    """复现 N1.7 可选 VL self-attention 参数图。"""

    def __init__(
        self,
        *,
        num_attention_heads: int,
        attention_head_dim: int,
        num_layers: int,
        dropout: float,
        attention_bias: bool,
        norm_elementwise_affine: bool,
        norm_eps: float,
        final_dropout: bool,
        positional_embeddings: str | None,
        max_positional_embeddings: int,
    ) -> None:
        """构造官方 ``transformer_blocks`` 容器。"""

        initialize_torch_module(super())
        width = num_attention_heads * attention_head_dim
        self.transformer_blocks = nn.ModuleList(
            BasicTransformerBlock(
                width,
                num_attention_heads,
                attention_head_dim,
                cross_attention_dim=None,
                dropout=dropout,
                attention_bias=attention_bias,
                norm_type="layer_norm",
                norm_affine=norm_elementwise_affine,
                norm_epsilon=norm_eps,
                final_dropout=final_dropout,
                positional_embeddings=positional_embeddings,
                max_positional_embeddings=max_positional_embeddings,
            )
            for _ in range(num_layers)
        )

    def forward(self, hidden_states: torch.Tensor) -> torch.Tensor:
        """逐层执行 VL 自注意力, 不引入额外输出投影。"""

        for block in self.transformer_blocks:
            hidden_states = block(hidden_states)
        return hidden_states


__all__ = [
    "AdaLayerNorm",
    "AlternateVLDiT",
    "BasicTransformerBlock",
    "SelfAttentionTransformer",
    "TimestepEncoder",
]
