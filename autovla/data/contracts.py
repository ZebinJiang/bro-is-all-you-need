"""AutoVLA 生产数据源、worker、分区、采样与恢复契约。"""

from __future__ import annotations

import hashlib
import json
import math
import random
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, fields, is_dataclass
from enum import Enum
from types import MappingProxyType
from typing import TypeAlias, cast

MapIndex: TypeAlias = tuple[int, int]
StreamAssignmentUnit: TypeAlias = tuple[int, str]
PartitionItem: TypeAlias = int | str | MapIndex | StreamAssignmentUnit


def _non_empty(value: str, name: str) -> str:
    """校验非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """校验排除 bool 的有界整数。"""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _strict_bool(value: object, name: str) -> bool:
    """校验严格布尔值。"""
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be bool")
    return value


def _canonical(value: object) -> object:
    """把不可变契约值转换为稳定 JSON 结构。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _canonical(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Mapping):
        return {str(key): _canonical(item) for key, item in sorted(value.items())}
    if isinstance(value, (tuple, list)):
        return [_canonical(item) for item in value]
    return value


def stable_fingerprint(value: object) -> str:
    """返回契约值的 SHA-256 稳定指纹。"""
    encoded = json.dumps(
        _canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class DataAccessMode(str, Enum):
    """区分确定性随机访问和顺序流式数据源。"""

    MAP = "map"
    STREAMING = "streaming"


AccessMode = DataAccessMode


class StreamMode(str, Enum):
    """声明 streaming epoch 是有限耗尽还是显式重采样。"""

    FINITE_EPOCH = "finite_epoch"
    RESAMPLED = "resampled"


class DataError(RuntimeError):
    """AutoVLA 数据平面的类型化错误基类。"""


class CorruptSampleError(DataError):
    """表示真实样本内容损坏。"""


class LocalMediaUnavailableError(DataError):
    """表示显式本地媒体不存在或不可读。"""


class DataSchemaMismatchError(DataError):
    """表示数据记录不满足声明 schema。"""


class DataDecodeError(DataError):
    """表示本地媒体或记录解码失败。"""


class TransientLocalIOError(DataError):
    """表示可按有界策略重试的瞬时本地 I/O 失败。"""


class WorkerInitializationError(DataError):
    """表示 worker 上下文或后端初始化失败。"""


class WorkerRuntimeError(DataError):
    """表示 worker 死亡或批次等待超时。"""


class IncompatibleDataStateError(DataError, ValueError):
    """表示检查点数据状态与当前运行契约不兼容。"""


SourceCompatibilityError = IncompatibleDataStateError


class UnsupportedBackendOperationError(DataError):
    """表示后端未实现所选访问模式或操作。"""


class DataLifecycleError(DataError):
    """表示数据源打开、使用或关闭顺序错误。"""


@dataclass(frozen=True, slots=True)
class DataSourceSpec:
    """描述打开数据前可验证的不可变源能力和兼容身份。"""

    dataset_key: str
    backend_key: str
    split: str
    access_mode: DataAccessMode
    source_fingerprint: str
    schema_fingerprint: str
    finite: bool
    sample_count: int | None
    supports_batch_read: bool
    supports_temporal_query: bool
    supports_media: bool
    supports_exact_resume: bool
    partition_units: tuple[str, ...] = ()
    stream_mode: StreamMode | None = None
    nominal_epoch_size: int | None = None
    local_only: bool = True
    compatibility_metadata: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验访问模式、长度、stream 模式和兼容元数据。"""
        for name in (
            "dataset_key",
            "backend_key",
            "split",
            "source_fingerprint",
            "schema_fingerprint",
        ):
            _non_empty(getattr(self, name), name)
        if not isinstance(self.access_mode, DataAccessMode):
            raise TypeError("access_mode must be DataAccessMode")
        if self.sample_count is not None:
            _strict_int(self.sample_count, "sample_count", minimum=1)
        if self.nominal_epoch_size is not None:
            _strict_int(self.nominal_epoch_size, "nominal_epoch_size", minimum=1)
        partition_units = tuple(self.partition_units)
        object.__setattr__(self, "partition_units", partition_units)
        if self.access_mode is DataAccessMode.MAP:
            if (
                not self.finite
                or self.sample_count is None
                or self.stream_mode is not None
                or self.partition_units
            ):
                raise ValueError("map source must be finite with sample_count and no stream_mode")
        else:
            if self.stream_mode is None:
                raise ValueError("streaming source requires stream_mode")
            if self.stream_mode is StreamMode.FINITE_EPOCH and self.nominal_epoch_size is None:
                raise ValueError("finite streaming source requires nominal_epoch_size")
            if self.stream_mode is StreamMode.RESAMPLED and self.nominal_epoch_size is None:
                raise ValueError("resampled streaming source requires nominal_epoch_size")
            if not partition_units or any(
                not isinstance(unit, str) or not unit.strip() for unit in partition_units
            ):
                raise ValueError("streaming source requires real partition_units")
            if len(set(partition_units)) != len(partition_units):
                raise ValueError("streaming partition_units must be unique")
        object.__setattr__(
            self,
            "compatibility_metadata",
            MappingProxyType(dict(self.compatibility_metadata)),
        )

    @property
    def compatibility_fingerprint(self) -> str:
        """返回源能力与 schema 的稳定兼容指纹。"""
        return stable_fingerprint(
            {
                "access_mode": self.access_mode,
                "backend_key": self.backend_key,
                "compatibility_metadata": self.compatibility_metadata,
                "dataset_key": self.dataset_key,
                "finite": self.finite,
                "local_only": self.local_only,
                "nominal_epoch_size": self.nominal_epoch_size,
                "partition_units": self.partition_units,
                "sample_count": self.sample_count,
                "schema_fingerprint": self.schema_fingerprint,
                "source_fingerprint": self.source_fingerprint,
                "split": self.split,
                "stream_mode": self.stream_mode,
                "supports_batch_read": self.supports_batch_read,
                "supports_exact_resume": self.supports_exact_resume,
                "supports_media": self.supports_media,
                "supports_temporal_query": self.supports_temporal_query,
            }
        )

    def __reduce__(self) -> tuple[object, tuple[object, ...]]:
        """用普通 dict 重建,保持 spawn pickle 不携带 mappingproxy。"""
        return (
            type(self),
            (
                self.dataset_key,
                self.backend_key,
                self.split,
                self.access_mode,
                self.source_fingerprint,
                self.schema_fingerprint,
                self.finite,
                self.sample_count,
                self.supports_batch_read,
                self.supports_temporal_query,
                self.supports_media,
                self.supports_exact_resume,
                self.partition_units,
                self.stream_mode,
                self.nominal_epoch_size,
                self.local_only,
                dict(self.compatibility_metadata),
            ),
        )


def derive_worker_seed(
    *, base_seed: int, epoch: int, global_rank: int, split: str, worker_id: int
) -> int:
    """从稳定运行身份派生 64-bit worker seed。"""
    for name, value in (
        ("base_seed", base_seed),
        ("epoch", epoch),
        ("global_rank", global_rank),
        ("worker_id", worker_id),
    ):
        _strict_int(value, name)
    digest = stable_fingerprint((base_seed, epoch, global_rank, split, worker_id))
    return int(digest[:16], 16)


_DEFAULT_WORKER_SEED = derive_worker_seed(
    base_seed=0,
    epoch=0,
    global_rank=0,
    split="train",
    worker_id=0,
)


@dataclass(frozen=True, slots=True)
class WorkerContext:
    """保存可序列化的实际 rank/worker 身份和确定性种子。"""

    global_rank: int = 0
    local_rank: int = 0
    world_size: int = 1
    worker_id: int = 0
    logical_worker_count: int = 1
    actual_worker_process_count: int = 0
    base_seed: int = 0
    derived_worker_seed: int = _DEFAULT_WORKER_SEED
    epoch: int = 0
    split: str = "train"
    multiprocessing_start_method: str = "none"
    node_id: str | None = None
    is_main_process: bool = True

    def __post_init__(self) -> None:
        """校验进程拓扑、实际 worker 数和派生种子。"""
        for name in (
            "global_rank",
            "local_rank",
            "worker_id",
            "actual_worker_process_count",
            "base_seed",
            "derived_worker_seed",
            "epoch",
        ):
            _strict_int(getattr(self, name), name)
        _strict_int(self.world_size, "world_size", minimum=1)
        _strict_int(self.logical_worker_count, "logical_worker_count", minimum=1)
        if self.global_rank >= self.world_size or self.worker_id >= self.logical_worker_count:
            raise ValueError("worker topology is invalid")
        if self.local_rank > self.global_rank:
            raise ValueError("local_rank cannot exceed global_rank without node topology")
        _non_empty(self.split, "split")
        _non_empty(self.multiprocessing_start_method, "multiprocessing_start_method")
        if self.node_id is not None:
            _non_empty(self.node_id, "node_id")
        if self.actual_worker_process_count == 0:
            if self.worker_id != 0 or self.logical_worker_count != 1 or not self.is_main_process:
                raise ValueError("zero-worker context must describe the main process")
        elif self.is_main_process:
            raise ValueError("worker process context cannot be marked main")
        elif self.actual_worker_process_count > self.logical_worker_count:
            raise ValueError("observed worker processes cannot exceed logical worker count")
        expected_seed = derive_worker_seed(
            base_seed=self.base_seed,
            epoch=self.epoch,
            global_rank=self.global_rank,
            split=self.split,
            worker_id=self.worker_id,
        )
        if self.derived_worker_seed != expected_seed:
            raise ValueError("derived_worker_seed does not match deterministic inputs")

    @classmethod
    def create(
        cls,
        *,
        global_rank: int,
        local_rank: int,
        world_size: int,
        worker_id: int,
        logical_worker_count: int,
        actual_worker_process_count: int,
        base_seed: int,
        epoch: int,
        split: str,
        multiprocessing_start_method: str,
        node_id: str | None = None,
        is_main_process: bool,
    ) -> "WorkerContext":
        """按契约字段构造并派生 worker seed。"""
        return cls(
            global_rank=global_rank,
            local_rank=local_rank,
            world_size=world_size,
            worker_id=worker_id,
            logical_worker_count=logical_worker_count,
            actual_worker_process_count=actual_worker_process_count,
            base_seed=base_seed,
            derived_worker_seed=derive_worker_seed(
                base_seed=base_seed,
                epoch=epoch,
                global_rank=global_rank,
                split=split,
                worker_id=worker_id,
            ),
            epoch=epoch,
            split=split,
            multiprocessing_start_method=multiprocessing_start_method,
            node_id=node_id,
            is_main_process=is_main_process,
        )

    @property
    def global_worker_id(self) -> int:
        """返回跨 rank 的稳定逻辑 worker 编号。"""
        return self.global_rank * self.logical_worker_count + self.worker_id


@dataclass(frozen=True, slots=True)
class StreamPartitionState:
    """保存 streaming worker 的下一条未读位置和 RNG 状态。"""

    worker_id: int
    epoch: int
    assignment_owner: str
    assigned_units: tuple[str, ...]
    upstream_partitioning_disabled: bool
    assignment_digest: str
    shard_order_digest: str
    current_shard: str | None = None
    shard_index: int = 0
    consumed_sample_offset: int = 0
    shard_rng_state: Mapping[str, object] = field(default_factory=dict)
    sample_rng_state: Mapping[str, object] = field(default_factory=dict)
    sample_shuffle_resume_policy: str = "disabled_for_exact_resume"
    sample_shuffle_buffer_state: tuple[Mapping[str, object], ...] = ()
    handler_counts: Mapping[str, int] = field(default_factory=dict)
    source_state: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """校验流位置并冻结嵌套状态。"""
        _strict_int(self.worker_id, "worker_id")
        _strict_int(self.epoch, "epoch")
        if self.assignment_owner != "autovla_loader":
            raise ValueError("stream assignment_owner must be autovla_loader")
        assigned_units = tuple(self.assigned_units)
        if not assigned_units or any(
            not isinstance(unit, str) or not unit.strip() for unit in assigned_units
        ):
            raise ValueError("stream state requires assigned_units")
        if len(set(assigned_units)) != len(assigned_units):
            raise ValueError("stream state assigned_units must be unique")
        object.__setattr__(self, "assigned_units", assigned_units)
        if not self.upstream_partitioning_disabled:
            raise ValueError("backend/upstream partitioning must be disabled")
        _strict_int(self.shard_index, "shard_index")
        _strict_int(self.consumed_sample_offset, "consumed_sample_offset")
        _non_empty(self.assignment_digest, "assignment_digest")
        _non_empty(self.shard_order_digest, "shard_order_digest")
        if self.current_shard is not None:
            _non_empty(self.current_shard, "current_shard")
        if self.sample_shuffle_resume_policy not in {
            "disabled_for_exact_resume",
            "disabled_non_exact",
            "non_exact_unserialized",
        }:
            raise ValueError("unsupported stream sample shuffle resume policy")
        if self.sample_shuffle_resume_policy != "non_exact_unserialized" and (
            self.sample_shuffle_buffer_state
        ):
            raise ValueError("disabled sample shuffle cannot carry buffer state")
        object.__setattr__(self, "shard_rng_state", MappingProxyType(dict(self.shard_rng_state)))
        object.__setattr__(self, "sample_rng_state", MappingProxyType(dict(self.sample_rng_state)))
        object.__setattr__(
            self,
            "sample_shuffle_buffer_state",
            tuple(MappingProxyType(dict(item)) for item in self.sample_shuffle_buffer_state),
        )
        handler_counts = dict(self.handler_counts)
        if any(
            not isinstance(key, str) or not key.strip() or type(value) is not int or value < 0
            for key, value in handler_counts.items()
        ):
            raise ValueError("handler_counts must map names to non-negative integers")
        object.__setattr__(self, "handler_counts", MappingProxyType(handler_counts))
        object.__setattr__(self, "source_state", MappingProxyType(dict(self.source_state)))

    def to_dict(self) -> dict[str, object]:
        """返回可序列化状态。"""
        return cast(dict[str, object], _canonical(self))

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "StreamPartitionState":
        """严格解析 worker stream 下一条未读位置。"""
        expected = {
            "worker_id",
            "epoch",
            "assignment_owner",
            "assigned_units",
            "upstream_partitioning_disabled",
            "assignment_digest",
            "shard_order_digest",
            "current_shard",
            "shard_index",
            "consumed_sample_offset",
            "shard_rng_state",
            "sample_rng_state",
            "sample_shuffle_resume_policy",
            "sample_shuffle_buffer_state",
            "handler_counts",
            "source_state",
        }
        if set(payload) != expected:
            raise ValueError("stream partition state fields mismatch")
        return cls(
            worker_id=_strict_int(payload["worker_id"], "worker_id"),
            epoch=_strict_int(payload["epoch"], "epoch"),
            assignment_owner=_non_empty(cast(str, payload["assignment_owner"]), "assignment_owner"),
            assigned_units=tuple(
                _non_empty(cast(str, unit), "assigned_unit")
                for unit in cast(Sequence[object], payload["assigned_units"])
            ),
            upstream_partitioning_disabled=_strict_bool(
                payload["upstream_partitioning_disabled"],
                "upstream_partitioning_disabled",
            ),
            assignment_digest=_non_empty(
                cast(str, payload["assignment_digest"]), "assignment_digest"
            ),
            shard_order_digest=_non_empty(
                cast(str, payload["shard_order_digest"]), "shard_order_digest"
            ),
            current_shard=cast(str | None, payload["current_shard"]),
            shard_index=_strict_int(payload["shard_index"], "shard_index"),
            consumed_sample_offset=_strict_int(
                payload["consumed_sample_offset"], "consumed_sample_offset"
            ),
            shard_rng_state=cast(Mapping[str, object], payload["shard_rng_state"]),
            sample_rng_state=cast(Mapping[str, object], payload["sample_rng_state"]),
            sample_shuffle_resume_policy=_non_empty(
                cast(str, payload["sample_shuffle_resume_policy"]),
                "sample_shuffle_resume_policy",
            ),
            sample_shuffle_buffer_state=tuple(
                cast(Sequence[Mapping[str, object]], payload["sample_shuffle_buffer_state"])
            ),
            handler_counts=cast(Mapping[str, int], payload["handler_counts"]),
            source_state=cast(Mapping[str, object], payload["source_state"]),
        )


@dataclass(frozen=True, slots=True)
class PartitionPlan:
    """保存一次性 rank/worker 分区、序列摘要和尾部策略。"""

    access_mode: DataAccessMode
    policy: str
    global_sequence: tuple[PartitionItem, ...]
    rank_sequence: tuple[PartitionItem, ...]
    worker_assignments: tuple[tuple[PartitionItem, ...], ...]
    global_rank: int
    world_size: int
    permutation_seed: int
    dropped_count: int = 0
    repeated_count: int = 0
    sequence_digest: str = field(init=False)
    rank_assignment_digest: str = field(init=False)
    worker_assignment_digests: tuple[str, ...] = field(init=False)

    def __post_init__(self) -> None:
        """校验策略、拓扑和确定性摘要。"""
        _strict_int(self.global_rank, "global_rank")
        _strict_int(self.world_size, "world_size", minimum=1)
        _strict_int(self.permutation_seed, "permutation_seed")
        _strict_int(self.dropped_count, "dropped_count")
        _strict_int(self.repeated_count, "repeated_count")
        if self.global_rank >= self.world_size:
            raise ValueError("global_rank must be smaller than world_size")
        if self.policy not in {"exact_no_pad", "drop_global_tail", "pad_repeat"}:
            raise ValueError("unsupported partition policy")
        object.__setattr__(
            self,
            "sequence_digest",
            stable_fingerprint(
                {"permutation_seed": self.permutation_seed, "items": self.global_sequence}
            ),
        )
        object.__setattr__(
            self,
            "rank_assignment_digest",
            stable_fingerprint(
                {"permutation_seed": self.permutation_seed, "items": self.rank_sequence}
            ),
        )
        object.__setattr__(
            self,
            "worker_assignment_digests",
            tuple(
                stable_fingerprint(
                    {
                        "permutation_seed": self.permutation_seed,
                        "worker_id": worker_id,
                        "items": items,
                    }
                )
                for worker_id, items in enumerate(self.worker_assignments)
            ),
        )

    @classmethod
    def for_map(
        cls,
        sequence: Sequence[MapIndex],
        *,
        global_rank: int,
        world_size: int,
        batch_size: int,
        seed: int,
        epoch: int,
        shuffle: bool,
        policy: str,
    ) -> "PartitionPlan":
        """打乱一次、处理全局尾部并按 rank 切分 map 索引。"""
        items = list(sequence)
        permutation_seed = derive_worker_seed(
            base_seed=seed,
            epoch=epoch,
            global_rank=0,
            split="map-permutation",
            worker_id=0,
        )
        if shuffle:
            random.Random(permutation_seed).shuffle(items)
        dropped = 0
        repeated = 0
        unit = world_size * batch_size
        if policy == "drop_global_tail" and unit > 0:
            kept = len(items) - len(items) % unit
            dropped = len(items) - kept
            items = items[:kept]
        elif policy == "pad_repeat" and items and len(items) % unit:
            repeated = unit - len(items) % unit
            items.extend(items[index % len(items)] for index in range(repeated))
        rank_items = tuple(items[global_rank::world_size])
        return cls(
            access_mode=DataAccessMode.MAP,
            policy=policy,
            global_sequence=tuple(items),
            rank_sequence=rank_items,
            worker_assignments=(),
            global_rank=global_rank,
            world_size=world_size,
            permutation_seed=permutation_seed,
            dropped_count=dropped,
            repeated_count=repeated,
        )

    @classmethod
    def for_streaming(
        cls,
        assignment_units: Sequence[StreamAssignmentUnit],
        *,
        global_rank: int,
        world_size: int,
        logical_worker_count: int,
        seed: int,
        epoch: int,
        shuffle: bool,
    ) -> "PartitionPlan":
        """打乱真实源单元一次,先按 rank 再按 worker 切分。"""
        _strict_int(logical_worker_count, "logical_worker_count", minimum=1)
        if not assignment_units or any(
            type(source_id) is not int or source_id < 0 or not unit_id.strip()
            for source_id, unit_id in assignment_units
        ):
            raise ValueError("streaming units must be (source_id, non-empty unit_id)")
        if len(set(assignment_units)) != len(assignment_units):
            raise ValueError("streaming assignment units must be unique")
        permutation_seed = derive_worker_seed(
            base_seed=seed,
            epoch=epoch,
            global_rank=0,
            split="stream-shards",
            worker_id=0,
        )
        ordered = list(assignment_units)
        if shuffle:
            random.Random(permutation_seed).shuffle(ordered)
        rank_items = tuple(ordered[global_rank::world_size])
        workers = tuple(
            tuple(rank_items[worker_id::logical_worker_count])
            for worker_id in range(logical_worker_count)
        )
        return cls(
            access_mode=DataAccessMode.STREAMING,
            policy="exact_no_pad",
            global_sequence=tuple(ordered),
            rank_sequence=rank_items,
            worker_assignments=workers,
            global_rank=global_rank,
            world_size=world_size,
            permutation_seed=permutation_seed,
        )


@dataclass(frozen=True, slots=True)
class SamplingPlan:
    """保存 map/stream 分离的 shuffle、耗尽和批语义。"""

    access_mode: DataAccessMode
    batch_size: int
    drop_last: bool
    base_seed: int
    map_shuffle: bool = False
    stream_shard_shuffle: bool = False
    stream_sample_shuffle_buffer: int = 0
    replacement: bool = False
    nominal_epoch_size: int | None = None
    exact_resume: bool = True

    def __post_init__(self) -> None:
        """拒绝跨访问模式字段和不可恢复 stream 组合。"""
        _strict_int(self.batch_size, "batch_size", minimum=1)
        _strict_int(self.base_seed, "base_seed")
        _strict_int(self.stream_sample_shuffle_buffer, "stream_sample_shuffle_buffer")
        if self.nominal_epoch_size is not None:
            _strict_int(self.nominal_epoch_size, "nominal_epoch_size", minimum=1)
        if self.access_mode is DataAccessMode.MAP:
            if self.stream_shard_shuffle or self.stream_sample_shuffle_buffer:
                raise ValueError("map sampling cannot set stream shuffle fields")
            if self.replacement and self.nominal_epoch_size is None:
                raise ValueError("replacement map sampling requires nominal_epoch_size")
        else:
            if self.map_shuffle:
                raise ValueError("streaming sampling cannot set map_shuffle")
            if self.nominal_epoch_size is None:
                raise ValueError("streaming sampling requires nominal_epoch_size")
            if self.exact_resume and self.stream_sample_shuffle_buffer:
                raise ValueError(
                    "exact streaming resume requires stream_sample_shuffle_buffer=0; "
                    "buffered sample shuffle is non-exact and is not serialized"
                )

    @property
    def compatibility_fingerprint(self) -> str:
        """返回全部采样语义的稳定指纹。"""
        return stable_fingerprint(self)


@dataclass(frozen=True, slots=True)
class TemporalQuery:
    """描述时间特征查询和独立 temporal mask 语义。"""

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
        """校验查询字段、边界策略和时间参数。"""
        _non_empty(self.feature_key, "feature_key")
        _non_empty(self.feature_family, "feature_family")
        if not self.frame_offsets and not self.timestamp_deltas:
            raise ValueError("temporal query requires frame offsets or timestamp deltas")
        if self.anchor_semantics not in {"sample", "frame", "timestamp"}:
            raise ValueError("unsupported temporal anchor semantics")
        if self.boundary_policy not in {"pad", "clip", "error"}:
            raise ValueError("unsupported temporal boundary policy")
        if self.output_mask_semantics not in {"true_is_observed", "true_is_padding"}:
            raise ValueError("unsupported temporal output mask semantics")
        _strict_int(self.action_horizon, "action_horizon", minimum=1)
        if self.fps is not None and (not math.isfinite(self.fps) or self.fps <= 0):
            raise ValueError("fps must be positive and finite")
        if self.tolerance is not None and (not math.isfinite(self.tolerance) or self.tolerance < 0):
            raise ValueError("tolerance must be non-negative and finite")

    @property
    def fingerprint(self) -> str:
        """返回时间查询稳定指纹。"""
        return stable_fingerprint(self)


__all__ = [
    "AccessMode",
    "CorruptSampleError",
    "DataAccessMode",
    "DataDecodeError",
    "DataError",
    "DataLifecycleError",
    "DataSchemaMismatchError",
    "DataSourceSpec",
    "IncompatibleDataStateError",
    "LocalMediaUnavailableError",
    "MapIndex",
    "PartitionPlan",
    "SamplingPlan",
    "SourceCompatibilityError",
    "StreamAssignmentUnit",
    "StreamMode",
    "StreamPartitionState",
    "TemporalQuery",
    "TransientLocalIOError",
    "UnsupportedBackendOperationError",
    "WorkerContext",
    "WorkerInitializationError",
    "WorkerRuntimeError",
    "derive_worker_seed",
    "stable_fingerprint",
]
