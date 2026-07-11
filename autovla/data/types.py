"""AutoVLA 规范数据类型。"""

from __future__ import annotations

import hashlib
import json
from abc import abstractmethod
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, ClassVar, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from autovla.core.types.training import TrainingBatch

NumericArray = NDArray[Any]
BoolArray = NDArray[np.bool_]


def _empty_metadata() -> Mapping[str, object]:
    """返回类型明确的空元数据。"""
    return {}


def _owned_numeric(value: object, *, name: str) -> NumericArray:
    """拥有并冻结有限数值数组。"""
    array = np.asarray(value)
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    if not bool(np.isfinite(array).all()):
        raise ValueError(f"{name} must be finite")
    owned = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


def _owned_bool(value: object, *, name: str, shape: tuple[int, ...]) -> BoolArray:
    """拥有并冻结严格布尔数组。"""
    array = np.asarray(value)
    if array.dtype != np.dtype(np.bool_):
        raise TypeError(f"{name} must use strict bool dtype")
    if array.shape != shape:
        raise ValueError(f"{name} shape must be {shape}, got {array.shape}")
    owned = np.array(array, dtype=np.bool_, copy=True)
    owned.setflags(write=False)
    return owned


def _non_empty(value: object, name: str) -> str:
    """校验稳定非空文本。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must not be empty")
    return value


class DataStage(str, Enum):
    """标识 DataModule 当前准备阶段。"""

    FIT = "fit"
    TRAIN = "train"
    VALIDATE = "validate"
    PREDICT = "predict"


@dataclass(frozen=True, slots=True)
class TrainingSample:
    """保存单条后端中立训练样本。

    动作和掩码使用 ``[H,D]``,图像按相机名保存。样本构造时复制数组,
    以阻止后端缓冲区复用修改已交付数据。
    """

    images: Mapping[str, NumericArray]
    language: str
    actions: NumericArray
    action_mask: BoolArray
    sample_source: Mapping[str, object]
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    state: NumericArray | None = None
    embodiment: str | None = None
    timestamps: NumericArray | None = None
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验数组形状、来源和指纹。"""
        actions = _owned_numeric(self.actions, name="actions")
        if actions.ndim != 2 or min(actions.shape) <= 0:
            raise ValueError("actions must have positive [H,D] shape")
        mask = _owned_bool(self.action_mask, name="action_mask", shape=actions.shape)
        if not self.images:
            raise ValueError("images must not be empty")
        images: dict[str, NumericArray] = {}
        for key, value in self.images.items():
            images[_non_empty(str(key), "image key")] = _owned_numeric(value, name=f"images.{key}")
        state = None if self.state is None else _owned_numeric(self.state, name="state")
        if state is not None and state.ndim != 1:
            raise ValueError("state must be a 1-D vector")
        timestamps = (
            None if self.timestamps is None else _owned_numeric(self.timestamps, name="timestamps")
        )
        if timestamps is not None and timestamps.ndim > 1:
            raise ValueError("timestamps must be a scalar or 1-D vector")
        _non_empty(self.language, "language")
        for field_name in (
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
        ):
            _non_empty(getattr(self, field_name), field_name)
        if self.embodiment is not None:
            _non_empty(self.embodiment, "embodiment")
        object.__setattr__(self, "images", MappingProxyType(images))
        object.__setattr__(self, "actions", actions)
        object.__setattr__(self, "action_mask", mask)
        object.__setattr__(self, "state", state)
        object.__setattr__(self, "timestamps", timestamps)
        object.__setattr__(self, "sample_source", MappingProxyType(dict(self.sample_source)))
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))


@dataclass(frozen=True, slots=True)
class DatasetManifest:
    """描述 DataModule 已解析的本地数据集集合与兼容性。"""

    datasets: tuple[str, ...]
    backends: tuple[str, ...]
    splits: tuple[str, ...]
    sample_counts: tuple[int | None, ...]
    weights: tuple[float, ...]
    embodiments: tuple[str | None, ...]
    mix_strategy: str
    mix_seed: int
    balance_by: str
    loader_batch_size: int
    loader_drop_last: bool
    schema_version: str = "autovla.dataset_manifest.v2"
    transform_fingerprint: str = "identity"
    statistics_fingerprint: str = "identity"
    metadata: Mapping[str, object] = field(default_factory=_empty_metadata)

    def __post_init__(self) -> None:
        """校验各数据集字段长度和身份唯一性。"""
        length = len(self.datasets)
        if length == 0:
            raise ValueError("manifest.datasets must not be empty")
        if len(set(self.datasets)) != length:
            raise ValueError("manifest.datasets must be unique")
        if any(
            len(values) != length
            for values in (
                self.backends,
                self.splits,
                self.sample_counts,
                self.weights,
                self.embodiments,
            )
        ):
            raise ValueError("manifest dataset fields must have equal length")
        for value in (*self.datasets, *self.backends, *self.splits, self.schema_version):
            _non_empty(value, "manifest value")
        if any(weight <= 0.0 for weight in self.weights):
            raise ValueError("manifest weights must be positive")
        if self.mix_strategy not in {"weighted", "balanced"}:
            raise ValueError("manifest mix_strategy is invalid")
        if self.balance_by not in {"dataset", "embodiment"}:
            raise ValueError("manifest balance_by is invalid")
        _strict_int(self.mix_seed, "manifest.mix_seed")
        _strict_int(self.loader_batch_size, "manifest.loader_batch_size", minimum=1)
        _strict_bool(self.loader_drop_last, "manifest.loader_drop_last")
        object.__setattr__(self, "metadata", MappingProxyType(dict(self.metadata)))

    @property
    def fingerprint(self) -> str:
        """返回不包含物理路径的稳定 manifest 指纹。"""
        payload = {
            "backends": self.backends,
            "datasets": self.datasets,
            "embodiments": self.embodiments,
            "balance_by": self.balance_by,
            "loader_batch_size": self.loader_batch_size,
            "loader_drop_last": self.loader_drop_last,
            "mix_seed": self.mix_seed,
            "mix_strategy": self.mix_strategy,
            "sample_counts": self.sample_counts,
            "schema_version": self.schema_version,
            "splits": self.splits,
            "statistics_fingerprint": self.statistics_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
            "weights": self.weights,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


class DataLoaderProtocol(Protocol):
    """定义不依赖具体框架的批加载器边界。"""

    @abstractmethod
    def __iter__(self) -> Iterator[TrainingBatch]:
        """返回规范训练批迭代器。"""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """返回当前 epoch 的批次数。"""
        raise NotImplementedError


class CheckpointableDataLoaderProtocol(DataLoaderProtocol, Protocol):
    """在基础迭代边界上增加确定性恢复契约。"""

    @abstractmethod
    def state_dict(self) -> Mapping[str, object]:
        """导出下一条未读数据的位置。"""
        raise NotImplementedError

    @abstractmethod
    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """严格恢复下一条未读数据的位置。"""
        raise NotImplementedError


def _strict_fields(payload: Mapping[str, object], expected: set[str], name: str) -> None:
    """要求映射字段集合与 schema 完全一致。"""

    actual = set(payload)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise ValueError(f"{name} fields mismatch: missing={missing}, unknown={unknown}")


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """读取排除布尔值的有界整数。"""

    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _strict_bool(value: object, name: str) -> bool:
    """读取严格布尔值并拒绝其他真值对象。"""

    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool")
    return value


def _strict_text(value: object, name: str) -> str:
    """读取严格非空文本。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _cursor_mapping(value: object, name: str) -> Mapping[str, int]:
    """复制并冻结非空数据集游标映射。"""

    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    raw = cast(Mapping[object, object], value)
    if not raw:
        raise ValueError(f"{name} must not be empty")
    cursors: dict[str, int] = {}
    for key, cursor in raw.items():
        if not isinstance(key, str) or not key.strip() or key in cursors:
            raise ValueError(f"{name} dataset names must be unique non-empty strings")
        cursors[key] = _strict_int(cursor, f"{name}.{key}")
    return MappingProxyType(cursors)


@dataclass(frozen=True, slots=True)
class DataLoaderState:
    """保存加载器下一条未读批次的不可变确定性状态。"""

    SCHEMA_VERSION: ClassVar[str] = "autovla.data_loader_state.v1"

    schema_version: str
    manifest_fingerprint: str
    mix_strategy: str
    selection_epoch: int
    next_batch_index: int
    next_local_position: int
    rank: int
    world_size: int
    worker_id: int
    worker_count: int
    mixer_cursors: Mapping[str, int]
    balanced_cursors: Mapping[str, int]

    def __post_init__(self) -> None:
        """校验 schema、计数器、分区拓扑与游标集合。"""

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("unsupported data loader state schema")
        _non_empty(self.manifest_fingerprint, "manifest_fingerprint")
        if self.mix_strategy not in {"weighted", "balanced"}:
            raise ValueError("mix_strategy must be weighted or balanced")
        for name in (
            "selection_epoch",
            "next_batch_index",
            "next_local_position",
            "rank",
            "worker_id",
        ):
            _strict_int(getattr(self, name), name)
        _strict_int(self.world_size, "world_size", minimum=1)
        _strict_int(self.worker_count, "worker_count", minimum=1)
        if self.rank >= self.world_size or self.worker_id >= self.worker_count:
            raise ValueError("data loader partition topology is invalid")
        mixer = _cursor_mapping(self.mixer_cursors, "mixer_cursors")
        balanced = _cursor_mapping(self.balanced_cursors, "balanced_cursors")
        if set(mixer) != set(balanced):
            raise ValueError("mixer and balanced cursor dataset names must match")
        object.__setattr__(self, "mixer_cursors", mixer)
        object.__setattr__(self, "balanced_cursors", balanced)

    def to_dict(self) -> dict[str, object]:
        """返回严格、可序列化的状态映射。"""

        return {
            "schema_version": self.schema_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "mix_strategy": self.mix_strategy,
            "selection_epoch": self.selection_epoch,
            "next_batch_index": self.next_batch_index,
            "next_local_position": self.next_local_position,
            "rank": self.rank,
            "world_size": self.world_size,
            "worker_id": self.worker_id,
            "worker_count": self.worker_count,
            "mixer_cursors": dict(self.mixer_cursors),
            "balanced_cursors": dict(self.balanced_cursors),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DataLoaderState":
        """从字段集合完全匹配的映射构造状态。"""

        expected = {
            "schema_version",
            "manifest_fingerprint",
            "mix_strategy",
            "selection_epoch",
            "next_batch_index",
            "next_local_position",
            "rank",
            "world_size",
            "worker_id",
            "worker_count",
            "mixer_cursors",
            "balanced_cursors",
        }
        _strict_fields(payload, expected, "data loader state")
        return cls(
            schema_version=_strict_text(payload["schema_version"], "schema_version"),
            manifest_fingerprint=_strict_text(
                payload["manifest_fingerprint"], "manifest_fingerprint"
            ),
            mix_strategy=_strict_text(payload["mix_strategy"], "mix_strategy"),
            selection_epoch=_strict_int(payload["selection_epoch"], "selection_epoch"),
            next_batch_index=_strict_int(payload["next_batch_index"], "next_batch_index"),
            next_local_position=_strict_int(payload["next_local_position"], "next_local_position"),
            rank=_strict_int(payload["rank"], "rank"),
            world_size=_strict_int(payload["world_size"], "world_size", minimum=1),
            worker_id=_strict_int(payload["worker_id"], "worker_id"),
            worker_count=_strict_int(payload["worker_count"], "worker_count", minimum=1),
            mixer_cursors=_cursor_mapping(payload["mixer_cursors"], "mixer_cursors"),
            balanced_cursors=_cursor_mapping(payload["balanced_cursors"], "balanced_cursors"),
        )


@dataclass(frozen=True, slots=True)
class DataModuleState:
    """保存 DataModule 阶段和两个可选加载器状态。"""

    SCHEMA_VERSION: ClassVar[str] = "autovla.data_module_state.v1"

    schema_version: str
    stage: DataStage
    manifest_fingerprint: str
    train_loader: DataLoaderState | None
    validation_loader: DataLoaderState | None

    def __post_init__(self) -> None:
        """校验模块 schema、阶段、指纹和加载器归属。"""

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("unsupported data module state schema")
        if not isinstance(cast(object, self.stage), DataStage):
            raise TypeError("stage must be a DataStage")
        _non_empty(self.manifest_fingerprint, "manifest_fingerprint")
        for loader in (self.train_loader, self.validation_loader):
            if loader is not None and not isinstance(cast(object, loader), DataLoaderState):
                raise TypeError("module loader state must be DataLoaderState or None")
            if loader is not None and loader.manifest_fingerprint != self.manifest_fingerprint:
                raise ValueError("loader and module manifest fingerprints differ")

    def to_dict(self) -> dict[str, object]:
        """返回严格、可序列化的模块状态。"""

        return {
            "schema_version": self.schema_version,
            "stage": self.stage.value,
            "manifest_fingerprint": self.manifest_fingerprint,
            "train_loader": None if self.train_loader is None else self.train_loader.to_dict(),
            "validation_loader": (
                None if self.validation_loader is None else self.validation_loader.to_dict()
            ),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DataModuleState":
        """严格解析模块状态及其嵌套加载器状态。"""

        _strict_fields(
            payload,
            {
                "schema_version",
                "stage",
                "manifest_fingerprint",
                "train_loader",
                "validation_loader",
            },
            "data module state",
        )

        def _loader(name: str) -> DataLoaderState | None:
            value = payload[name]
            if value is None:
                return None
            if not isinstance(value, Mapping):
                raise TypeError(f"{name} must be a mapping or None")
            return DataLoaderState.from_dict(cast(Mapping[str, object], value))

        try:
            stage = DataStage(_strict_text(payload["stage"], "stage"))
        except (TypeError, ValueError) as exc:
            raise ValueError("data module stage is invalid") from exc
        return cls(
            schema_version=_strict_text(payload["schema_version"], "schema_version"),
            stage=stage,
            manifest_fingerprint=_strict_text(
                payload["manifest_fingerprint"], "manifest_fingerprint"
            ),
            train_loader=_loader("train_loader"),
            validation_loader=_loader("validation_loader"),
        )


__all__ = [
    "CheckpointableDataLoaderProtocol",
    "DataLoaderProtocol",
    "DataLoaderState",
    "DataModuleState",
    "DataStage",
    "DatasetManifest",
    "NumericArray",
    "TrainingBatch",
    "TrainingSample",
]
