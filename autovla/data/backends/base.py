"""AutoVLA 数据后端基础契约和记录转换。"""

from __future__ import annotations

import hashlib
import json
from abc import abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from autovla.config.schema import DatasetConfig
from autovla.core.types.training import TrainingSample
from autovla.data.contracts import (
    DataAccessMode,
    DataSourceSpec,
    StreamPartitionState,
    WorkerContext,
)
from autovla.data.types import DataStage

if TYPE_CHECKING:
    from autovla.data.binding.adapter import DataBackendBindingAdapter

NumericArray = NDArray[Any]


class MapDataSource(Protocol):
    """定义有限整数索引、批读取和 worker-local 生命周期。"""

    @property
    @abstractmethod
    def spec(self) -> DataSourceSpec:
        """返回打开前后保持一致的源规格。"""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """返回确定性有限整数索引空间长度。"""
        raise NotImplementedError

    @abstractmethod
    def initialize_worker(self, context: WorkerContext) -> None:
        """在拥有该源的进程中安装 worker 上下文并打开缓存。"""
        raise NotImplementedError

    @abstractmethod
    def read(self, index: int) -> TrainingSample:
        """按整数索引读取一条规范样本。"""
        raise NotImplementedError

    @abstractmethod
    def read_many(self, indices: Sequence[int]) -> Sequence[TrainingSample]:
        """按请求顺序批读取样本。"""
        raise NotImplementedError

    @abstractmethod
    def state_dict(self) -> Mapping[str, object]:
        """返回 worker-local 可序列化源状态。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭 worker-local 文件、媒体或容器句柄。"""
        raise NotImplementedError


class StreamingDataSource(Protocol):
    """定义显式有限或重采样 streaming 源。

    ``iter_samples`` 必须只消费 ``state.assigned_units``;loader 已完成 rank
    和 worker 分区,后端及上游 splitter 不得再次切分。
    """

    @property
    @abstractmethod
    def spec(self) -> DataSourceSpec:
        """返回 streaming 模式和恢复能力规格。"""
        raise NotImplementedError

    @abstractmethod
    def initialize_worker(self, context: WorkerContext) -> None:
        """在 worker 中建立源缓存和处理器。"""
        raise NotImplementedError

    @abstractmethod
    def iter_samples(
        self,
        context: WorkerContext,
        state: StreamPartitionState,
    ) -> Iterator[TrainingSample]:
        """从下一条未读 stream 位置迭代规范样本。"""
        raise NotImplementedError

    @abstractmethod
    def state_dict(self) -> Mapping[str, object]:
        """返回当前 worker stream 状态。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭 worker-local pipeline 和媒体句柄。"""
        raise NotImplementedError


class DataBackend(Protocol):
    """定义源描述和 worker-local 打开边界。"""

    @abstractmethod
    def binding_adapter(self) -> "DataBackendBindingAdapter":
        """返回统一 production binding 收据适配器,不读取 payload。"""
        raise NotImplementedError

    @abstractmethod
    def describe_source(self, config: DatasetConfig, stage: DataStage) -> DataSourceSpec:
        """只读取轻量元数据并返回源规格,不得打开长期句柄。"""
        raise NotImplementedError

    @abstractmethod
    def describe_stream_partition_units(
        self,
        config: DatasetConfig,
        stage: DataStage,
    ) -> Sequence[str]:
        """迭代前返回真实 shard/source 单元身份,不得打开长期句柄。"""
        raise NotImplementedError

    @abstractmethod
    def open_source(
        self,
        config: DatasetConfig,
        stage: DataStage,
        context: WorkerContext,
    ) -> MapDataSource | StreamingDataSource:
        """在 worker 上下文中打开类型化生产源。"""
        raise NotImplementedError

    @abstractmethod
    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> object:
        """返回已弃用兼容句柄;实现必须委托给同一生产源。"""
        raise NotImplementedError


@dataclass(frozen=True, slots=True)
class DataBackendCapabilities:
    """记录打开数据前可检查的后端能力真值。"""

    sequential_streaming: bool
    random_access: bool
    persistent_index: bool
    grouped_reads: bool
    deterministic_partition: bool
    prototype_only: bool
    native_compatible: bool
    local_only: bool = True

    def supports(self, mode: DataAccessMode) -> bool:
        """返回后端是否声明支持给定访问模式。"""
        return self.random_access if mode is DataAccessMode.MAP else self.sequential_streaming


@dataclass(frozen=True, slots=True)
class DataBackendSpec:
    """绑定规范后端键、能力和懒工厂路径。"""

    key: str
    aliases: tuple[str, ...]
    capabilities: DataBackendCapabilities
    factory_path: str
    optional_extra: str | None = None
    required_modules: tuple[str, ...] = ()


def local_sample_count(root: Path, configured: int | None = None) -> int:
    """从显式配置或本地 JSONL 索引解析样本数量。"""
    if configured is not None:
        return configured
    index_path = root / "sample_index.jsonl"
    if not index_path.is_file():
        raise ValueError(f"local dataset index is missing: {index_path}")
    count = sum(1 for line in index_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if count <= 0:
        raise ValueError(f"local dataset index is empty: {index_path}")
    return count


def dataset_config_fingerprint(config: DatasetConfig) -> str:
    """计算不包含绝对物理路径的数据集配置指纹。"""
    payload = {
        "action_key": config.action_key,
        "action_mask_key": config.action_mask_key,
        "backend": config.backend,
        "embodiment": config.embodiment,
        "image_keys": config.image_keys,
        "language_key": config.language_key,
        "name": config.name,
        "sample_count": config.sample_count,
        "split": config.split,
        "state_key": config.state_key,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _materialize_images(
    record: Mapping[str, object], payload: Mapping[str, object], config: DatasetConfig
) -> dict[str, NumericArray]:
    """优先使用物化数组,否则仅从受根目录约束的 NPY 引用读取。"""
    materialized = record.get("images", {})
    if not isinstance(materialized, Mapping):
        raise ValueError("record.images must be a mapping")
    materialized_mapping = cast(Mapping[object, object], materialized)
    images: dict[str, NumericArray] = {
        str(name): np.asarray(value) for name, value in materialized_mapping.items()
    }
    if images:
        return images
    refs_value = payload.get("camera_refs")
    if not isinstance(refs_value, Sequence) or isinstance(refs_value, (str, bytes, bytearray)):
        raise ValueError("record must provide materialized images or local camera_refs")
    refs = cast(Sequence[object], refs_value)
    root = Path(config.root).resolve()
    names = config.image_keys or tuple(f"camera.rgb_{index}" for index in range(len(refs)))
    if len(names) != len(refs):
        raise ValueError("image_keys length must match camera_refs")
    for name, reference in zip(names, refs, strict=True):
        if not isinstance(reference, str):
            raise ValueError("camera_refs entries must be local path strings")
        path = Path(reference)
        path = path.resolve() if path.is_absolute() else (root / path).resolve()
        if path != root and root not in path.parents:
            raise ValueError("camera reference escapes dataset root")
        if path.suffix != ".npy" or not path.is_file():
            raise ValueError(
                f"camera {name!r} requires a materialized array or local NPY file: {path}"
            )
        images[name] = np.load(path, allow_pickle=False)
    return images


def record_to_training_sample(
    record: Mapping[str, object],
    *,
    config: DatasetConfig,
    transform_fingerprint: str = "identity",
    statistics_fingerprint: str = "identity",
) -> TrainingSample:
    """把现有 store 记录转换为规范样本并保留来源字段。"""
    payload_value = record.get("payload", record)
    if not isinstance(payload_value, Mapping):
        raise ValueError("dataset record payload must be a mapping")
    payload = cast(Mapping[str, object], payload_value)
    action = np.asarray(payload.get(config.action_key), dtype=np.float32)
    if action.ndim == 1:
        action = action[None, :]
    if action.ndim != 2:
        raise ValueError("action payload must have [D] or [H,D] shape")
    raw_mask = payload.get(config.action_mask_key)
    if raw_mask is None:
        action_mask = np.ones(action.shape, dtype=np.bool_)
    else:
        action_mask = np.asarray(raw_mask)
        if action_mask.ndim == 1:
            action_mask = action_mask[None, :]
        if action_mask.dtype != np.dtype(np.bool_):
            raise TypeError("action mask payload must retain strict bool dtype")
    language = payload.get(config.language_key)
    if not isinstance(language, str):
        raise ValueError(f"payload field {config.language_key!r} must be a string")
    source = {
        key: payload[key]
        for key in ("episode_id", "frame_index", "sample_id", "timestamp", "window_id")
        if key in payload
    }
    source.update({"backend": config.backend, "dataset": config.name, "split": config.split})
    timestamps = payload.get("timestamp")
    timestamp_array = None
    if timestamps is not None:
        timestamp_array = np.asarray(timestamps, dtype=np.float64)
        if timestamp_array.ndim == 0:
            timestamp_array = timestamp_array.reshape(1)
        if timestamp_array.ndim != 1:
            raise ValueError("timestamp payload must be a scalar or 1-D vector")
    state_value = payload.get(config.state_key)
    state = None if state_value is None else np.asarray(state_value, dtype=np.float32)
    return TrainingSample(
        images=_materialize_images(record, payload, config),
        language=language,
        actions=action,
        action_mask=action_mask,
        sample_source=source,
        dataset_fingerprint=dataset_config_fingerprint(config),
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
        state=state,
        embodiment=config.embodiment,
        timestamps=timestamp_array,
        metadata={"payload_hash": payload.get("payload_hash")},
    )


__all__ = [
    "DataBackend",
    "DataBackendCapabilities",
    "DataBackendSpec",
    "MapDataSource",
    "StreamingDataSource",
    "dataset_config_fingerprint",
    "local_sample_count",
    "record_to_training_sample",
]
