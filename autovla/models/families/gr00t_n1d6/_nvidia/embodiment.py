# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# Licensed under the NVIDIA License; see licenses/NVIDIA-ISAAC-GROOT-N1D6.txt.
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a:
# gr00t/model/modules/embodiment_conditioned_mlp.py.
"""N1.6.1 多 embodiment 参数库。"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from autovla.models._torch_typing import initialize_torch_module


class CategorySpecificLinear(nn.Module):
    """按样本 embodiment ID 选择独立线性参数。"""

    def __init__(
        self,
        num_categories: int,
        input_dim: int,
        output_dim: int,
    ) -> None:
        """初始化 ``[category,input,output]`` 参数库。"""
        initialize_torch_module(super())
        if num_categories <= 0 or input_dim <= 0 or output_dim <= 0:
            raise ValueError("category-specific dimensions must be positive")
        self.num_categories = num_categories
        self.W = nn.Parameter(0.02 * torch.randn(num_categories, input_dim, output_dim))
        self.b = nn.Parameter(torch.zeros(num_categories, output_dim))

    def forward(self, values: torch.Tensor, category_ids: torch.Tensor) -> torch.Tensor:
        """把 ``[B,T,I]`` 映射为 ``[B,T,O]``。"""
        if values.ndim != 3 or category_ids.shape != (values.shape[0],):
            raise ValueError("values must be [B,T,I] and category_ids must be [B]")
        if category_ids.dtype != torch.long:
            raise TypeError("category_ids must use torch.long")
        if bool(torch.any(category_ids < 0)) or bool(
            torch.any(category_ids >= self.num_categories)
        ):
            raise ValueError("category_ids exceed configured embodiment bank")
        weights = self.W[category_ids]
        biases = self.b[category_ids]
        return torch.bmm(values, weights) + biases.unsqueeze(1)


class CategorySpecificMLP(nn.Module):
    """使用两层 embodiment 专用参数的 MLP。"""

    def __init__(
        self,
        num_categories: int,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
    ) -> None:
        """构造两层参数库。"""
        initialize_torch_module(super())
        self.layer1 = CategorySpecificLinear(num_categories, input_dim, hidden_dim)
        self.layer2 = CategorySpecificLinear(num_categories, hidden_dim, output_dim)

    def forward(self, values: torch.Tensor, category_ids: torch.Tensor) -> torch.Tensor:
        """执行 ReLU 激活的两层映射。"""
        return self.layer2(F.relu(self.layer1(values, category_ids)), category_ids)


class SinusoidalPositionalEncoding(nn.Module):
    """把离散时间 ``[B,T]`` 编码为 ``[B,T,C]``。"""

    def __init__(self, embedding_dim: int) -> None:
        """保存偶数编码宽度。"""
        initialize_torch_module(super())
        if embedding_dim <= 0 or embedding_dim % 2:
            raise ValueError("embedding_dim must be a positive even number")
        self.embedding_dim = embedding_dim

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        """计算固定正弦/余弦时间特征。"""
        if timesteps.ndim != 2:
            raise ValueError("timesteps must have shape [B,T]")
        half_dim = self.embedding_dim // 2
        exponent = -torch.arange(
            half_dim,
            dtype=torch.float32,
            device=timesteps.device,
        ) * (math.log(10000.0) / half_dim)
        frequencies = timesteps.float().unsqueeze(-1) * exponent.exp()
        return torch.cat((frequencies.sin(), frequencies.cos()), dim=-1)


class MultiEmbodimentActionEncoder(nn.Module):
    """联合编码动作轨迹、离散时间和 embodiment。"""

    def __init__(self, action_dim: int, hidden_size: int, num_embodiments: int) -> None:
        """构造三个 checkpoint 可寻址的参数库。"""
        initialize_torch_module(super())
        self.W1 = CategorySpecificLinear(num_embodiments, action_dim, hidden_size)
        self.W2 = CategorySpecificLinear(num_embodiments, 2 * hidden_size, hidden_size)
        self.W3 = CategorySpecificLinear(num_embodiments, hidden_size, hidden_size)
        self.pos_encoding = SinusoidalPositionalEncoding(hidden_size)

    def forward(
        self,
        actions: torch.Tensor,
        timesteps: torch.Tensor,
        category_ids: torch.Tensor,
    ) -> torch.Tensor:
        """返回 ``[B,H,C]`` 动作时间特征。"""
        if actions.ndim != 3 or timesteps.shape != (actions.shape[0],):
            raise ValueError("actions must be [B,H,D] and timesteps must be [B]")
        repeated_time = timesteps.unsqueeze(1).expand(-1, actions.shape[1])
        action_embedding = self.W1(actions, category_ids)
        time_embedding = self.pos_encoding(repeated_time).to(dtype=action_embedding.dtype)
        combined = torch.cat((action_embedding, time_embedding), dim=-1)
        return self.W3(F.silu(self.W2(combined, category_ids)), category_ids)


__all__ = [
    "CategorySpecificLinear",
    "CategorySpecificMLP",
    "MultiEmbodimentActionEncoder",
    "SinusoidalPositionalEncoding",
]
