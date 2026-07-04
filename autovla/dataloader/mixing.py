"""Dataset mixing 计划 substrate, 不读取真实数据。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from autovla.dataloader.backends import DataSourceSpec


class MixPlanValidationError(ValueError):
    """Dataset mixing 计划校验错误。"""


@dataclass(frozen=True, slots=True)
class SourceWeight:
    """表示 source 的正权重。"""

    source_id: str
    weight: float

    def __post_init__(self) -> None:
        """校验权重为正。"""
        if not self.source_id.strip():
            raise MixPlanValidationError("source_id must not be empty")
        if self.weight <= 0:
            raise MixPlanValidationError("source weight must be positive")


@dataclass(frozen=True, slots=True)
class SourceRatioSpec(SourceWeight):
    """DatasetMixSpec 使用的 source ratio。"""


@dataclass(frozen=True, slots=True)
class SourcePlanRow:
    """单个 step 的 source 计划行。"""

    step: int
    source_id: str
    backend: str
    planned_batch_size: int


@dataclass(frozen=True, slots=True)
class DatasetMixSpec:
    """描述多个 DataSourceSpec 的 deterministic mixing 计划。"""

    sources: tuple[DataSourceSpec, ...]
    ratios: tuple[SourceRatioSpec, ...]
    seed: int
    total_steps: int
    batch_size: int
    streaming_runtime_future: str = "inactive"
    fsdp_runtime_plan_future: str = "inactive"

    def __post_init__(self) -> None:
        """校验 source/ratio 一一对应且运行参数有效。"""
        if not self.sources:
            raise MixPlanValidationError("sources must not be empty")
        if type(self.seed) is not int or self.seed < 0:
            raise MixPlanValidationError("seed must be a non-negative int")
        if type(self.total_steps) is not int or self.total_steps <= 0:
            raise MixPlanValidationError("total_steps must be positive")
        if type(self.batch_size) is not int or self.batch_size <= 0:
            raise MixPlanValidationError("batch_size must be positive")
        source_ids = {source.source_id for source in self.sources}
        ratio_ids = {ratio.source_id for ratio in self.ratios}
        if source_ids != ratio_ids:
            raise MixPlanValidationError("ratios must cover every source exactly")
        for ratio in self.ratios:
            if ratio.weight <= 0:
                raise MixPlanValidationError("ratios must be positive")

    def normalized_ratios(self) -> dict[str, float]:
        """返回稳定归一化 ratio。"""
        total = sum(ratio.weight for ratio in self.ratios)
        return {ratio.source_id: ratio.weight / total for ratio in self.ratios}

    def to_table_rows(self) -> tuple[dict[str, object], ...]:
        """返回 source mix plan 表格行。"""
        normalized = self.normalized_ratios()
        source_by_id = {source.source_id: source for source in self.sources}
        rows: list[dict[str, object]] = []
        for ratio in sorted(self.ratios, key=lambda item: item.source_id):
            planned_samples = round(
                normalized[ratio.source_id] * self.total_steps * self.batch_size
            )
            source = source_by_id[ratio.source_id]
            rows.append(
                {
                    "backend": source.backend,
                    "balance_status": "PLANNED_NO_DATA_READ",
                    "missing_data_status": "metadata_probe_required",
                    "normalized_ratio": normalized[ratio.source_id],
                    "planned_batches": self.total_steps,
                    "planned_samples": planned_samples,
                    "requested_ratio": ratio.weight,
                    "source_id": ratio.source_id,
                }
            )
        return tuple(rows)


class MixScheduler(Protocol):
    """Dataset mix scheduler 协议。"""

    def plan(self, spec: DatasetMixSpec) -> tuple[SourcePlanRow, ...]:
        """返回 step 级 source 计划。"""
        ...


@dataclass(frozen=True, slots=True)
class DeterministicRoundRobinMixScheduler:
    """按 source 顺序轮转的 deterministic scheduler。"""

    def plan(self, spec: DatasetMixSpec) -> tuple[SourcePlanRow, ...]:
        """生成 round-robin source 计划。"""
        ordered = tuple(sorted(spec.sources, key=lambda source: source.source_id))
        return tuple(
            SourcePlanRow(
                step=step,
                source_id=ordered[step % len(ordered)].source_id,
                backend=ordered[step % len(ordered)].backend,
                planned_batch_size=spec.batch_size,
            )
            for step in range(spec.total_steps)
        )


@dataclass(frozen=True, slots=True)
class WeightedDeterministicMixScheduler:
    """按归一化权重展开固定序列的 deterministic scheduler。"""

    def plan(self, spec: DatasetMixSpec) -> tuple[SourcePlanRow, ...]:
        """生成 deterministic weighted source 计划。"""
        normalized = spec.normalized_ratios()
        source_by_id = {source.source_id: source for source in spec.sources}
        quotas = {
            source_id: max(1, round(ratio * spec.total_steps))
            for source_id, ratio in normalized.items()
        }
        sequence: list[str] = []
        for source_id in sorted(quotas):
            sequence.extend([source_id] * quotas[source_id])
        if not sequence:
            raise MixPlanValidationError("weighted sequence must not be empty")
        return tuple(
            SourcePlanRow(
                step=step,
                source_id=sequence[(step + spec.seed) % len(sequence)],
                backend=source_by_id[sequence[(step + spec.seed) % len(sequence)]].backend,
                planned_batch_size=spec.batch_size,
            )
            for step in range(spec.total_steps)
        )
