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
# Source path: gr00t/model/modules/embodiment_conditioned_mlp.py
# Source blob: 504785d57cc33a87613dd775cc415cc88574c2ee
# Local changes: Python 3.10 typing, Chinese documentation, strict shape checks.

"""官方 category-specific 状态与动作投影器的家族私有适配。"""

from __future__ import annotations

import math

import torch
from torch import nn
from torch.nn import functional as F

from autovla.models._torch_typing import initialize_torch_module


class CategorySpecificLinear(nn.Module):
    """为每个 embodiment 保存独立 ``W`` 和 ``b`` 参数。"""

    def __init__(self, num_categories: int, input_dim: int, output_dim: int) -> None:
        """按官方 ``[C,Din,Dout]`` 命名和初始化构造参数。"""

        initialize_torch_module(super())
        if min(num_categories, input_dim, output_dim) <= 0:
            raise ValueError("category-specific linear dimensions must be positive")
        self.num_categories = num_categories
        self.W = nn.Parameter(0.02 * torch.randn(num_categories, input_dim, output_dim))
        self.b = nn.Parameter(torch.zeros(num_categories, output_dim))

    def forward(self, values: torch.Tensor, category_ids: torch.Tensor) -> torch.Tensor:
        """对 ``[B,T,Din]`` 使用逐样本 projector。"""

        if values.ndim != 3 or category_ids.shape != (values.shape[0],):
            raise ValueError("category-specific linear expects [B,T,D] and category_ids[B]")
        if category_ids.dtype != torch.long:
            raise TypeError("category_ids must use torch.long")
        return torch.bmm(values, self.W[category_ids]) + self.b[category_ids].unsqueeze(1)


class CategorySpecificMLP(nn.Module):
    """保留官方 ``layer1``/``layer2`` checkpoint 命名。"""

    def __init__(
        self,
        num_categories: int,
        input_dim: int,
        hidden_dim: int,
        output_dim: int,
    ) -> None:
        """构造两层 category-specific ReLU MLP。"""

        initialize_torch_module(super())
        self.layer1 = CategorySpecificLinear(num_categories, input_dim, hidden_dim)
        self.layer2 = CategorySpecificLinear(num_categories, hidden_dim, output_dim)

    def forward(self, values: torch.Tensor, category_ids: torch.Tensor) -> torch.Tensor:
        """返回 ``[B,T,Dout]``。"""

        return self.layer2(F.relu(self.layer1(values, category_ids)), category_ids)


class SinusoidalPositionalEncoding(nn.Module):
    """按官方频率公式编码每个动作 token 的扩散时间。"""

    def __init__(self, embedding_dim: int) -> None:
        """记录偶数 embedding 宽度, 不创建 checkpoint 参数。"""

        initialize_torch_module(super())
        if embedding_dim <= 0 or embedding_dim % 2:
            raise ValueError("sinusoidal action encoding requires a positive even width")
        self.embedding_dim = embedding_dim

    def forward(self, timesteps: torch.Tensor) -> torch.Tensor:
        """把 ``[B,T]`` 时间转换为 ``[B,T,W]``。"""

        if timesteps.ndim != 2:
            raise ValueError("expanded timesteps must have shape [B,T]")
        half = self.embedding_dim // 2
        exponent = -torch.arange(
            half,
            dtype=torch.float32,
            device=timesteps.device,
        ) * (math.log(10000.0) / half)
        frequencies = timesteps.float().unsqueeze(-1) * exponent.exp()
        return torch.cat((frequencies.sin(), frequencies.cos()), dim=-1)


class MultiEmbodimentActionEncoder(nn.Module):
    """保留官方 ``W1``/``W2``/``W3`` 参数图和时间拼接顺序。"""

    def __init__(self, action_dim: int, hidden_size: int, num_embodiments: int) -> None:
        """构造动作、时间和最终 projector。"""

        initialize_torch_module(super())
        self.hidden_size = hidden_size
        self.num_embodiments = num_embodiments
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
        """执行官方 action projector 的完整 tensor flow。"""

        if actions.ndim != 3 or timesteps.shape != (actions.shape[0],):
            raise ValueError("action encoder expects actions[B,T,D] and timesteps[B]")
        expanded_time = timesteps.unsqueeze(1).expand(-1, actions.shape[1])
        action_embedding = self.W1(actions, category_ids)
        time_embedding = self.pos_encoding(expanded_time).to(dtype=action_embedding.dtype)
        hidden = torch.cat((action_embedding, time_embedding), dim=-1)
        hidden = self.W2(hidden, category_ids)
        hidden = hidden * torch.sigmoid(hidden)
        return self.W3(hidden, category_ids)


__all__ = [
    "CategorySpecificLinear",
    "CategorySpecificMLP",
    "MultiEmbodimentActionEncoder",
    "SinusoidalPositionalEncoding",
]
