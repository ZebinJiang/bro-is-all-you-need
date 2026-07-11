"""AutoVLA 数据源和真实 DataLoader 运行配置。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from autovla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_choice,
    require_int,
    require_non_empty_str,
    require_number,
    require_positive_int,
    require_schema_version,
    require_str_tuple,
)

_MODULAR_BACKEND_ALIASES = {
    "robodm": "robodm_container_v1",
    "robodm_style": "robodm_container_v1",
    "zjh_robodm_container_v1": "robodm_container_v1",
    "webdataset": "webdataset_tar",
    "webdataset_native": "webdataset_tar",
    "zjh_webdataset_tar": "webdataset_tar",
}
_MODULAR_BACKEND_KEYS = frozenset({"robodm_container_v1", "webdataset_tar"})


@dataclass(frozen=True, slots=True)
class TemporalQueryConfig:
    """描述可序列化的时间特征查询配置。"""

    feature_key: str
    feature_family: str
    frame_offsets: tuple[int, ...] = ()
    timestamp_deltas: tuple[float, ...] = ()
    anchor_semantics: str = "sample"
    fps: float | None = None
    tolerance: float | None = None
    boundary_policy: str = "error"
    output_mask_semantics: str = "true_is_observed"
    action_horizon: int = 1

    def __post_init__(self) -> None:
        """校验坐标系、anchor、时间参数和 action horizon。"""
        require_non_empty_str(self.feature_key, "temporal_query.feature_key")
        require_non_empty_str(self.feature_family, "temporal_query.feature_family")
        frame_offsets = tuple(
            require_int(value, f"temporal_query.frame_offsets[{index}]")
            for index, value in enumerate(self.frame_offsets)
        )
        timestamp_deltas = tuple(
            require_number(value, f"temporal_query.timestamp_deltas[{index}]")
            for index, value in enumerate(self.timestamp_deltas)
        )
        if not frame_offsets and not timestamp_deltas:
            raise ValueError("temporal_query requires frame_offsets or timestamp_deltas")
        if len(set(frame_offsets)) != len(frame_offsets):
            raise ValueError("temporal_query.frame_offsets must be unique")
        if len(set(timestamp_deltas)) != len(timestamp_deltas):
            raise ValueError("temporal_query.timestamp_deltas must be unique")
        require_choice(
            self.anchor_semantics,
            "temporal_query.anchor_semantics",
            ("sample", "frame", "timestamp"),
        )
        if frame_offsets and timestamp_deltas and self.anchor_semantics != "sample":
            raise ValueError("mixed temporal coordinates require sample anchor semantics")
        if frame_offsets and not timestamp_deltas and self.anchor_semantics == "timestamp":
            raise ValueError("frame_offsets cannot use timestamp anchor semantics")
        if timestamp_deltas and not frame_offsets and self.anchor_semantics == "frame":
            raise ValueError("timestamp_deltas cannot use frame anchor semantics")
        require_choice(
            self.boundary_policy,
            "temporal_query.boundary_policy",
            ("pad", "clip", "error"),
        )
        require_choice(
            self.output_mask_semantics,
            "temporal_query.output_mask_semantics",
            ("true_is_observed", "true_is_padding"),
        )
        action_horizon = require_positive_int(
            self.action_horizon,
            "temporal_query.action_horizon",
        )
        fps = None if self.fps is None else require_number(self.fps, "temporal_query.fps")
        if fps is not None and fps <= 0:
            raise ValueError("temporal_query.fps must be positive")
        tolerance = (
            None
            if self.tolerance is None
            else require_number(self.tolerance, "temporal_query.tolerance")
        )
        if tolerance is not None and tolerance < 0:
            raise ValueError("temporal_query.tolerance must be non-negative")
        if frame_offsets and not timestamp_deltas and tolerance is not None:
            raise ValueError("frame_offsets cannot set timestamp tolerance")
        query_size = len(frame_offsets) + len(timestamp_deltas)
        if self.feature_family == "action" and query_size != action_horizon:
            raise ValueError("action temporal query size must equal action_horizon")
        object.__setattr__(self, "frame_offsets", frame_offsets)
        object.__setattr__(self, "timestamp_deltas", timestamp_deltas)
        object.__setattr__(self, "fps", fps)
        object.__setattr__(self, "tolerance", tolerance)

    def to_dict(self) -> dict[str, object]:
        """返回可直接转换为 canonical TemporalQuery 的稳定字段。"""
        return {
            "feature_key": self.feature_key,
            "feature_family": self.feature_family,
            "frame_offsets": list(self.frame_offsets),
            "timestamp_deltas": list(self.timestamp_deltas),
            "anchor_semantics": self.anchor_semantics,
            "fps": self.fps,
            "tolerance": self.tolerance,
            "boundary_policy": self.boundary_policy,
            "output_mask_semantics": self.output_mask_semantics,
            "action_horizon": self.action_horizon,
        }

    @property
    def fingerprint(self) -> str:
        """返回与全部查询字段绑定的确定性 SHA-256 指纹。"""
        encoded = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class DatasetConfig:
    """描述一个显式本地源及其访问和字段语义。"""

    name: str
    backend: str
    root: str
    split: str = "train"
    weight: float = 1.0
    embodiment: str | None = None
    sample_count: int | None = None
    image_keys: tuple[str, ...] = ()
    language_key: str = "language"
    state_key: str = "state"
    action_key: str = "action"
    action_mask_key: str = "action_mask"
    access_mode: str = "map"
    stream_mode: str | None = None
    nominal_epoch_size: int | None = None
    temporal_query: TemporalQueryConfig | None = None

    def __post_init__(self) -> None:
        """校验源身份、模式、长度和字段映射。"""
        for field_name in (
            "name",
            "backend",
            "root",
            "split",
            "language_key",
            "state_key",
            "action_key",
            "action_mask_key",
        ):
            require_non_empty_str(getattr(self, field_name), f"dataset.{field_name}")
        weight = require_number(self.weight, "dataset.weight")
        if weight <= 0.0:
            raise ValueError("dataset.weight must be positive")
        if self.embodiment is not None:
            require_non_empty_str(self.embodiment, "dataset.embodiment")
        if self.sample_count is not None:
            require_positive_int(self.sample_count, "dataset.sample_count")
        if self.image_keys:
            require_str_tuple(self.image_keys, "dataset.image_keys")
        if self.temporal_query is not None and not isinstance(
            self.temporal_query, TemporalQueryConfig
        ):
            raise TypeError("dataset.temporal_query must be TemporalQueryConfig or None")
        require_choice(self.access_mode, "dataset.access_mode", ("map", "streaming"))
        if self.access_mode == "map":
            if self.stream_mode is not None or self.nominal_epoch_size is not None:
                raise ValueError("map dataset cannot set stream_mode or nominal_epoch_size")
        else:
            if self.stream_mode is None:
                raise ValueError("streaming dataset requires stream_mode")
            require_choice(
                self.stream_mode,
                "dataset.stream_mode",
                ("finite_epoch", "resampled"),
            )
            if self.nominal_epoch_size is None:
                raise ValueError("streaming dataset requires nominal_epoch_size")
            require_positive_int(self.nominal_epoch_size, "dataset.nominal_epoch_size")


@dataclass(frozen=True, slots=True)
class DataLoaderConfig:
    """描述每个字段都由标准 Torch DataLoader 消费的运行参数。"""

    batch_size: int = 1
    num_workers: int = 0
    drop_last: bool = False
    pin_memory: bool = False
    persistent_workers: bool = False
    prefetch_factor: int | None = None
    timeout_seconds: float = 0.0
    multiprocessing_context: str | None = None
    worker_seed_policy: str = "stable_hash_v1"
    map_shuffle: bool = False
    stream_shard_shuffle: bool = False
    stream_sample_shuffle_buffer: int = 0
    exact_resume: bool = True
    partition_policy: str = "exact_no_pad"

    def __post_init__(self) -> None:
        """校验 worker-only 参数和可恢复采样语义。"""
        require_positive_int(self.batch_size, "data.loader.batch_size")
        workers = require_int(self.num_workers, "data.loader.num_workers")
        if workers < 0:
            raise ValueError("data.loader.num_workers must be non-negative")
        for name in (
            "drop_last",
            "pin_memory",
            "persistent_workers",
            "map_shuffle",
            "stream_shard_shuffle",
            "exact_resume",
        ):
            require_bool(getattr(self, name), f"data.loader.{name}")
        if self.pin_memory:
            raise ValueError(
                "data.loader.pin_memory is unsupported for the canonical NumPy-backed "
                "TrainingBatch; enable only after a storage-neutral pinning contract exists"
            )
        if self.prefetch_factor is not None:
            require_positive_int(self.prefetch_factor, "data.loader.prefetch_factor")
        timeout = require_number(self.timeout_seconds, "data.loader.timeout_seconds")
        if timeout < 0:
            raise ValueError("data.loader.timeout_seconds must be non-negative")
        require_choice(
            self.worker_seed_policy,
            "data.loader.worker_seed_policy",
            ("stable_hash_v1",),
        )
        buffer_size = require_int(
            self.stream_sample_shuffle_buffer,
            "data.loader.stream_sample_shuffle_buffer",
        )
        if buffer_size < 0:
            raise ValueError("data.loader.stream_sample_shuffle_buffer must be non-negative")
        require_choice(
            self.partition_policy,
            "data.loader.partition_policy",
            ("exact_no_pad", "drop_global_tail", "pad_repeat"),
        )
        if self.multiprocessing_context is not None:
            require_choice(
                self.multiprocessing_context,
                "data.loader.multiprocessing_context",
                ("spawn", "forkserver"),
            )
        if self.persistent_workers and workers == 0:
            raise ValueError("persistent_workers requires num_workers > 0")
        if self.prefetch_factor is not None and workers == 0:
            raise ValueError("prefetch_factor requires num_workers > 0")
        if timeout > 0 and workers == 0:
            raise ValueError("timeout_seconds requires num_workers > 0")
        if self.multiprocessing_context is not None and workers == 0:
            raise ValueError("multiprocessing_context requires num_workers > 0")


@dataclass(frozen=True, slots=True)
class DatasetMixConfig:
    """描述确定性数据集混合与批平衡策略。"""

    strategy: str = "weighted"
    seed: int = 0
    balance_by: str = "dataset"

    def __post_init__(self) -> None:
        """校验混合策略和基础随机种子。"""
        require_choice(self.strategy, "data.mix.strategy", ("weighted", "balanced"))
        seed = require_int(self.seed, "data.mix.seed")
        if seed < 0:
            raise ValueError("data.mix.seed must be non-negative")
        require_choice(self.balance_by, "data.mix.balance_by", ("dataset", "embodiment"))


@dataclass(frozen=True, slots=True)
class DataConfig(BaseConfig):
    """描述唯一访问模式的数据源、加载、混合和归一化选择。"""

    name: str = "local-debug-data"
    root: str = "datasets/working/local_debug"
    required_modalities: tuple[str, ...] = ("front",)
    backend: str | None = None
    datasets: tuple[DatasetConfig, ...] = ()
    loader: DataLoaderConfig = field(default_factory=DataLoaderConfig)
    mix: DatasetMixConfig = field(default_factory=DatasetMixConfig)
    normalization: str | None = None

    def __post_init__(self) -> None:
        """校验数据集唯一性、访问模式和跨字段组合。"""
        require_schema_version(self.schema_version, "data.schema_version")
        require_non_empty_str(self.name, "data.name")
        require_non_empty_str(self.root, "data.root")
        require_str_tuple(self.required_modalities, "data.required_modalities")
        if self.backend is not None:
            require_non_empty_str(self.backend, "data.backend")
            canonical_backend = _MODULAR_BACKEND_ALIASES.get(self.backend, self.backend)
            if canonical_backend not in _MODULAR_BACKEND_KEYS:
                choices = ", ".join(sorted(_MODULAR_BACKEND_KEYS))
                raise ValueError(
                    f"unknown data.backend {self.backend!r}; expected one of: {choices}"
                )
            object.__setattr__(self, "backend", canonical_backend)
        names = tuple(dataset.name for dataset in self.datasets)
        if len(set(names)) != len(names):
            raise ValueError("data.datasets names must be unique")
        modes = {dataset.access_mode for dataset in self.datasets}
        if len(modes) > 1:
            raise ValueError("mixed map and streaming datasets are unsupported")
        mode = next(iter(modes), "map")
        if mode == "map":
            if self.loader.stream_shard_shuffle or self.loader.stream_sample_shuffle_buffer:
                raise ValueError("map data cannot set streaming shuffle fields")
        else:
            if self.loader.map_shuffle:
                raise ValueError("streaming data cannot set map_shuffle")
            if self.loader.partition_policy != "exact_no_pad":
                raise ValueError("streaming data requires exact_no_pad partition policy")
            if self.loader.exact_resume and self.loader.stream_sample_shuffle_buffer:
                raise ValueError(
                    "exact streaming resume requires stream_sample_shuffle_buffer=0; "
                    "buffered sample shuffle is non-exact and is not serialized"
                )
        if self.normalization is not None:
            require_non_empty_str(self.normalization, "data.normalization")


__all__ = [
    "DataConfig",
    "DataLoaderConfig",
    "DatasetConfig",
    "DatasetMixConfig",
    "TemporalQueryConfig",
]
