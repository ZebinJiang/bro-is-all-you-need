"""AutoVLA 数据后端基础契约和记录转换。"""

from __future__ import annotations

import hashlib
import json
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, cast

import numpy as np
from numpy.typing import NDArray

from autovla.config.schema import DatasetConfig
from autovla.data.datasets.base import DatasetHandle
from autovla.data.types import DataStage, TrainingSample

NumericArray = NDArray[Any]


class DataBackend(Protocol):
    """定义一个显式本地数据后端。"""

    @abstractmethod
    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> DatasetHandle:
        """打开配置指定的数据集并返回有界句柄。"""
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
    timestamp_array = None if timestamps is None else np.asarray([timestamps], dtype=np.float64)
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
    "dataset_config_fingerprint",
    "local_sample_count",
    "record_to_training_sample",
]
