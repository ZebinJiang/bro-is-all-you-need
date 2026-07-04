"""Batch balancing 计划 substrate, 不创建真实 DataLoader。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.dataloader.backends import DataSourceSpec


@dataclass(frozen=True, slots=True)
class BalancedBatchRequest:
    """描述 batch balancing 请求。"""

    batch_size: int
    total_steps: int
    seed: int

    def __post_init__(self) -> None:
        """校验请求参数。"""
        if type(self.batch_size) is not int or self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if type(self.total_steps) is not int or self.total_steps <= 0:
            raise ValueError("total_steps must be positive")
        if type(self.seed) is not int or self.seed < 0:
            raise ValueError("seed must be a non-negative int")


@dataclass(frozen=True, slots=True)
class BalancedBatchPlan:
    """单 source 的 batch balance 行。"""

    source_id: str
    backend: str
    requested_ratio: float
    normalized_ratio: float
    planned_samples: int
    planned_batches: int
    balance_status: str
    missing_data_status: str

    def to_table_row(self) -> dict[str, object]:
        """返回稳定表格行。"""
        return {
            "backend": self.backend,
            "balance_status": self.balance_status,
            "missing_data_status": self.missing_data_status,
            "planned_batches": self.planned_batches,
            "planned_samples": self.planned_samples,
            "requested_ratio": self.requested_ratio,
            "normalized_ratio": self.normalized_ratio,
            "source_id": self.source_id,
        }


@dataclass(frozen=True, slots=True)
class BatchBalancePlan:
    """多个 source 的 deterministic batch balance 计划。"""

    request: BalancedBatchRequest
    sources: tuple[DataSourceSpec, ...]

    def __post_init__(self) -> None:
        """校验 source 非空。"""
        if not self.sources:
            raise ValueError("sources must not be empty")

    def plans(self) -> tuple[BalancedBatchPlan, ...]:
        """生成每个 source 的 balance 计划。"""
        ratio = 1.0 / len(self.sources)
        planned_samples = round(self.request.batch_size * self.request.total_steps * ratio)
        return tuple(
            BalancedBatchPlan(
                source_id=source.source_id,
                backend=source.backend,
                requested_ratio=ratio,
                normalized_ratio=ratio,
                planned_samples=planned_samples,
                planned_batches=self.request.total_steps,
                balance_status="PLANNED_NO_DATA_READ",
                missing_data_status="metadata_probe_required",
            )
            for source in sorted(self.sources, key=lambda item: item.source_id)
        )

    def to_table_rows(self) -> tuple[dict[str, object], ...]:
        """返回 batch_balance_plan_table 行。"""
        return tuple(plan.to_table_row() for plan in self.plans())
