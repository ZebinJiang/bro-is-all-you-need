# SPDX-License-Identifier: Apache-2.0
# Source: https://github.com/Physical-Intelligence/openpi/tree/15a9616a00943ada6c20a0f158e3adb39df2ccac
# License: Apache-2.0 source; model, tokenizer and checkpoint terms are separate.
# Reuse: Materially adapted PaliGemma/SigLIP prefix execution semantics.
# AutoVLA changes: Family interface, explicit masks and layer-local immutable K/V output.
# ruff: noqa: RUF002,RUF003
"""Pi0.5 PaliGemma/SigLIP 前缀骨干与显式 mask/position 契约。"""

from __future__ import annotations

import hashlib
import math
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import cast

import numpy as np
import torch
from numpy.typing import NDArray
from torch.utils.checkpoint import checkpoint

from autovla.models.families.pi0_5._openpi_compat import (
    GemmaLanguageModel,
    MultiModalProjector,
    SiglipVisionModel,
    SiglipVisionTower,
)
from autovla.models.families.pi0_5.config import Pi05Config
from autovla.models.interfaces.backbone import VisionLanguageBackbone
from autovla.models.outputs import BackboneOutput, ModelInputBatch


def _freeze_value(value: object) -> object:
    """复制兼容性 cache 值；NumPy 副本额外设为只读。"""

    if isinstance(value, np.ndarray):
        output = np.array(value, copy=True)
        output.setflags(write=False)
        return output
    clone = getattr(value, "clone", None)
    if not callable(clone):
        raise TypeError("prefix cache values must be NumPy arrays or cloneable tensors")
    output = clone()
    if output is value:
        raise TypeError("tensor backend clone must return independently owned storage")
    return output


def _shape(value: object) -> tuple[int, ...]:
    """读取数组或张量形状。"""

    raw = getattr(value, "shape", None)
    if raw is None:
        raise TypeError("cache value must expose shape")
    return tuple(int(item) for item in raw)


class Pi05VisionLanguageBackbone(VisionLanguageBackbone):
    """编码三路 SigLIP 图像和 prompt/state token 的 PaliGemma 前缀。

    生产工厂传入 ``build_modules=True``，从配置创建全部注册参数。默认关闭
    仅保留 M10 的 import-light cache 契约检查，生产 ``forward`` 会失败关闭。
    """

    def __init__(self, config: Pi05Config, *, build_modules: bool = False) -> None:
        """按显式开关注册 SigLIP、投影器、token embedding 和 Gemma 前缀层。"""

        super().__init__()
        self.config = config
        self.gradient_checkpointing = config.gradient_checkpointing
        self.vision_tower: SiglipVisionTower | None = None
        self.multi_modal_projector: MultiModalProjector | None = None
        self.language_model: GemmaLanguageModel | None = None
        if build_modules:
            self.vision_tower = SiglipVisionTower(
                SiglipVisionModel(
                    config.image_size,
                    config.vision_patch_size,
                    config.vision_hidden_size,
                    config.vision_intermediate_size,
                    config.vision_num_layers,
                    config.vision_num_heads,
                )
            )
            self.multi_modal_projector = MultiModalProjector(
                config.vision_hidden_size,
                config.prefix_hidden_size,
            )
            self.language_model = GemmaLanguageModel(
                vocab_size=config.vocab_size,
                width=config.prefix_hidden_size,
                intermediate_size=config.prefix_intermediate_size,
                num_layers=config.prefix_num_layers,
                num_heads=config.prefix_num_heads,
                num_kv_heads=config.prefix_num_key_value_heads,
                head_dim=config.prefix_head_dim,
                epsilon=config.rms_norm_epsilon,
                rope_theta=config.rope_theta,
            )
            self._apply_tuning_plan()

    def _apply_tuning_plan(self) -> None:
        """把视觉和语言前缀的 ``requires_grad`` 精确投影到配置。"""

        if self.vision_tower is not None:
            for parameter in self.vision_tower.parameters():
                parameter.requires_grad_(self.config.tune_vision_encoder)
        language_modules = (
            self.multi_modal_projector,
            self.language_model,
        )
        for module in language_modules:
            if module is not None:
                for parameter in module.parameters():
                    parameter.requires_grad_(self.config.tune_language_prefix)

    def gradient_checkpointing_enable(self) -> None:
        """启用视觉和语言前缀的非重入 gradient checkpointing。"""

        self.gradient_checkpointing = True
        if self.vision_tower is not None:
            self.vision_tower.gradient_checkpointing = True

    def gradient_checkpointing_disable(self) -> None:
        """关闭视觉和语言前缀 gradient checkpointing。"""

        self.gradient_checkpointing = False
        if self.vision_tower is not None:
            self.vision_tower.gradient_checkpointing = False

    def _require_modules(
        self,
    ) -> tuple[SiglipVisionTower, MultiModalProjector, GemmaLanguageModel]:
        """返回完整生产模块，拒绝 compatibility-only 实例进入 forward。"""

        values = (
            self.vision_tower,
            self.multi_modal_projector,
            self.language_model,
        )
        if any(value is None for value in values):
            raise RuntimeError("Pi0.5 production backbone requires build_modules=True")
        return cast(
            tuple[SiglipVisionTower, MultiModalProjector, GemmaLanguageModel],
            values,
        )

    def forward(self, batch: ModelInputBatch) -> BackboneOutput:
        """生成图像优先、prompt/state 其后的前缀特征、mask 和位置。"""

        vision, projection, language_model = self._require_modules()
        if batch.camera_order != tuple(batch.images) or batch.camera_order != (
            "base_0_rgb",
            "left_wrist_0_rgb",
            "right_wrist_0_rgb",
        ):
            raise ValueError("Pi0.5 input cameras must use the canonical ordered triple")
        raw_image_masks = batch.metadata.get("image_masks")
        if not torch.is_tensor(raw_image_masks):
            raise TypeError("Pi0.5 ModelInputBatch metadata requires image_masks tensor")
        image_masks = cast(torch.Tensor, raw_image_masks)
        if image_masks.dtype != torch.bool or image_masks.shape != (batch.batch_size, 3):
            raise TypeError("image_masks must use strict bool[B,3]")
        # 三相机沿 batch 轴合并为一次视觉塔调用，避免三个串行 GPU kernel 链。
        pixels = torch.cat(tuple(batch.images[name] for name in batch.camera_order), dim=0)
        encoded = projection(vision(pixels))
        token_count = encoded.shape[1]
        encoded = encoded.view(3, batch.batch_size, token_count, -1).transpose(0, 1)
        visual = encoded.reshape(batch.batch_size, 3 * token_count, -1)
        visual_mask = (
            image_masks[:, :, None]
            .expand(-1, -1, token_count)
            .reshape(batch.batch_size, 3 * token_count)
        )
        tokens = language_model.embed_tokens(batch.input_ids)
        tokens = tokens * math.sqrt(self.config.prefix_hidden_size)
        hidden = torch.cat((visual, tokens), dim=1)
        valid_mask = torch.cat((visual_mask, batch.attention_mask), dim=1)
        positions = self.position_ids_torch(valid_mask)
        attention = valid_mask[:, :, None] & valid_mask[:, None, :]
        layer_cache: list[torch.Tensor] = []
        for layer in language_model.layers:
            if self.gradient_checkpointing and self.training:
                hidden, key, value = checkpoint(
                    layer,
                    hidden,
                    positions,
                    attention,
                    use_reentrant=False,
                )
            else:
                hidden, key, value = layer(hidden, positions, attention)
            layer_cache.extend((key, value))
        hidden = language_model.norm(hidden)
        image_sequence_mask = torch.cat(
            (visual_mask, torch.zeros_like(batch.attention_mask)), dim=1
        )
        return BackboneOutput(
            features=hidden,
            attention_mask=valid_mask,
            image_mask=image_sequence_mask,
            hidden_states=tuple(layer_cache),
        )

    @staticmethod
    def position_ids_torch(valid_mask: torch.Tensor) -> torch.Tensor:
        """生成有效 token 累计位置，padding 位置固定为零。"""

        if valid_mask.dtype != torch.bool or valid_mask.ndim != 2:
            raise TypeError("valid_mask must use strict bool[B,L]")
        positions = torch.clamp(valid_mask.long().cumsum(dim=1) - 1, min=0)
        return torch.where(valid_mask, positions, torch.zeros_like(positions))

    def build_prefix_cache(
        self,
        layer_keys: Sequence[object],
        layer_values: Sequence[object],
        prefix_mask: object,
    ) -> Mapping[str, object]:
        """兼容 M10：拥有 prefix K/V 与 mask，不允许 suffix 写回。"""

        if not layer_keys or len(layer_keys) != len(layer_values):
            raise ValueError("prefix cache requires equal non-empty K/V layer sequences")
        mask = np.asarray(prefix_mask)
        if mask.dtype != np.bool_ or mask.ndim != 2:
            raise TypeError("prefix_mask must use strict bool [B,P]")
        keys = tuple(_freeze_value(item) for item in layer_keys)
        values = tuple(_freeze_value(item) for item in layer_values)
        if any(_shape(key) != _shape(value) for key, value in zip(keys, values, strict=True)):
            raise ValueError("every prefix K/V pair must have equal shape")
        if any(_shape(key)[0] != mask.shape[0] or _shape(key)[-2] != mask.shape[1] for key in keys):
            raise ValueError("prefix K/V batch and sequence axes must match prefix_mask")
        owned_mask = np.array(mask, copy=True)
        owned_mask.setflags(write=False)
        identity = hashlib.sha256(
            repr((tuple(_shape(item) for item in keys), owned_mask.tolist())).encode()
        ).hexdigest()
        return MappingProxyType(
            {"keys": keys, "values": values, "mask": owned_mask, "fingerprint": identity}
        )

    def joint_attention_inputs(
        self,
        prefix_cache: Mapping[str, object],
        suffix_keys: Sequence[object],
        suffix_values: Sequence[object],
    ) -> tuple[tuple[object, ...], tuple[object, ...]]:
        """兼容 M10：拼接当前 suffix，但保持 prefix cache 自身不变。"""

        prefix_keys = cast(tuple[object, ...], prefix_cache["keys"])
        prefix_values = cast(tuple[object, ...], prefix_cache["values"])
        if len(suffix_keys) != len(prefix_keys) or len(suffix_values) != len(prefix_values):
            raise ValueError("suffix K/V layer count must match immutable prefix cache")
        return (
            tuple(
                self._concatenate(prefix, suffix)
                for prefix, suffix in zip(prefix_keys, suffix_keys, strict=True)
            ),
            tuple(
                self._concatenate(prefix, suffix)
                for prefix, suffix in zip(prefix_values, suffix_values, strict=True)
            ),
        )

    @staticmethod
    def _concatenate(prefix: object, suffix: object) -> object:
        """沿序列轴拼接同类 NumPy 或 Torch 张量。"""

        if isinstance(prefix, np.ndarray) and isinstance(suffix, np.ndarray):
            if prefix.shape[:-2] + prefix.shape[-1:] != suffix.shape[:-2] + suffix.shape[-1:]:
                raise ValueError("prefix and suffix cache shapes are incompatible")
            return np.concatenate((prefix, suffix), axis=-2)
        if not torch.is_tensor(prefix) or not torch.is_tensor(suffix):
            raise TypeError("prefix and suffix cache values must share one tensor backend")
        return torch.cat((prefix, suffix), dim=-2)

    @staticmethod
    def build_block_attention_mask(prefix_mask: object, suffix_mask: object) -> NDArray[np.bool_]:
        """构造 prefix 不看 suffix、suffix 可看全部有效上下文的 mask。"""

        prefix = np.asarray(prefix_mask)
        suffix = np.asarray(suffix_mask)
        if prefix.dtype != np.bool_ or suffix.dtype != np.bool_:
            raise TypeError("attention masks must use strict bool dtype")
        if prefix.ndim != 2 or suffix.ndim != 2 or prefix.shape[0] != suffix.shape[0]:
            raise ValueError("attention masks must use [B,L] with equal batch size")
        batch, prefix_length = prefix.shape
        suffix_length = suffix.shape[1]
        output = np.zeros(
            (batch, prefix_length + suffix_length, prefix_length + suffix_length),
            dtype=np.bool_,
        )
        output[:, :prefix_length, :prefix_length] = prefix[:, :, None] & prefix[:, None, :]
        all_keys = np.concatenate((prefix, suffix), axis=1)
        output[:, prefix_length:, :] = suffix[:, :, None] & all_keys[:, None, :]
        return output

    @staticmethod
    def position_ids(valid_mask: object) -> NDArray[np.int64]:
        """兼容 M10：生成 NumPy 累计有效位置。"""

        mask = np.asarray(valid_mask)
        if mask.dtype != np.bool_ or mask.ndim != 2:
            raise TypeError("valid_mask must use strict bool [B,L]")
        positions = np.maximum(np.cumsum(mask, axis=1, dtype=np.int64) - 1, 0)
        return np.where(mask, positions, 0)


__all__ = ["Pi05VisionLanguageBackbone"]
