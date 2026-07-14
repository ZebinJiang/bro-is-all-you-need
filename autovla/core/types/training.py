"""AutoVLA 后端无关训练批契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import TypeAlias, cast

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


def _readonly_bool(value: object, *, name: str, shape: tuple[int, ...]) -> ActionMask:
    """校验任意形状的严格 bool 数组并返回只读副本。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError(f"{name} must use strict bool dtype")
    if array.shape != shape:
        raise ValueError(f"{name} shape must be {shape}, got {array.shape}")
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


def _pickle_owned(value: object) -> object:
    """递归复制 mapping/sequence 容器,排除嵌套只读代理。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {key: _pickle_owned(item) for key, item in mapping.items()}
    if isinstance(value, tuple):
        values = cast(tuple[object, ...], value)
        return tuple(_pickle_owned(item) for item in values)
    if isinstance(value, list):
        values = cast(list[object], value)
        return [_pickle_owned(item) for item in values]
    return value


@dataclass(frozen=True, slots=True)
class TrainingSample:
    """保存后端中立的单条训练样本。

    动作与严格布尔有效掩码使用 ``[H,D]``。store/source/schema、数据集
    manifest 和物理/逻辑来源各自保留,不包含模型族专用 tensor 或 tokenizer 状态。
    """

    images: Mapping[str, NumericArray]
    language: str
    actions: NumericArray
    action_mask: ActionMask
    sample_source: SampleSource
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    state: NumericArray | None = None
    embodiment: str | None = None
    timestamps: NumericArray | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)
    source_fingerprint: str | None = None
    schema_fingerprint: str | None = None
    dataset_manifest_fingerprint: str | None = None
    store_fingerprint: str | None = None

    def __post_init__(self) -> None:
        """校验形状、文本、来源和指纹并冻结拥有值。"""
        actions = _readonly_numeric(self.actions, name="actions", ndim=2)
        if min(actions.shape) <= 0:
            raise ValueError("actions must have positive [H,D] shape")
        action_mask = _readonly_bool(
            self.action_mask,
            name="action_mask",
            shape=actions.shape,
        )
        if not self.images:
            raise ValueError("images must not be empty")
        images: dict[str, NumericArray] = {}
        for key, value in self.images.items():
            key_text = str(key)
            _require_non_empty(key_text, "image key")
            images[key_text] = _readonly_numeric(value, name=f"images.{key_text}")
        state = None
        if self.state is not None:
            state = _readonly_numeric(self.state, name="state", ndim=1)
        timestamps = None
        if self.timestamps is not None:
            timestamps = _readonly_numeric(self.timestamps, name="timestamps")
            if timestamps.ndim > 1:
                raise ValueError("timestamps must be a scalar or 1-D vector")
        _require_non_empty(self.language, "language")
        for name in (
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _require_non_empty(getattr(self, name), name)
        for name in (
            "source_fingerprint",
            "schema_fingerprint",
            "dataset_manifest_fingerprint",
            "store_fingerprint",
        ):
            value = getattr(self, name)
            if value is not None:
                _require_non_empty(value, name)
        if self.embodiment is not None:
            _require_non_empty(self.embodiment, "embodiment")
        object.__setattr__(self, "images", MappingProxyType(images))
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "action_mask", action_mask)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(
            self,
            "sample_source",
            _readonly_metadata(self.sample_source, name="sample_source"),
        )
        object.__setattr__(self, "metadata", _readonly_metadata(self.metadata, name="metadata"))
        object.__setattr__(
            self,
            "store_fingerprint",
            self.store_fingerprint or self.dataset_fingerprint,
        )

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """用拥有的普通映射重建,避免 worker 队列序列化 mappingproxy。"""
        return (
            type(self),
            (
                _pickle_owned(self.images),
                self.language,
                self.actions,
                self.action_mask,
                _pickle_owned(self.sample_source),
                self.dataset_fingerprint,
                self.transform_fingerprint,
                self.statistics_fingerprint,
                self.state,
                self.embodiment,
                self.timestamps,
                _pickle_owned(self.metadata),
                self.source_fingerprint,
                self.schema_fingerprint,
                self.dataset_manifest_fingerprint,
                self.store_fingerprint,
            ),
        )


@dataclass(frozen=True, slots=True)
class TrainingBatch:
    """保存模型族无关的 batch-major 数值训练批。

    输入图像按相机名保存,动作和严格布尔掩码形状均为 ``[B,H,D]``。
    store/source/schema 指纹和来源映射按样本顺序保存;旧 scalar 指纹仅作为
    dataset manifest 指纹的兼容别名。
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
    embodiment: tuple[str, ...] | None = None
    timestamps: NumericArray | None = None
    dataset_manifest_fingerprint: str | None = None
    store_fingerprints: tuple[str, ...] = ()
    source_fingerprints: tuple[str, ...] = ()
    schema_fingerprints: tuple[str, ...] = ()

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
        embodiment = None
        if self.embodiment is not None:
            if len(self.embodiment) != batch_size:
                raise ValueError("embodiment length must match batch size")
            embodiment_values: list[str] = []
            for index, value in enumerate(self.embodiment):
                _require_non_empty(value, f"embodiment[{index}]")
                embodiment_values.append(value)
            embodiment = tuple(embodiment_values)
        timestamps = None
        if self.timestamps is not None:
            timestamps = _readonly_numeric(self.timestamps, name="timestamps")
            if timestamps.shape[0] != batch_size:
                raise ValueError("timestamps first dimension must match batch size")
        for field_name in (
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _require_non_empty(getattr(self, field_name), field_name)
        manifest_fingerprint = self.dataset_manifest_fingerprint or self.dataset_fingerprint
        _require_non_empty(manifest_fingerprint, "dataset_manifest_fingerprint")
        if manifest_fingerprint != self.dataset_fingerprint:
            raise ValueError(
                "dataset_fingerprint compatibility alias must equal dataset_manifest_fingerprint"
            )
        ordered_fingerprints: dict[str, tuple[str, ...]] = {}
        for field_name in (
            "store_fingerprints",
            "source_fingerprints",
            "schema_fingerprints",
        ):
            values = tuple(getattr(self, field_name))
            if values and len(values) != batch_size:
                raise ValueError(f"{field_name} length must match batch size")
            for index, value in enumerate(values):
                _require_non_empty(value, f"{field_name}[{index}]")
            ordered_fingerprints[field_name] = values

        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "action_mask", action_mask)
        object.__setattr__(self, "sample_source", sample_source)
        object.__setattr__(self, "images", MappingProxyType(images))
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "metadata", _readonly_metadata(self.metadata, name="metadata"))
        object.__setattr__(self, "embodiment", embodiment)
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(
            self,
            "dataset_manifest_fingerprint",
            manifest_fingerprint,
        )
        for field_name, values in ordered_fingerprints.items():
            object.__setattr__(self, field_name, values)

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

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """用拥有的普通映射重建,保持不可变接口且支持 spawn 结果队列。"""
        return (
            type(self),
            (
                _pickle_owned(self.images),
                self.language,
                self.actions,
                self.action_mask,
                _pickle_owned(self.sample_source),
                self.dataset_fingerprint,
                self.transform_fingerprint,
                self.statistics_fingerprint,
                self.state,
                _pickle_owned(self.metadata),
                self.embodiment,
                self.timestamps,
                self.dataset_manifest_fingerprint,
                self.store_fingerprints,
                self.source_fingerprints,
                self.schema_fingerprints,
            ),
        )


__all__ = ["NumericArray", "SampleSource", "TrainingBatch", "TrainingSample"]
