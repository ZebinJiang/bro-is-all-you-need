"""Pi0.5 联合 prefix/expert 注意力与显式所有权 prefix cache 契约。

设计参考: OpenPI@15a9616a00943ada6c20a0f158e3adb39df2ccac,Apache-2.0。
用途: 以 AutoVLA 自有边界表达联合执行;风险: 尚无官方权重数值对齐证据。
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from importlib import import_module
from types import MappingProxyType
from typing import cast

import numpy as np

from autovla.models.families.pi0_5.config import Pi05Config


def _freeze_value(value: object) -> object:
    """复制数组或张量;NumPy 副本只读,注入后端副本保持其原生可变性。"""

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


class Pi05VisionLanguageBackbone:
    """保存自有前缀塔并提供不会把 suffix K/V 写回的联合注意力输入。"""

    def __init__(self, config: Pi05Config, prefix_tower: object | None = None) -> None:
        """绑定显式前缀塔;本构造不下载、补丁或推断模型家族。"""

        self.config = config
        self.prefix_tower = prefix_tower

    def build_prefix_cache(
        self,
        layer_keys: Sequence[object],
        layer_values: Sequence[object],
        prefix_mask: object,
    ) -> Mapping[str, object]:
        """拥有 prefix K/V 与 mask;NumPy 值只读,注入张量值仅保证无源别名。"""

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
        """拼接 prefix/suffix 供当前步读取,但绝不改写 prefix cache。"""

        prefix_keys = cast(tuple[object, ...], prefix_cache["keys"])
        prefix_values = cast(tuple[object, ...], prefix_cache["values"])
        if len(suffix_keys) != len(prefix_keys) or len(suffix_values) != len(prefix_values):
            raise ValueError("suffix K/V layer count must match immutable prefix cache")
        combined_keys = tuple(
            self._concatenate(prefix, suffix)
            for prefix, suffix in zip(prefix_keys, suffix_keys, strict=True)
        )
        combined_values = tuple(
            self._concatenate(prefix, suffix)
            for prefix, suffix in zip(prefix_values, suffix_values, strict=True)
        )
        return combined_keys, combined_values

    @staticmethod
    def _concatenate(prefix: object, suffix: object) -> object:
        """在序列轴拼接同类数组或 Torch 张量。"""

        if isinstance(prefix, np.ndarray) and isinstance(suffix, np.ndarray):
            if prefix.shape[:-2] + prefix.shape[-1:] != suffix.shape[:-2] + suffix.shape[-1:]:
                raise ValueError("prefix and suffix cache shapes are incompatible")
            return np.concatenate((prefix, suffix), axis=-2)
        torch = import_module("torch")
        if not bool(torch.is_tensor(prefix)) or not bool(torch.is_tensor(suffix)):
            raise TypeError("prefix and suffix cache values must share one tensor backend")
        return torch.cat((prefix, suffix), dim=-2)

    @staticmethod
    def build_block_attention_mask(prefix_mask: object, suffix_mask: object) -> np.ndarray:
        """构造 prefix 不看 suffix、suffix 可看完整有效上下文的 ``[B,L,L]`` mask。"""

        prefix = np.asarray(prefix_mask)
        suffix = np.asarray(suffix_mask)
        if prefix.dtype != np.bool_ or suffix.dtype != np.bool_:
            raise TypeError("attention masks must use strict bool dtype")
        if prefix.ndim != 2 or suffix.ndim != 2 or prefix.shape[0] != suffix.shape[0]:
            raise ValueError("attention masks must use [B,L] with equal batch size")
        batch, prefix_length = prefix.shape
        suffix_length = suffix.shape[1]
        output = np.zeros(
            (batch, prefix_length + suffix_length, prefix_length + suffix_length), dtype=np.bool_
        )
        output[:, :prefix_length, :prefix_length] = prefix[:, :, None] & prefix[:, None, :]
        all_keys = np.concatenate((prefix, suffix), axis=1)
        output[:, prefix_length:, :] = suffix[:, :, None] & all_keys[:, None, :]
        return output

    @staticmethod
    def position_ids(valid_mask: object) -> np.ndarray:
        """以累计有效 token 数减一生成位置,padding 位置保持零。"""

        mask = np.asarray(valid_mask)
        if mask.dtype != np.bool_ or mask.ndim != 2:
            raise TypeError("valid_mask must use strict bool [B,L]")
        positions = np.maximum(np.cumsum(mask, axis=1, dtype=np.int64) - 1, 0)
        return np.where(mask, positions, 0)
