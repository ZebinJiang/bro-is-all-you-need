"""AutoVLA 后端无关训练批契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias

import numpy as np

from autovla.core.types.action import ActionMask, NumericArray

SampleSource: TypeAlias = Mapping[str, object]


def _empty_metadata() -> dict[str, object]:
    """返回空元数据映射。"""
    return {}


def _readonly_numeric(value: object, *, name: str, ndim: int | None = None) -> NumericArray:
    """校验有限数值数组并返回只读副本。"""
    array = np.asarray(value)
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    if ndim is not None and array.ndim != ndim:
        raise ValueError(f"{name} must have rank {ndim}")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must be finite")
    owned: NumericArray = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


def _readonly_mask(value: object, *, shape: tuple[int, int, int]) -> ActionMask:
    """校验严格 bool action mask 并返回只读副本。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError("action_mask must be bool [B,H,D] without coercion")
    if array.shape != shape:
        raise ValueError(f"action_mask shape must be {shape}, got {array.shape}")
    owned: ActionMask = np.array(array, dtype=np.bool_, copy=True)
    owned.setflags(write=False)
    return owned


def _require_non_empty(value: str, name: str) -> None:
    """校验字符串非空。"""
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _readonly_metadata(value: Mapping[str, object], *, name: str) -> Mapping[str, object]:
    """复制并冻结字符串 key 元数据映射。"""
    frozen: dict[str, object] = {}
    for key, item in value.items():
        key_text = str(key)
        _require_non_empty(key_text, name)
        frozen[key_text] = item
    return MappingProxyType(frozen)


@dataclass(frozen=True, slots=True)
class TrainingBatch:
    """保存模型族无关的 batch-major 数值训练批。

    输入图像按相机名保存,动作和严格布尔掩码形状均为 ``[B,H,D]``。
    构造后数组与来源元数据均由该对象拥有并设为只读。
    """

    images: Mapping[str, NumericArray]
    language: tuple[str, ...]
    actions: NumericArray
    action_mask: ActionMask
    sample_source: tuple[SampleSource, ...]
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    state: NumericArray | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验形状、指纹和只读拥有语义。"""
        actions = _readonly_numeric(self.actions, name="actions", ndim=3)
        batch_size, action_horizon, action_dim = actions.shape
        if batch_size <= 0 or action_horizon <= 0 or action_dim <= 0:
            raise ValueError("actions must have positive [B,H,D] shape")
        action_mask = _readonly_mask(
            self.action_mask,
            shape=(batch_size, action_horizon, action_dim),
        )
        if len(self.language) != batch_size:
            raise ValueError("language length must match batch size")
        for index, text in enumerate(self.language):
            _require_non_empty(text, f"language[{index}]")
        if len(self.sample_source) != batch_size:
            raise ValueError("sample_source length must match batch size")
        sample_source = tuple(
            _readonly_metadata(source, name=f"sample_source[{index}]")
            for index, source in enumerate(self.sample_source)
        )
        if not self.images:
            raise ValueError("images must not be empty")
        images: dict[str, NumericArray] = {}
        for name, value in self.images.items():
            _require_non_empty(str(name), "image key")
            image = _readonly_numeric(value, name=f"images.{name}")
            if image.shape[0] != batch_size:
                raise ValueError(f"images.{name} first dimension must match batch size")
            images[str(name)] = image
        state = None
        if self.state is not None:
            state = _readonly_numeric(self.state, name="state")
            if state.shape[0] != batch_size:
                raise ValueError("state first dimension must match batch size")
        for field_name in (
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _require_non_empty(getattr(self, field_name), field_name)

        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "action_mask", action_mask)
        object.__setattr__(self, "sample_source", sample_source)
        object.__setattr__(self, "images", MappingProxyType(images))
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "metadata", _readonly_metadata(self.metadata, name="metadata"))

    @property
    def batch_size(self) -> int:
        """返回批大小。"""
        return int(self.actions.shape[0])

    @property
    def action_horizon(self) -> int:
        """返回动作 horizon。"""
        return int(self.actions.shape[1])

    @property
    def action_dim(self) -> int:
        """返回动作维度。"""
        return int(self.actions.shape[2])


__all__ = ["SampleSource", "TrainingBatch"]
