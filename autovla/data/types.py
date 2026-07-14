"""AutoVLA 数据状态类型;TrainingSample 仅保留弃用身份别名。"""

from __future__ import annotations

import hashlib
import json
from abc import abstractmethod
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import ClassVar, Protocol, cast

from autovla.core.types.training import NumericArray, TrainingBatch, TrainingSample


def _empty_metadata() -> Mapping[str, object]:
    """返回类型明确的空元数据。"""
    return {}


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
class DatasetManifest:
    """描述 DataModule 已解析的本地数据集集合与兼容性。"""

    datasets: tuple[str, ...]
    backends: tuple[str, ...]
    splits: tuple[str, ...]
    sample_counts: tuple[int | None, ...]
    source_fingerprints: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    temporal_query_fingerprints: tuple[str, ...]
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
                self.source_fingerprints,
                self.schema_fingerprints,
                self.temporal_query_fingerprints,
                self.weights,
                self.embodiments,
            )
        ):
            raise ValueError("manifest dataset fields must have equal length")
        for value in (
            *self.datasets,
            *self.backends,
            *self.splits,
            *self.source_fingerprints,
            *self.schema_fingerprints,
            *self.temporal_query_fingerprints,
            self.schema_version,
        ):
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
            "source_fingerprints": self.source_fingerprints,
            "schema_fingerprints": self.schema_fingerprints,
            "temporal_query_fingerprints": self.temporal_query_fingerprints,
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


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """复制并冻结字符串键状态映射。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    output: dict[str, object] = {}
    for key, item in cast(Mapping[object, object], value).items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError(f"{name} keys must be non-empty strings")
        output[key] = item
    return MappingProxyType(output)


def _text_tuple(value: object, name: str) -> tuple[str, ...]:
    """读取非空字符串元组。"""
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"{name} must be a sequence")
    sequence = cast(Sequence[object], value)
    return tuple(_strict_text(item, f"{name} item") for item in sequence)


@dataclass(frozen=True, slots=True)
class DataLoaderState:
    """保存主进程已提交边界和完整 v2 恢复兼容状态。"""

    SCHEMA_VERSION: ClassVar[str] = "autovla.data_loader_state.v2"

    schema_version: str
    manifest_fingerprint: str
    backend_keys: tuple[str, ...]
    source_keys: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    split: str
    access_mode: str
    epoch: int
    global_batches_consumed: int
    global_samples_consumed: int
    sequence_seed: int
    permutation_seed: int
    committed_batch_cursor: int
    global_rank: int
    world_size: int
    configured_worker_count: int
    actual_loader_worker_count: int
    partition_policy: str
    batch_size: int
    drop_last: bool
    stream_mode: str | None
    map_shuffle: bool
    stream_shard_shuffle: bool
    stream_sample_shuffle_buffer: int
    sample_shuffle_resume_policy: str
    assignment_digests: Mapping[str, object]
    stream_partition_states: Mapping[str, object]
    stream_rng_state: Mapping[str, object]
    sample_shuffle_buffer_state: Mapping[str, object]
    map_sampler_state: Mapping[str, object]
    mixer_state: Mapping[str, object]
    balancer_state: Mapping[str, object]
    temporal_query_fingerprint: str
    temporal_query_state: Mapping[str, object]
    normalization_fingerprint: str
    generator_state: Mapping[str, object]
    compatibility_fingerprint: str

    def __post_init__(self) -> None:
        """校验 schema、计数器、分区拓扑与游标集合。"""

        if self.schema_version != self.SCHEMA_VERSION:
            raise ValueError("unsupported data loader state schema")
        for name in (
            "manifest_fingerprint",
            "split",
            "temporal_query_fingerprint",
            "normalization_fingerprint",
            "compatibility_fingerprint",
        ):
            _strict_text(getattr(self, name), name)
        for name in (
            "backend_keys",
            "source_keys",
            "source_fingerprints",
            "schema_fingerprints",
        ):
            values = _text_tuple(getattr(self, name), name)
            if not values:
                raise ValueError(f"{name} must not be empty")
            object.__setattr__(self, name, values)
        lengths = {
            len(self.backend_keys),
            len(self.source_keys),
            len(self.source_fingerprints),
            len(self.schema_fingerprints),
        }
        if len(lengths) != 1:
            raise ValueError("source identity tuple lengths must match")
        if self.access_mode not in {"map", "streaming"}:
            raise ValueError("access_mode must be map or streaming")
        for name in (
            "epoch",
            "global_batches_consumed",
            "global_samples_consumed",
            "sequence_seed",
            "permutation_seed",
            "committed_batch_cursor",
            "global_rank",
            "configured_worker_count",
            "actual_loader_worker_count",
            "stream_sample_shuffle_buffer",
        ):
            _strict_int(getattr(self, name), name)
        _strict_int(self.world_size, "world_size", minimum=1)
        _strict_int(self.batch_size, "batch_size", minimum=1)
        _strict_bool(self.drop_last, "drop_last")
        _strict_bool(self.map_shuffle, "map_shuffle")
        _strict_bool(self.stream_shard_shuffle, "stream_shard_shuffle")
        if self.global_rank >= self.world_size:
            raise ValueError("data loader partition topology is invalid")
        if self.actual_loader_worker_count > self.configured_worker_count:
            raise ValueError("observed worker count cannot exceed configured worker count")
        if self.partition_policy not in {"exact_no_pad", "drop_global_tail", "pad_repeat"}:
            raise ValueError("unsupported partition policy")
        if self.sample_shuffle_resume_policy not in {
            "disabled_for_exact_resume",
            "disabled_non_exact",
            "non_exact_unserialized",
        }:
            raise ValueError("unsupported sample shuffle resume policy")
        if (self.sample_shuffle_resume_policy == "non_exact_unserialized") != (
            self.stream_sample_shuffle_buffer > 0
        ):
            raise ValueError("sample shuffle resume policy conflicts with buffer size")
        if self.access_mode == "map" and self.stream_mode is not None:
            raise ValueError("map state cannot set stream_mode")
        if self.access_mode == "streaming" and self.stream_mode not in {
            "finite_epoch",
            "resampled",
        }:
            raise ValueError("streaming state requires a valid stream_mode")
        for name in (
            "assignment_digests",
            "stream_partition_states",
            "stream_rng_state",
            "sample_shuffle_buffer_state",
            "map_sampler_state",
            "mixer_state",
            "balancer_state",
            "temporal_query_state",
            "generator_state",
        ):
            object.__setattr__(self, name, _mapping(getattr(self, name), name))

    def to_dict(self) -> dict[str, object]:
        """返回严格、可序列化的状态映射。"""

        return {
            "schema_version": self.schema_version,
            "manifest_fingerprint": self.manifest_fingerprint,
            "backend_keys": list(self.backend_keys),
            "source_keys": list(self.source_keys),
            "source_fingerprints": list(self.source_fingerprints),
            "schema_fingerprints": list(self.schema_fingerprints),
            "split": self.split,
            "access_mode": self.access_mode,
            "epoch": self.epoch,
            "global_batches_consumed": self.global_batches_consumed,
            "global_samples_consumed": self.global_samples_consumed,
            "sequence_seed": self.sequence_seed,
            "permutation_seed": self.permutation_seed,
            "committed_batch_cursor": self.committed_batch_cursor,
            "global_rank": self.global_rank,
            "world_size": self.world_size,
            "configured_worker_count": self.configured_worker_count,
            "actual_loader_worker_count": self.actual_loader_worker_count,
            "partition_policy": self.partition_policy,
            "batch_size": self.batch_size,
            "drop_last": self.drop_last,
            "stream_mode": self.stream_mode,
            "map_shuffle": self.map_shuffle,
            "stream_shard_shuffle": self.stream_shard_shuffle,
            "stream_sample_shuffle_buffer": self.stream_sample_shuffle_buffer,
            "sample_shuffle_resume_policy": self.sample_shuffle_resume_policy,
            "assignment_digests": dict(self.assignment_digests),
            "stream_partition_states": dict(self.stream_partition_states),
            "stream_rng_state": dict(self.stream_rng_state),
            "sample_shuffle_buffer_state": dict(self.sample_shuffle_buffer_state),
            "map_sampler_state": dict(self.map_sampler_state),
            "mixer_state": dict(self.mixer_state),
            "balancer_state": dict(self.balancer_state),
            "temporal_query_fingerprint": self.temporal_query_fingerprint,
            "temporal_query_state": dict(self.temporal_query_state),
            "normalization_fingerprint": self.normalization_fingerprint,
            "generator_state": dict(self.generator_state),
            "compatibility_fingerprint": self.compatibility_fingerprint,
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DataLoaderState":
        """从字段集合完全匹配的映射构造状态。"""

        expected = {
            "schema_version",
            "manifest_fingerprint",
            "backend_keys",
            "source_keys",
            "source_fingerprints",
            "schema_fingerprints",
            "split",
            "access_mode",
            "epoch",
            "global_batches_consumed",
            "global_samples_consumed",
            "sequence_seed",
            "permutation_seed",
            "committed_batch_cursor",
            "global_rank",
            "world_size",
            "configured_worker_count",
            "actual_loader_worker_count",
            "partition_policy",
            "batch_size",
            "drop_last",
            "stream_mode",
            "map_shuffle",
            "stream_shard_shuffle",
            "stream_sample_shuffle_buffer",
            "sample_shuffle_resume_policy",
            "assignment_digests",
            "stream_partition_states",
            "stream_rng_state",
            "sample_shuffle_buffer_state",
            "map_sampler_state",
            "mixer_state",
            "balancer_state",
            "temporal_query_fingerprint",
            "temporal_query_state",
            "normalization_fingerprint",
            "generator_state",
            "compatibility_fingerprint",
        }
        _strict_fields(payload, expected, "data loader state")
        return cls(
            schema_version=_strict_text(payload["schema_version"], "schema_version"),
            manifest_fingerprint=_strict_text(
                payload["manifest_fingerprint"], "manifest_fingerprint"
            ),
            backend_keys=_text_tuple(payload["backend_keys"], "backend_keys"),
            source_keys=_text_tuple(payload["source_keys"], "source_keys"),
            source_fingerprints=_text_tuple(payload["source_fingerprints"], "source_fingerprints"),
            schema_fingerprints=_text_tuple(payload["schema_fingerprints"], "schema_fingerprints"),
            split=_strict_text(payload["split"], "split"),
            access_mode=_strict_text(payload["access_mode"], "access_mode"),
            epoch=_strict_int(payload["epoch"], "epoch"),
            global_batches_consumed=_strict_int(
                payload["global_batches_consumed"], "global_batches_consumed"
            ),
            global_samples_consumed=_strict_int(
                payload["global_samples_consumed"], "global_samples_consumed"
            ),
            sequence_seed=_strict_int(payload["sequence_seed"], "sequence_seed"),
            permutation_seed=_strict_int(payload["permutation_seed"], "permutation_seed"),
            committed_batch_cursor=_strict_int(
                payload["committed_batch_cursor"], "committed_batch_cursor"
            ),
            global_rank=_strict_int(payload["global_rank"], "global_rank"),
            world_size=_strict_int(payload["world_size"], "world_size", minimum=1),
            configured_worker_count=_strict_int(
                payload["configured_worker_count"], "configured_worker_count"
            ),
            actual_loader_worker_count=_strict_int(
                payload["actual_loader_worker_count"], "actual_loader_worker_count"
            ),
            partition_policy=_strict_text(payload["partition_policy"], "partition_policy"),
            batch_size=_strict_int(payload["batch_size"], "batch_size", minimum=1),
            drop_last=_strict_bool(payload["drop_last"], "drop_last"),
            stream_mode=(
                None
                if payload["stream_mode"] is None
                else _strict_text(payload["stream_mode"], "stream_mode")
            ),
            map_shuffle=_strict_bool(payload["map_shuffle"], "map_shuffle"),
            stream_shard_shuffle=_strict_bool(
                payload["stream_shard_shuffle"], "stream_shard_shuffle"
            ),
            stream_sample_shuffle_buffer=_strict_int(
                payload["stream_sample_shuffle_buffer"], "stream_sample_shuffle_buffer"
            ),
            sample_shuffle_resume_policy=_strict_text(
                payload["sample_shuffle_resume_policy"],
                "sample_shuffle_resume_policy",
            ),
            assignment_digests=_mapping(payload["assignment_digests"], "assignment_digests"),
            stream_partition_states=_mapping(
                payload["stream_partition_states"], "stream_partition_states"
            ),
            stream_rng_state=_mapping(payload["stream_rng_state"], "stream_rng_state"),
            sample_shuffle_buffer_state=_mapping(
                payload["sample_shuffle_buffer_state"], "sample_shuffle_buffer_state"
            ),
            map_sampler_state=_mapping(payload["map_sampler_state"], "map_sampler_state"),
            mixer_state=_mapping(payload["mixer_state"], "mixer_state"),
            balancer_state=_mapping(payload["balancer_state"], "balancer_state"),
            temporal_query_fingerprint=_strict_text(
                payload["temporal_query_fingerprint"], "temporal_query_fingerprint"
            ),
            temporal_query_state=_mapping(payload["temporal_query_state"], "temporal_query_state"),
            normalization_fingerprint=_strict_text(
                payload["normalization_fingerprint"], "normalization_fingerprint"
            ),
            generator_state=_mapping(payload["generator_state"], "generator_state"),
            compatibility_fingerprint=_strict_text(
                payload["compatibility_fingerprint"], "compatibility_fingerprint"
            ),
        )


@dataclass(frozen=True, slots=True)
class DataModuleState:
    """保存 DataModule 阶段和两个可选加载器状态。"""

    SCHEMA_VERSION: ClassVar[str] = "autovla.data_module_state.v2"

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
