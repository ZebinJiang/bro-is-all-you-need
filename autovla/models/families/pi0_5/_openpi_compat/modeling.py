# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# License status: OpenPI source recorded as Apache-2.0; exact pin receipt awaits Wave 4.
# Purpose: family-local clean PyTorch compatibility for Pi0.5 attention and adaRMSNorm.
# Risk: architecture contract only; no numerical parity or official checkpoint proof yet.
# ruff: noqa: RUF002
"""OpenPI Pi0.5 张量契约的家族私有 PyTorch 清洁实现。"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint


@dataclass(frozen=True, slots=True)
class PrefixKVCache:
    """保存每层只读前缀 K/V 及严格有效 mask。

    K/V 形状为 ``[B,K,P,D]``，mask 为 ``bool[B,P]``。该值对象只保存
    推理图中的张量引用；suffix 层只拼接读取，不会把 suffix K/V 写回。
    """

    keys: tuple[torch.Tensor, ...]
    values: tuple[torch.Tensor, ...]
    mask: torch.Tensor
    positions: torch.Tensor

    def __post_init__(self) -> None:
        """关闭层数、形状、dtype 和前缀位置不变量。"""

        if not self.keys or len(self.keys) != len(self.values):
            raise ValueError("prefix cache requires equal non-empty K/V tuples")
        if self.mask.dtype != torch.bool or self.mask.ndim != 2:
            raise TypeError("prefix cache mask must use bool[B,P]")
        if self.positions.dtype != torch.long or self.positions.shape != self.mask.shape:
            raise TypeError("prefix cache positions must use long[B,P]")
        for key, value in zip(self.keys, self.values, strict=True):
            if key.shape != value.shape or key.ndim != 4:
                raise ValueError("prefix K/V tensors must share [B,K,P,D]")
            if key.shape[0] != self.mask.shape[0] or key.shape[-2] != self.mask.shape[1]:
                raise ValueError("prefix K/V batch and sequence must match mask")


class RMSNorm(nn.Module):
    """以 float32 归约并恢复输入 dtype 的 Gemma RMSNorm。"""

    def __init__(self, width: int, epsilon: float) -> None:
        """创建 Gemma 风格的零初始化偏移权重。"""

        super().__init__()
        self.weight = nn.Parameter(torch.zeros(width))
        self.epsilon = epsilon

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """归一化最后一维，返回与输入同 dtype 的张量。"""

        variance = hidden.float().square().mean(dim=-1, keepdim=True)
        normalized = hidden.float() * torch.rsqrt(variance + self.epsilon)
        return (normalized * (1.0 + self.weight.float())).to(dtype=hidden.dtype)


def apply_rotary_embedding(
    query: torch.Tensor,
    key: torch.Tensor,
    positions: torch.Tensor,
    *,
    theta: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """按 ``long[B,L]`` 位置向 Q/K 的偶奇通道应用 RoPE。"""

    head_dim = query.shape[-1]
    if head_dim % 2 or key.shape[-1] != head_dim:
        raise ValueError("RoPE requires equal even Q/K head dimensions")
    frequencies = torch.arange(0, head_dim, 2, device=query.device, dtype=torch.float32)
    frequencies = theta ** (-frequencies / head_dim)
    angles = positions.float()[:, None, :, None] * frequencies[None, None, None, :]
    cosine = angles.cos().to(dtype=query.dtype)
    sine = angles.sin().to(dtype=query.dtype)

    def rotate(value: torch.Tensor) -> torch.Tensor:
        """旋转一个 ``[B,K,L,D]`` 张量。"""

        even, odd = value[..., 0::2], value[..., 1::2]
        return torch.stack(
            (even * cosine - odd * sine, odd * cosine + even * sine), dim=-1
        ).flatten(-2)

    return rotate(query), rotate(key)


def _expand_kv(value: torch.Tensor, num_heads: int) -> torch.Tensor:
    """把 GQA K/V 头按组扩展为 query 头，不复制持久参数。"""

    if num_heads % value.shape[1]:
        raise ValueError("query heads must be divisible by key/value heads")
    return value.repeat_interleave(num_heads // value.shape[1], dim=1)


class GemmaAttention(nn.Module):
    """支持 GQA、RoPE、显式 mask 和外部前缀 K/V 的注意力层。"""

    def __init__(
        self,
        width: int,
        num_heads: int,
        num_kv_heads: int,
        *,
        rope_theta: float,
    ) -> None:
        """注册标准 Q/K/V/O 投影。"""

        super().__init__()
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = width // num_heads
        self.rope_theta = rope_theta
        self.q_proj = nn.Linear(width, num_heads * self.head_dim, bias=False)
        self.k_proj = nn.Linear(width, num_kv_heads * self.head_dim, bias=False)
        self.v_proj = nn.Linear(width, num_kv_heads * self.head_dim, bias=False)
        self.o_proj = nn.Linear(num_heads * self.head_dim, width, bias=False)

    def project_kv(
        self, hidden: torch.Tensor, positions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """仅投影前缀 K/V，供一次 prefill 后复用。"""

        batch, length, _ = hidden.shape
        key = (
            self.k_proj(hidden)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        value = (
            self.v_proj(hidden)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        dummy = torch.zeros(
            batch,
            self.num_heads,
            length,
            self.head_dim,
            dtype=key.dtype,
            device=key.device,
        )
        _, key = apply_rotary_embedding(dummy, key, positions, theta=self.rope_theta)
        return key, value

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
        *,
        prefix_kv: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> torch.Tensor:
        """执行当前序列注意力，并只读拼接可选前缀 K/V。"""

        batch, length, _ = hidden.shape
        query = (
            self.q_proj(hidden).view(batch, length, self.num_heads, self.head_dim).transpose(1, 2)
        )
        key = (
            self.k_proj(hidden)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        value = (
            self.v_proj(hidden)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        query, key = apply_rotary_embedding(query, key, positions, theta=self.rope_theta)
        if prefix_kv is not None:
            prefix_key, prefix_value = prefix_kv
            key = torch.cat((prefix_key, key), dim=-2)
            value = torch.cat((prefix_value, value), dim=-2)
        key = _expand_kv(key, self.num_heads)
        value = _expand_kv(value, self.num_heads)
        if attention_mask.dtype != torch.bool or attention_mask.shape != (
            batch,
            length,
            key.shape[-2],
        ):
            raise ValueError("attention mask must use bool[B,Q,K]")
        output = F.scaled_dot_product_attention(
            query,
            key,
            value,
            attn_mask=attention_mask[:, None, :, :],
            dropout_p=0.0,
        )
        return self.o_proj(output.transpose(1, 2).reshape(batch, length, -1))


class GemmaMLP(nn.Module):
    """实现 Gemma gated-GELU 前馈层。"""

    def __init__(self, width: int, intermediate_size: int) -> None:
        """注册 gate/up/down 三个无偏置投影。"""

        super().__init__()
        self.gate_proj = nn.Linear(width, intermediate_size, bias=False)
        self.up_proj = nn.Linear(width, intermediate_size, bias=False)
        self.down_proj = nn.Linear(intermediate_size, width, bias=False)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """执行 gated GELU 前馈。"""

        return self.down_proj(
            F.gelu(self.gate_proj(hidden), approximate="tanh") * self.up_proj(hidden)
        )


class GemmaPrefixLayer(nn.Module):
    """执行 PaliGemma 前缀自注意力和前馈残差。"""

    def __init__(
        self,
        width: int,
        intermediate_size: int,
        num_heads: int,
        num_kv_heads: int,
        *,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """创建一层前缀 Transformer。"""

        super().__init__()
        self.input_norm = RMSNorm(width, epsilon)
        self.attention = GemmaAttention(width, num_heads, num_kv_heads, rope_theta=rope_theta)
        self.post_attention_norm = RMSNorm(width, epsilon)
        self.mlp = GemmaMLP(width, intermediate_size)

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> torch.Tensor:
        """执行双残差前缀层。"""

        hidden = hidden + self.attention(self.input_norm(hidden), positions, attention_mask)
        return hidden + self.mlp(self.post_attention_norm(hidden))


class AdaRMSBlock(nn.Module):
    """用时间条件 scale/shift/gate 驱动 Gemma 动作 expert 层。"""

    def __init__(
        self,
        width: int,
        intermediate_size: int,
        num_heads: int,
        num_kv_heads: int,
        prefix_width: int,
        *,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """注册 expert、自适应条件和跨宽度前缀 K/V 投影。"""

        super().__init__()
        self.width = width
        self.epsilon = epsilon
        self.attention = GemmaAttention(width, num_heads, num_kv_heads, rope_theta=rope_theta)
        self.mlp = GemmaMLP(width, intermediate_size)
        self.attention_condition = nn.Linear(width, 3 * width)
        self.mlp_condition = nn.Linear(width, 3 * width)
        self.prefix_key = nn.Linear(prefix_width, num_kv_heads * (width // num_heads), bias=False)
        self.prefix_value = nn.Linear(prefix_width, num_kv_heads * (width // num_heads), bias=False)
        self.num_kv_heads = num_kv_heads
        self.head_dim = width // num_heads
        self.rope_theta = rope_theta

    def prefix_kv(
        self, prefix: torch.Tensor, positions: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """从共享前缀特征生成本层不可变 K/V。"""

        batch, length, _ = prefix.shape
        key = (
            self.prefix_key(prefix)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        value = (
            self.prefix_value(prefix)
            .view(batch, length, self.num_kv_heads, self.head_dim)
            .transpose(1, 2)
        )
        dummy = torch.zeros(batch, 1, length, self.head_dim, dtype=key.dtype, device=key.device)
        _, key = apply_rotary_embedding(dummy, key, positions, theta=self.rope_theta)
        return key, value

    def _condition(
        self, hidden: torch.Tensor, condition: torch.Tensor, projection: nn.Linear
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """计算 AdaRMSNorm 激活与残差门。"""

        scale, shift, gate = projection(condition).chunk(3, dim=-1)
        variance = hidden.float().square().mean(dim=-1, keepdim=True)
        normalized = (hidden.float() * torch.rsqrt(variance + self.epsilon)).to(hidden.dtype)
        return normalized * (1.0 + scale[:, None]) + shift[:, None], gate[:, None]

    def forward(
        self,
        hidden: torch.Tensor,
        condition: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
        prefix_kv: tuple[torch.Tensor, torch.Tensor],
    ) -> torch.Tensor:
        """执行两次 AdaRMSNorm 门控残差，前缀缓存保持只读。"""

        normalized, gate = self._condition(hidden, condition, self.attention_condition)
        hidden = hidden + gate * self.attention(
            normalized,
            positions,
            attention_mask,
            prefix_kv=prefix_kv,
        )
        normalized, gate = self._condition(hidden, condition, self.mlp_condition)
        return hidden + gate * self.mlp(normalized)


class SiglipVisionTower(nn.Module):
    """以 14x14 patch 和双向 Transformer 编码 224 图像。"""

    def __init__(
        self,
        image_size: int,
        patch_size: int,
        width: int,
        intermediate_size: int,
        num_layers: int,
        num_heads: int,
    ) -> None:
        """注册 patch embedding、位置向量和 SigLIP 编码层。"""

        super().__init__()
        self.patch_embedding = nn.Conv2d(3, width, patch_size, stride=patch_size)
        token_count = (image_size // patch_size) ** 2
        self.position_embedding = nn.Parameter(torch.zeros(1, token_count, width))
        self.layers = nn.ModuleList(
            nn.TransformerEncoderLayer(
                width,
                num_heads,
                intermediate_size,
                dropout=0.0,
                activation="gelu",
                batch_first=True,
                norm_first=True,
            )
            for _ in range(num_layers)
        )
        self.post_layernorm = nn.LayerNorm(width)
        self.gradient_checkpointing = False

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """把 ``[B,3,224,224]`` 编码为 ``[B,256,C]`` patch 序列。"""

        hidden = self.patch_embedding(images).flatten(2).transpose(1, 2)
        if hidden.shape[1] != self.position_embedding.shape[1]:
            raise ValueError("vision patch token count drifted from configuration")
        hidden = hidden + self.position_embedding
        for layer in self.layers:
            if self.gradient_checkpointing and self.training:
                hidden = checkpoint(layer, hidden, use_reentrant=False)
            else:
                hidden = layer(hidden)
        return self.post_layernorm(hidden)
