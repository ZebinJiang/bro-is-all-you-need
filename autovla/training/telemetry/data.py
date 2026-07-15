"""AutoVLA 数据平面遥测的稳定记录契约。"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from autovla.core.types.training import TrainingBatch
from autovla.training.checkpointing.identity import stable_fingerprint

DATA_TELEMETRY_SCHEMA = "autovla.data_telemetry.v1"


def _empty_counts() -> dict[str, int]:
    """返回类型明确的空计数映射。"""
    return {}


def _empty_floats() -> dict[str, float]:
    """返回类型明确的空浮点映射。"""
    return {}


def _is_finite_number(value: object) -> bool:
    """在遥测解码边界仅接受有限内置浮点数。"""
    return type(value) is float and math.isfinite(value)


def _freeze_counts(values: object, name: str) -> Mapping[str, int]:
    """校验非负计数并冻结映射。"""
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, int] = {}
    for key, value in cast(Mapping[object, object], values).items():
        if type(key) is not str or not key.strip():
            raise TypeError(f"{name} keys must be non-empty text")
        if type(value) is not int or value < 0:
            raise ValueError(f"{name} values must be non-negative integers")
        result[key] = value
    return MappingProxyType(result)


def _freeze_floats(values: object, name: str) -> Mapping[str, float]:
    """校验有限浮点映射并冻结。"""
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, float] = {}
    for key, value in cast(Mapping[object, object], values).items():
        if type(key) is not str or not key.strip():
            raise TypeError(f"{name} keys must be non-empty text")
        if not _is_finite_number(value):
            raise ValueError(f"{name} values must be finite floats")
        result[key] = cast(float, value)
    return MappingProxyType(result)


def _normalize_weights(values: object, name: str) -> dict[str, float]:
    """接受 JSON 数值且拒绝 bool 并规范为有限内置浮点数。"""
    if not isinstance(values, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, float] = {}
    for key, value in cast(Mapping[object, object], values).items():
        if type(key) is not str or not key.strip():
            raise TypeError(f"{name} keys must be non-empty text")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeError(f"{name} values must be numeric")
        normalized = float(value)
        if not math.isfinite(normalized):
            raise ValueError(f"{name} values must be finite")
        result[key] = normalized
    return result


@dataclass(frozen=True, slots=True)
class DataTelemetryRecord:
    """保存 rank-local 或 reduced 的完整数据遥测快照。"""

    rank: int
    world_size: int
    aggregate: str
    samples_by_dataset: Mapping[str, int] = field(default_factory=_empty_counts)
    batches_by_dataset: Mapping[str, int] = field(default_factory=_empty_counts)
    samples_by_embodiment: Mapping[str, int] = field(default_factory=_empty_counts)
    batches_by_embodiment: Mapping[str, int] = field(default_factory=_empty_counts)
    requested_weights: Mapping[str, float] = field(default_factory=_empty_floats)
    effective_weights: Mapping[str, float] = field(default_factory=_empty_floats)
    balance_deviations: Mapping[str, float] = field(default_factory=_empty_floats)
    skipped_by_reason: Mapping[str, int] = field(default_factory=_empty_counts)
    data_wait_seconds: float = 0.0
    decode_seconds: float | None = None
    collate_seconds: float | None = None
    valid_image_elements: int = 0
    valid_token_elements: int = 0
    valid_action_elements: int = 0
    source_fingerprints: tuple[str, ...] = ()
    transform_fingerprint: str = "identity"

    def __post_init__(self) -> None:
        """校验 rank、计数、耗时与身份。"""
        if type(self.rank) is not int or type(self.world_size) is not int:
            raise TypeError("telemetry rank/world_size must be integers")
        if self.rank < 0 or self.world_size <= 0 or self.rank >= self.world_size:
            raise ValueError("invalid telemetry rank/world_size")
        if type(self.aggregate) is not str or self.aggregate not in {
            "rank_local",
            "reduced_sum",
            "reduced_mean",
        }:
            raise ValueError("unsupported telemetry aggregate identity")
        for name in (
            "samples_by_dataset",
            "batches_by_dataset",
            "samples_by_embodiment",
            "batches_by_embodiment",
            "skipped_by_reason",
        ):
            object.__setattr__(self, name, _freeze_counts(getattr(self, name), name))
        for name in ("requested_weights", "effective_weights", "balance_deviations"):
            object.__setattr__(self, name, _freeze_floats(getattr(self, name), name))
        for name in ("data_wait_seconds", "decode_seconds", "collate_seconds"):
            value = getattr(self, name)
            if value is not None and (
                type(value) is not float or not math.isfinite(value) or value < 0.0
            ):
                raise ValueError(f"{name} must be a finite non-negative float")
        if any(
            type(value) is not int
            for value in (
                self.valid_image_elements,
                self.valid_token_elements,
                self.valid_action_elements,
            )
        ):
            raise TypeError("valid element counts must be integers")
        if (
            min(
                self.valid_image_elements,
                self.valid_token_elements,
                self.valid_action_elements,
            )
            < 0
        ):
            raise ValueError("valid element counts must be non-negative")
        if type(self.source_fingerprints) is not tuple or any(
            type(value) is not str or not value.strip() for value in self.source_fingerprints
        ):
            raise ValueError("source fingerprints must be a tuple of non-empty text")
        if type(self.transform_fingerprint) is not str or not self.transform_fingerprint.strip():
            raise ValueError("transform fingerprint must not be empty")

    def to_dict(self) -> dict[str, object]:
        """返回 logger/checkpoint 共用的稳定载荷。"""
        mapping_names = (
            "samples_by_dataset",
            "batches_by_dataset",
            "samples_by_embodiment",
            "batches_by_embodiment",
            "requested_weights",
            "effective_weights",
            "balance_deviations",
            "skipped_by_reason",
        )
        payload: dict[str, object] = {
            name: dict(sorted(getattr(self, name).items())) for name in mapping_names
        }
        payload.update(
            {
                "rank": self.rank,
                "world_size": self.world_size,
                "aggregate": self.aggregate,
                "data_wait_seconds": self.data_wait_seconds,
                "decode_seconds": self.decode_seconds,
                "collate_seconds": self.collate_seconds,
                "valid_image_elements": self.valid_image_elements,
                "valid_token_elements": self.valid_token_elements,
                "valid_action_elements": self.valid_action_elements,
                "source_fingerprints": list(self.source_fingerprints),
                "transform_fingerprint": self.transform_fingerprint,
            }
        )
        return payload

    @property
    def fingerprint(self) -> str:
        """返回遥测字段和身份的稳定指纹。"""
        return stable_fingerprint(self.to_dict())

    @classmethod
    def from_training_batch(
        cls,
        batch: TrainingBatch,
        *,
        rank: int,
        world_size: int,
        fallback_dataset: str,
        requested_weights: Mapping[str, float],
        planned_source_fingerprints: tuple[str, ...],
        valid_image_elements: int,
        valid_token_elements: int,
        valid_action_elements: int,
    ) -> "DataTelemetryRecord":
        """从 canonical batch 与处理器有效掩码构造 rank-local 记录。"""
        raw_batch = cast(object, batch)
        if not isinstance(raw_batch, TrainingBatch):
            raise TypeError("data telemetry requires canonical TrainingBatch")
        batch = raw_batch
        if type(fallback_dataset) is not str or not fallback_dataset.strip():
            raise ValueError("fallback dataset identity must not be empty")
        if type(planned_source_fingerprints) is not tuple or any(
            type(value) is not str or not value.strip() for value in planned_source_fingerprints
        ):
            raise TypeError("planned source fingerprints must be a text tuple")
        samples_by_dataset: dict[str, int] = {}
        for source in batch.sample_source:
            raw_name = source.get("dataset", source.get("dataset_name", fallback_dataset))
            name = raw_name if isinstance(raw_name, str) and raw_name.strip() else fallback_dataset
            samples_by_dataset[name] = samples_by_dataset.get(name, 0) + 1
        samples_by_embodiment: dict[str, int] = {}
        if batch.embodiment is not None:
            for embodiment in batch.embodiment:
                samples_by_embodiment[embodiment] = samples_by_embodiment.get(embodiment, 0) + 1
        total = sum(samples_by_dataset.values())
        effective = {name: float(count / total) for name, count in samples_by_dataset.items()}
        requested = _normalize_weights(requested_weights, "requested_weights")
        deviations = {
            name: effective.get(name, 0.0) - requested.get(name, 0.0)
            for name in sorted(set(effective) | set(requested))
        }
        observed_sources = batch.source_fingerprints or planned_source_fingerprints
        return cls(
            rank=rank,
            world_size=world_size,
            aggregate="rank_local",
            samples_by_dataset=samples_by_dataset,
            batches_by_dataset={name: 1 for name in samples_by_dataset},
            samples_by_embodiment=samples_by_embodiment,
            batches_by_embodiment={name: 1 for name in samples_by_embodiment},
            requested_weights=requested,
            effective_weights=effective,
            balance_deviations=deviations,
            data_wait_seconds=0.0,
            valid_image_elements=valid_image_elements,
            valid_token_elements=valid_token_elements,
            valid_action_elements=valid_action_elements,
            source_fingerprints=tuple(sorted(set(observed_sources))),
            transform_fingerprint=batch.transform_fingerprint,
        )

    @classmethod
    def combine(
        cls,
        records: Sequence["DataTelemetryRecord"],
        *,
        rank: int,
        world_size: int,
        aggregate: str,
    ) -> "DataTelemetryRecord":
        """确定性合并连续 step 或多 rank 记录,计数求和且权重重算。"""
        values = tuple(records)
        if not values:
            raise ValueError("data telemetry reduction requires at least one record")
        if any(type(record) is not cls for record in values):
            raise TypeError("data telemetry reduction requires canonical records")
        transforms = {record.transform_fingerprint for record in values}
        if len(transforms) != 1:
            raise ValueError("data telemetry reduction requires one transform fingerprint")
        requested = dict(values[0].requested_weights)
        if any(dict(record.requested_weights) != requested for record in values[1:]):
            raise ValueError("data telemetry requested weights differ across records")

        def sum_counts(name: str) -> dict[str, int]:
            """按键求和一个计数字段。"""
            result: dict[str, int] = {}
            for record in values:
                mapping = cast(Mapping[str, int], getattr(record, name))
                for key, count in mapping.items():
                    result[key] = result.get(key, 0) + count
            return result

        samples_by_dataset = sum_counts("samples_by_dataset")
        total = sum(samples_by_dataset.values())
        effective = (
            {}
            if total == 0
            else {name: float(count / total) for name, count in samples_by_dataset.items()}
        )
        deviations = {
            name: effective.get(name, 0.0) - requested.get(name, 0.0)
            for name in sorted(set(effective) | set(requested))
        }

        def optional_total(name: str) -> float | None:
            """仅在全部记录提供计时时返回总耗时。"""
            timings = tuple(getattr(record, name) for record in values)
            if any(value is None for value in timings):
                return None
            return float(sum(cast(tuple[float, ...], timings)))

        return cls(
            rank=rank,
            world_size=world_size,
            aggregate=aggregate,
            samples_by_dataset=samples_by_dataset,
            batches_by_dataset=sum_counts("batches_by_dataset"),
            samples_by_embodiment=sum_counts("samples_by_embodiment"),
            batches_by_embodiment=sum_counts("batches_by_embodiment"),
            requested_weights=requested,
            effective_weights=effective,
            balance_deviations=deviations,
            skipped_by_reason=sum_counts("skipped_by_reason"),
            data_wait_seconds=float(sum(record.data_wait_seconds for record in values)),
            decode_seconds=optional_total("decode_seconds"),
            collate_seconds=optional_total("collate_seconds"),
            valid_image_elements=sum(record.valid_image_elements for record in values),
            valid_token_elements=sum(record.valid_token_elements for record in values),
            valid_action_elements=sum(record.valid_action_elements for record in values),
            source_fingerprints=tuple(
                sorted(
                    {fingerprint for record in values for fingerprint in record.source_fingerprints}
                )
            ),
            transform_fingerprint=next(iter(transforms)),
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "DataTelemetryRecord":
        """从 logger/checkpoint JSON 载荷严格恢复记录。"""
        expected = set(cls(0, 1, "rank_local").to_dict())
        if set(payload) != expected:
            raise ValueError("data telemetry fields are incomplete or unknown")

        def mapping(name: str) -> Mapping[str, object]:
            """读取字符串键 mapping 字段。"""
            value = payload[name]
            if not isinstance(value, Mapping):
                raise TypeError(f"data telemetry {name} must be a string-key mapping")
            raw_mapping = cast(Mapping[object, object], value)
            if not all(isinstance(key, str) for key in raw_mapping):
                raise TypeError(f"data telemetry {name} must be a string-key mapping")
            return cast(Mapping[str, object], raw_mapping)

        raw_sources = payload["source_fingerprints"]
        if type(raw_sources) is not list or not all(
            type(value) is str for value in cast(Sequence[object], raw_sources)
        ):
            raise TypeError("data telemetry source_fingerprints must be a string list")
        return cls(
            rank=cast(int, payload["rank"]),
            world_size=cast(int, payload["world_size"]),
            aggregate=cast(str, payload["aggregate"]),
            samples_by_dataset=cast(Mapping[str, int], mapping("samples_by_dataset")),
            batches_by_dataset=cast(Mapping[str, int], mapping("batches_by_dataset")),
            samples_by_embodiment=cast(Mapping[str, int], mapping("samples_by_embodiment")),
            batches_by_embodiment=cast(Mapping[str, int], mapping("batches_by_embodiment")),
            requested_weights=cast(Mapping[str, float], mapping("requested_weights")),
            effective_weights=cast(Mapping[str, float], mapping("effective_weights")),
            balance_deviations=cast(Mapping[str, float], mapping("balance_deviations")),
            skipped_by_reason=cast(Mapping[str, int], mapping("skipped_by_reason")),
            data_wait_seconds=cast(float, payload["data_wait_seconds"]),
            decode_seconds=cast(float | None, payload["decode_seconds"]),
            collate_seconds=cast(float | None, payload["collate_seconds"]),
            valid_image_elements=cast(int, payload["valid_image_elements"]),
            valid_token_elements=cast(int, payload["valid_token_elements"]),
            valid_action_elements=cast(int, payload["valid_action_elements"]),
            source_fingerprints=tuple(cast(Sequence[str], raw_sources)),
            transform_fingerprint=cast(str, payload["transform_fingerprint"]),
        )


__all__ = ["DATA_TELEMETRY_SCHEMA", "DataTelemetryRecord"]
