"""AutoVLA 生产数据批到训练运行时的后端中立交接契约。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from autovla.core.types.training import TrainingBatch
from autovla.data.contracts import stable_fingerprint

DATA_RUNTIME_HANDOFF_SCHEMA = "autovla.data_runtime_handoff.v1"
BACKEND_DECISION = "NO_BACKEND_WINNER"


def _non_empty_text(value: object, name: str) -> str:
    """校验并返回非空文本。"""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """校验排除布尔值的有界整数。"""

    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _logical_sample_id(source: Mapping[str, object], index: int) -> str:
    """从物理来源映射提取不包含 backend 名称的稳定逻辑样本 ID。"""

    sample_id = _non_empty_text(source.get("sample_id"), f"sample_source[{index}].sample_id")
    explicit = source.get("logical_sample_id")
    if explicit is not None and _non_empty_text(
        explicit, f"sample_source[{index}].logical_sample_id"
    ) != sample_id:
        raise ValueError("logical_sample_id must equal the backend-independent sample_id")
    return sample_id


@dataclass(frozen=True, slots=True)
class DataWaitTelemetry:
    """保存 rank-local loader 等待时间, 供 Training 直接消费。"""

    observed_batches: int = 0
    total_seconds: float = 0.0
    last_seconds: float = 0.0
    max_seconds: float = 0.0

    def __post_init__(self) -> None:
        """校验计数和有限非负耗时。"""

        _strict_int(self.observed_batches, "observed_batches")
        for name in ("total_seconds", "last_seconds", "max_seconds"):
            value = getattr(self, name)
            if type(value) is not float or not math.isfinite(value) or value < 0.0:
                raise ValueError(f"{name} must be a finite non-negative float")
        if self.observed_batches == 0 and any(
            value != 0.0 for value in (self.total_seconds, self.last_seconds, self.max_seconds)
        ):
            raise ValueError("empty data-wait telemetry cannot contain elapsed time")
        if self.last_seconds > self.max_seconds or self.max_seconds > self.total_seconds:
            raise ValueError("data-wait telemetry aggregates are inconsistent")

    def observe(self, elapsed_seconds: float) -> "DataWaitTelemetry":
        """以常数时间追加一次完整批次等待观测。"""

        if (
            type(elapsed_seconds) is not float
            or not math.isfinite(elapsed_seconds)
            or elapsed_seconds < 0.0
        ):
            raise ValueError("elapsed_seconds must be a finite non-negative float")
        elapsed = elapsed_seconds
        return type(self)(
            observed_batches=self.observed_batches + 1,
            total_seconds=self.total_seconds + elapsed,
            last_seconds=elapsed,
            max_seconds=max(self.max_seconds, elapsed),
        )

    @property
    def mean_seconds(self) -> float:
        """返回已观测批次的平均等待时间。"""

        if self.observed_batches == 0:
            return 0.0
        return self.total_seconds / self.observed_batches

    def to_dict(self) -> dict[str, object]:
        """返回 logger 可直接序列化的稳定载荷。"""

        return {
            "observed_batches": self.observed_batches,
            "total_seconds": self.total_seconds,
            "last_seconds": self.last_seconds,
            "max_seconds": self.max_seconds,
            "mean_seconds": self.mean_seconds,
        }


@dataclass(frozen=True, slots=True)
class DataRuntimeHandoff:
    """描述一个已提交批次的逻辑身份、动作语义和恢复边界。

    该对象不持有图像、状态或动作数组, 因此不会复制张量, 也不会延长批次
    内存生命周期。动作仍由规范 ``TrainingBatch`` 以 ``[B,H,D]`` 和严格布尔
    掩码交付; 此 sidecar 只提供 Training、checkpoint 与遥测需要的稳定元数据。
    """

    logical_sample_ids: tuple[str, ...]
    logical_batch_fingerprint: str
    dataset_manifest_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    store_fingerprints: tuple[str, ...]
    source_fingerprints: tuple[str, ...]
    schema_fingerprints: tuple[str, ...]
    rank: int
    world_size: int
    epoch: int
    global_batches_consumed: int
    global_samples_consumed: int
    committed_sample_cursor: int
    assignment_digest: str
    resume_fingerprint: str
    action_shape: tuple[int, int, int]
    data_wait: DataWaitTelemetry
    schema_version: str = DATA_RUNTIME_HANDOFF_SCHEMA
    action_layout: str = "BHD"
    action_mask_semantics: str = "strict_bool_true_is_valid"
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """校验拓扑、计数、身份和规范动作/掩码语义。"""

        if self.schema_version != DATA_RUNTIME_HANDOFF_SCHEMA:
            raise ValueError("unsupported data runtime handoff schema")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("data runtime handoff must preserve NO_BACKEND_WINNER")
        if not self.logical_sample_ids:
            raise ValueError("logical_sample_ids must not be empty")
        for name in (
            "logical_batch_fingerprint",
            "dataset_manifest_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
            "assignment_digest",
            "resume_fingerprint",
        ):
            _non_empty_text(getattr(self, name), name)
        for group_name in (
            "logical_sample_ids",
            "store_fingerprints",
            "source_fingerprints",
            "schema_fingerprints",
        ):
            for index, value in enumerate(getattr(self, group_name)):
                _non_empty_text(value, f"{group_name}[{index}]")
        for name in (
            "rank",
            "epoch",
            "global_samples_consumed",
            "committed_sample_cursor",
        ):
            _strict_int(getattr(self, name), name)
        _strict_int(self.global_batches_consumed, "global_batches_consumed", minimum=1)
        _strict_int(self.world_size, "world_size", minimum=1)
        if self.rank >= self.world_size:
            raise ValueError("rank must be smaller than world_size")
        if self.action_layout != "BHD" or self.action_mask_semantics != (
            "strict_bool_true_is_valid"
        ):
            raise ValueError("unsupported canonical action or mask semantics")
        if len(self.action_shape) != 3 or any(
            type(value) is not int or value <= 0 for value in self.action_shape
        ):
            raise ValueError("action_shape must contain positive [B,H,D] dimensions")
        if self.action_shape[0] != len(self.logical_sample_ids):
            raise ValueError("action batch dimension must match logical sample IDs")
        if self.global_samples_consumed < len(self.logical_sample_ids):
            raise ValueError("global sample count cannot precede the committed batch")
        if not len(self.logical_sample_ids) <= self.committed_sample_cursor <= (
            self.global_samples_consumed
        ):
            raise ValueError("committed sample cursor is inconsistent with global samples")
        for values in (
            self.store_fingerprints,
            self.source_fingerprints,
            self.schema_fingerprints,
        ):
            if values and len(values) != len(self.logical_sample_ids):
                raise ValueError("ordered fingerprints must match batch size when present")
        if self.data_wait.observed_batches > self.global_batches_consumed:
            raise ValueError("data-wait count cannot exceed committed global batch count")

    @classmethod
    def from_committed_batch(
        cls,
        batch: TrainingBatch,
        *,
        rank: int,
        world_size: int,
        epoch: int,
        global_batches_consumed: int,
        global_samples_consumed: int,
        committed_sample_cursor: int,
        assignment_digest: str,
        compatibility_fingerprint: str,
        data_wait: DataWaitTelemetry,
    ) -> "DataRuntimeHandoff":
        """从已提交规范批次构建不持有数组的运行时 sidecar。"""

        if not isinstance(batch, TrainingBatch):
            raise TypeError("runtime handoff requires canonical TrainingBatch")
        sample_ids = tuple(
            _logical_sample_id(source, index) for index, source in enumerate(batch.sample_source)
        )
        dataset_identity = _non_empty_text(
            batch.dataset_manifest_fingerprint or batch.dataset_fingerprint,
            "dataset_manifest_fingerprint",
        )
        batch_identity = {
            "logical_sample_ids": sample_ids,
            "dataset_manifest_fingerprint": dataset_identity,
            "transform_fingerprint": batch.transform_fingerprint,
            "statistics_fingerprint": batch.statistics_fingerprint,
        }
        resume_identity = {
            "assignment_digest": assignment_digest,
            "committed_sample_cursor": committed_sample_cursor,
            "compatibility_fingerprint": compatibility_fingerprint,
            "epoch": epoch,
            "global_batches_consumed": global_batches_consumed,
            "global_samples_consumed": global_samples_consumed,
            "rank": rank,
            "world_size": world_size,
        }
        return cls(
            logical_sample_ids=sample_ids,
            logical_batch_fingerprint=stable_fingerprint(batch_identity),
            dataset_manifest_fingerprint=dataset_identity,
            transform_fingerprint=batch.transform_fingerprint,
            statistics_fingerprint=batch.statistics_fingerprint,
            store_fingerprints=batch.store_fingerprints,
            source_fingerprints=batch.source_fingerprints,
            schema_fingerprints=batch.schema_fingerprints,
            rank=rank,
            world_size=world_size,
            epoch=epoch,
            global_batches_consumed=global_batches_consumed,
            global_samples_consumed=global_samples_consumed,
            committed_sample_cursor=committed_sample_cursor,
            assignment_digest=assignment_digest,
            resume_fingerprint=stable_fingerprint(resume_identity),
            action_shape=(batch.batch_size, batch.action_horizon, batch.action_dim),
            data_wait=data_wait,
        )

    def to_dict(self) -> dict[str, object]:
        """返回 Training/logger/checkpoint 可直接消费的纯元数据。"""

        return {
            "schema_version": self.schema_version,
            "logical_sample_ids": list(self.logical_sample_ids),
            "logical_batch_fingerprint": self.logical_batch_fingerprint,
            "dataset_manifest_fingerprint": self.dataset_manifest_fingerprint,
            "transform_fingerprint": self.transform_fingerprint,
            "statistics_fingerprint": self.statistics_fingerprint,
            "store_fingerprints": list(self.store_fingerprints),
            "source_fingerprints": list(self.source_fingerprints),
            "schema_fingerprints": list(self.schema_fingerprints),
            "rank": self.rank,
            "world_size": self.world_size,
            "epoch": self.epoch,
            "global_batches_consumed": self.global_batches_consumed,
            "global_samples_consumed": self.global_samples_consumed,
            "committed_sample_cursor": self.committed_sample_cursor,
            "assignment_digest": self.assignment_digest,
            "resume_fingerprint": self.resume_fingerprint,
            "action_shape": list(self.action_shape),
            "action_layout": self.action_layout,
            "action_mask_semantics": self.action_mask_semantics,
            "data_wait": self.data_wait.to_dict(),
            "backend_decision": self.backend_decision,
        }


def logical_batch_fingerprint(
    sample_sources: Sequence[Mapping[str, object]],
    *,
    dataset_manifest_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
) -> str:
    """计算与物理后端无关的有序逻辑批身份。"""

    sample_ids = tuple(
        _logical_sample_id(source, index) for index, source in enumerate(sample_sources)
    )
    if not sample_ids:
        raise ValueError("sample_sources must not be empty")
    return stable_fingerprint(
        {
            "logical_sample_ids": sample_ids,
            "dataset_manifest_fingerprint": _non_empty_text(
                dataset_manifest_fingerprint, "dataset_manifest_fingerprint"
            ),
            "transform_fingerprint": _non_empty_text(
                transform_fingerprint, "transform_fingerprint"
            ),
            "statistics_fingerprint": _non_empty_text(
                statistics_fingerprint, "statistics_fingerprint"
            ),
        }
    )


__all__ = [
    "BACKEND_DECISION",
    "DATA_RUNTIME_HANDOFF_SCHEMA",
    "DataRuntimeHandoff",
    "DataWaitTelemetry",
    "logical_batch_fingerprint",
]
