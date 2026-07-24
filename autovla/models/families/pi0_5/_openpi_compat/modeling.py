# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# License: Apache-2.0 source; model, tokenizer and checkpoint terms are separate.
# Reuse: Materially adapted PyTorch module topology and tensor semantics.
# AutoVLA changes: Local modules, explicit masks and no OpenPI runtime dependency.
# ruff: noqa: RUF002
"""Pi0.5 官方图与命名空间的家族私有纯 PyTorch 实现。"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.checkpoint import checkpoint


@dataclass(frozen=True, slots=True)
class PrefixKVCache:
    """保存各 PaliGemma 层产生的只读前缀 K/V。"""

    keys: tuple[torch.Tensor, ...]
    values: tuple[torch.Tensor, ...]
    mask: torch.Tensor
    positions: torch.Tensor

    def __post_init__(self) -> None:
        """关闭层数、形状和 dtype 不变量。"""

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
    """实现 Gemma 的零初始化偏移 RMSNorm。"""

    def __init__(self, width: int, epsilon: float) -> None:
        """注册与官方 checkpoint 一致的 ``weight``。"""

        super().__init__()
        self.weight = nn.Parameter(torch.zeros(width))
        self.epsilon = epsilon

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """用 float32 归约并恢复输入 dtype。"""

        variance = hidden.float().square().mean(dim=-1, keepdim=True)
        normalized = hidden.float() * torch.rsqrt(variance + self.epsilon)
        return (normalized * (1.0 + self.weight.float())).to(hidden.dtype)


class AdaRMSNorm(nn.Module):
    """实现官方 expert 的条件 scale、shift 和 residual gate。"""

    def __init__(self, width: int, condition_width: int, epsilon: float) -> None:
        """注册转换目标所需的 ``dense`` 参数名。"""

        super().__init__()
        self.dense = nn.Linear(condition_width, width * 3)
        nn.init.zeros_(self.dense.weight)
        self.epsilon = epsilon

    def forward(
        self,
        hidden: torch.Tensor,
        condition: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        """返回条件归一化激活和当前残差门。"""

        scale, shift, gate = self.dense(condition).chunk(3, dim=-1)
        variance = hidden.float().square().mean(dim=-1, keepdim=True)
        normalized = hidden * torch.rsqrt(variance + self.epsilon)
        return (
            (
                normalized * (1.0 + scale.float()[:, None])
                + shift.float()[:, None]
            ).to(hidden.dtype),
            gate[:, None].to(hidden.dtype),
        )


def _rotate_half(value: torch.Tensor) -> torch.Tensor:
    """按 Gemma/Hugging Face 的前后半通道布局旋转。"""

    first, second = value.chunk(2, dim=-1)
    return torch.cat((-second, first), dim=-1)


def apply_rotary_embedding(
    query: torch.Tensor,
    key: torch.Tensor,
    positions: torch.Tensor,
    *,
    theta: float,
) -> tuple[torch.Tensor, torch.Tensor]:
    """向 ``[B,H,L,D]`` Q/K 应用官方 Gemma RoPE。"""

    head_dim = query.shape[-1]
    if key.shape[-1] != head_dim or head_dim % 2:
        raise ValueError("RoPE requires equal even Q/K head dimensions")
    inverse = 1.0 / (
        theta
        ** (
            torch.arange(0, head_dim, 2, device=query.device, dtype=torch.float32)
            / head_dim
        )
    )
    angles = positions.float()[:, :, None] * inverse[None, None, :]
    angles = torch.cat((angles, angles), dim=-1)[:, None]
    cosine = angles.cos().to(query.dtype)
    sine = angles.sin().to(query.dtype)
    return (
        query * cosine + _rotate_half(query) * sine,
        key * cosine + _rotate_half(key) * sine,
    )


class GemmaAttention(nn.Module):
    """实现独立 Q/K/V、GQA、RoPE 与显式前缀缓存。"""

    def __init__(
        self,
        width: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        *,
        rope_theta: float,
    ) -> None:
        """注册官方布局的四个无偏置投影。"""

        super().__init__()
        if num_kv_heads <= 0 or num_heads % num_kv_heads or head_dim % 2:
            raise ValueError("invalid Gemma attention head contract")
        self.num_heads = num_heads
        self.num_kv_heads = num_kv_heads
        self.head_dim = head_dim
        self.rope_theta = rope_theta
        self.q_proj = nn.Linear(width, num_heads * head_dim, bias=False)
        self.k_proj = nn.Linear(width, num_kv_heads * head_dim, bias=False)
        self.v_proj = nn.Linear(width, num_kv_heads * head_dim, bias=False)
        self.o_proj = nn.Linear(num_heads * head_dim, width, bias=False)

    def _project(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """一次生成当前序列的旋转 Q/K 和未旋转 V。"""

        batch, length, _ = hidden.shape
        query = self.q_proj(hidden).view(
            batch, length, self.num_heads, self.head_dim
        ).transpose(1, 2)
        key = self.k_proj(hidden).view(
            batch, length, self.num_kv_heads, self.head_dim
        ).transpose(1, 2)
        value = self.v_proj(hidden).view(
            batch, length, self.num_kv_heads, self.head_dim
        ).transpose(1, 2)
        query, key = apply_rotary_embedding(
            query,
            key,
            positions,
            theta=self.rope_theta,
        )
        return query, key, value

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
        *,
        prefix_kv: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """执行注意力并返回当前层自身 K/V 供前缀缓存。"""

        batch, length, _ = hidden.shape
        query, own_key, own_value = self._project(hidden, positions)
        key, value = own_key, own_value
        if prefix_kv is not None:
            key = torch.cat((prefix_kv[0], own_key), dim=-2)
            value = torch.cat((prefix_kv[1], own_value), dim=-2)
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
            attn_mask=attention_mask[:, None],
            dropout_p=0.0,
            enable_gqa=True,
        )
        projected = self.o_proj(output.transpose(1, 2).reshape(batch, length, -1))
        return projected, own_key, own_value


class GemmaMLP(nn.Module):
    """实现官方 Gemma gated GELU 前馈层。"""

    def __init__(self, width: int, intermediate_size: int) -> None:
        """注册 gate/up/down 三个无偏置投影。"""

        super().__init__()
        self.gate_proj = nn.Linear(width, intermediate_size, bias=False)
        self.up_proj = nn.Linear(width, intermediate_size, bias=False)
        self.down_proj = nn.Linear(intermediate_size, width, bias=False)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """执行近似 tanh 的 gated GELU。"""

        return self.down_proj(
            F.gelu(self.gate_proj(hidden), approximate="tanh") * self.up_proj(hidden)
        )


class GemmaPrefixLayer(nn.Module):
    """实现一个 PaliGemma 前缀层并暴露该层 K/V。"""

    def __init__(
        self,
        width: int,
        intermediate_size: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        *,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """创建转换器目标命名空间一致的层。"""

        super().__init__()
        self.self_attn = GemmaAttention(
            width,
            num_heads,
            num_kv_heads,
            head_dim,
            rope_theta=rope_theta,
        )
        self.mlp = GemmaMLP(width, intermediate_size)
        self.input_layernorm = RMSNorm(width, epsilon)
        self.post_attention_layernorm = RMSNorm(width, epsilon)

    def forward(
        self,
        hidden: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        """耦合执行当前前缀层并保存当前层 PaliGemma K/V。"""

        attended, key, value = self.self_attn(
            self.input_layernorm(hidden),
            positions,
            attention_mask,
        )
        hidden = hidden + attended
        hidden = hidden + self.mlp(self.post_attention_layernorm(hidden))
        return hidden, key, value


class GemmaExpertLayer(nn.Module):
    """实现一个条件 Gemma action expert 层。"""

    def __init__(
        self,
        width: int,
        intermediate_size: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        *,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """注册官方 expert 层和 AdaRMSNorm 命名。"""

        super().__init__()
        self.self_attn = GemmaAttention(
            width,
            num_heads,
            num_kv_heads,
            head_dim,
            rope_theta=rope_theta,
        )
        self.mlp = GemmaMLP(width, intermediate_size)
        self.input_layernorm = AdaRMSNorm(width, width, epsilon)
        self.post_attention_layernorm = AdaRMSNorm(width, width, epsilon)

    def forward(
        self,
        hidden: torch.Tensor,
        condition: torch.Tensor,
        positions: torch.Tensor,
        attention_mask: torch.Tensor,
        prefix_kv: tuple[torch.Tensor, torch.Tensor],
    ) -> torch.Tensor:
        """只读拼接同层 PaliGemma K/V 并执行两次门控残差。"""

        normalized, gate = self.input_layernorm(hidden, condition)
        attended, _, _ = self.self_attn(
            normalized,
            positions,
            attention_mask,
            prefix_kv=prefix_kv,
        )
        hidden = hidden + gate * attended
        normalized, gate = self.post_attention_layernorm(hidden, condition)
        return hidden + gate * self.mlp(normalized)


class GemmaLanguageModel(nn.Module):
    """承载官方 PaliGemma language-model 参数树。"""

    def __init__(
        self,
        *,
        vocab_size: int,
        width: int,
        intermediate_size: int,
        num_layers: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """注册 embedding、18 层前缀和最终 RMSNorm。"""

        super().__init__()
        self.embed_tokens = nn.Embedding(vocab_size, width)
        self.layers = nn.ModuleList(
            GemmaPrefixLayer(
                width,
                intermediate_size,
                num_heads,
                num_kv_heads,
                head_dim,
                epsilon=epsilon,
                rope_theta=rope_theta,
            )
            for _ in range(num_layers)
        )
        self.norm = RMSNorm(width, epsilon)


class GemmaExpertModel(nn.Module):
    """承载官方 Gemma expert 的 ``model.layers`` 参数树。"""

    def __init__(
        self,
        *,
        width: int,
        intermediate_size: int,
        num_layers: int,
        num_heads: int,
        num_kv_heads: int,
        head_dim: int,
        epsilon: float,
        rope_theta: float,
    ) -> None:
        """注册条件层和最终条件 RMSNorm。"""

        super().__init__()
        self.layers = nn.ModuleList(
            GemmaExpertLayer(
                width,
                intermediate_size,
                num_heads,
                num_kv_heads,
                head_dim,
                epsilon=epsilon,
                rope_theta=rope_theta,
            )
            for _ in range(num_layers)
        )
        self.norm = AdaRMSNorm(width, width, epsilon)


class GemmaExpert(nn.Module):
    """保持官方 ``gemma_expert.model`` 容器命名。"""

    def __init__(self, model: GemmaExpertModel) -> None:
        """注册唯一 expert 模型。"""

        super().__init__()
        self.model = model


class SiglipAttention(nn.Module):
    """实现 SigLIP 独立 Q/K/V/out 投影。"""

    def __init__(self, width: int, num_heads: int) -> None:
        """注册有偏置的官方视觉注意力参数。"""

        super().__init__()
        if width % num_heads:
            raise ValueError("SigLIP width must divide evenly into heads")
        self.num_heads = num_heads
        self.head_dim = width // num_heads
        self.q_proj = nn.Linear(width, width)
        self.k_proj = nn.Linear(width, width)
        self.v_proj = nn.Linear(width, width)
        self.out_proj = nn.Linear(width, width)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """执行无 dropout 双向视觉自注意力。"""

        batch, length, width = hidden.shape
        query = self.q_proj(hidden).view(
            batch, length, self.num_heads, self.head_dim
        ).transpose(1, 2)
        key = self.k_proj(hidden).view(
            batch, length, self.num_heads, self.head_dim
        ).transpose(1, 2)
        value = self.v_proj(hidden).view(
            batch, length, self.num_heads, self.head_dim
        ).transpose(1, 2)
        output = F.scaled_dot_product_attention(query, key, value, dropout_p=0.0)
        return self.out_proj(output.transpose(1, 2).reshape(batch, length, width))


class SiglipMLP(nn.Module):
    """实现 SigLIP 两层 MLP。"""

    def __init__(self, width: int, intermediate_size: int) -> None:
        """注册转换目标所需的 ``fc1`` 和 ``fc2``。"""

        super().__init__()
        self.fc1 = nn.Linear(width, intermediate_size)
        self.fc2 = nn.Linear(intermediate_size, width)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """执行官方近似 GELU。"""

        return self.fc2(F.gelu(self.fc1(hidden), approximate="tanh"))


class SiglipEncoderLayer(nn.Module):
    """实现一个 SigLIP pre-norm 编码层。"""

    def __init__(self, width: int, intermediate_size: int, num_heads: int) -> None:
        """注册官方层名称。"""

        super().__init__()
        self.self_attn = SiglipAttention(width, num_heads)
        self.layer_norm1 = nn.LayerNorm(width)
        self.mlp = SiglipMLP(width, intermediate_size)
        self.layer_norm2 = nn.LayerNorm(width)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """执行两个残差子层。"""

        hidden = hidden + self.self_attn(self.layer_norm1(hidden))
        return hidden + self.mlp(self.layer_norm2(hidden))


class SiglipEncoder(nn.Module):
    """保持官方 ``encoder.layers`` 参数树。"""

    def __init__(
        self,
        width: int,
        intermediate_size: int,
        num_layers: int,
        num_heads: int,
    ) -> None:
        """注册固定视觉层序列。"""

        super().__init__()
        self.layers = nn.ModuleList(
            SiglipEncoderLayer(width, intermediate_size, num_heads)
            for _ in range(num_layers)
        )


class SiglipVisionEmbeddings(nn.Module):
    """实现 patch 卷积和可转换的位置 embedding。"""

    def __init__(self, image_size: int, patch_size: int, width: int) -> None:
        """注册官方 ``patch_embedding`` 与 ``position_embedding``。"""

        super().__init__()
        self.patch_embedding = nn.Conv2d(3, width, patch_size, stride=patch_size)
        token_count = (image_size // patch_size) ** 2
        self.position_embedding = nn.Embedding(token_count, width)
        self.register_buffer(
            "position_ids",
            torch.arange(token_count).unsqueeze(0),
            persistent=False,
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """把图像变为 patch token 并叠加固定位置。"""

        hidden = self.patch_embedding(images).flatten(2).transpose(1, 2)
        if hidden.shape[1] != self.position_ids.shape[1]:
            raise ValueError("vision patch token count drifted from configuration")
        return hidden + self.position_embedding(self.position_ids)


class SiglipVisionModel(nn.Module):
    """实现官方 ``vision_model`` 参数树。"""

    def __init__(
        self,
        image_size: int,
        patch_size: int,
        width: int,
        intermediate_size: int,
        num_layers: int,
        num_heads: int,
    ) -> None:
        """注册 embedding、encoder 和 post layer norm。"""

        super().__init__()
        self.embeddings = SiglipVisionEmbeddings(image_size, patch_size, width)
        self.encoder = SiglipEncoder(width, intermediate_size, num_layers, num_heads)
        self.post_layernorm = nn.LayerNorm(width)
        self.gradient_checkpointing = False

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """编码 ``[B,3,224,224]`` 为 patch 序列。"""

        hidden = self.embeddings(images)
        for layer in self.encoder.layers:
            if self.gradient_checkpointing and self.training:
                hidden = checkpoint(layer, hidden, use_reentrant=False)
            else:
                hidden = layer(hidden)
        return self.post_layernorm(hidden)


class SiglipVisionTower(nn.Module):
    """保持官方 ``vision_tower.vision_model`` 容器命名。"""

    def __init__(self, vision_model: SiglipVisionModel) -> None:
        """注册唯一视觉模型。"""

        super().__init__()
        self.vision_model = vision_model

    @property
    def gradient_checkpointing(self) -> bool:
        """暴露视觉模型 checkpoint 开关。"""

        return self.vision_model.gradient_checkpointing

    @gradient_checkpointing.setter
    def gradient_checkpointing(self, enabled: bool) -> None:
        """转发视觉模型 checkpoint 开关。"""

        self.vision_model.gradient_checkpointing = enabled

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """转发视觉模型。"""

        return self.vision_model(images)


class MultiModalProjector(nn.Module):
    """保持官方 ``multi_modal_projector.linear`` 命名。"""

    def __init__(self, vision_width: int, language_width: int) -> None:
        """注册视觉到语言宽度的有偏置投影。"""

        super().__init__()
        self.linear = nn.Linear(vision_width, language_width)

    def forward(self, hidden: torch.Tensor) -> torch.Tensor:
        """投影视觉 token。"""

        return self.linear(hidden)


__all__ = [
    "AdaRMSNorm",
    "GemmaExpert",
    "GemmaExpertModel",
    "GemmaLanguageModel",
    "GemmaPrefixLayer",
    "MultiModalProjector",
    "PrefixKVCache",
    "RMSNorm",
    "SiglipVisionModel",
    "SiglipVisionTower",
    "apply_rotary_embedding",
]
