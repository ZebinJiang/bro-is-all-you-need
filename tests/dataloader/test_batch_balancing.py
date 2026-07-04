"""Batch balancing substrate 测试。"""

from __future__ import annotations

from pathlib import Path

from autovla.dataloader.backends import DataSourceSpec
from autovla.dataloader.balancing import BalancedBatchRequest, BatchBalancePlan


def test_batch_balance_plan_is_deterministic_and_table_shaped() -> None:
    """Batch balance 只计划 source 配额, 不读取样本。"""
    sources = (
        DataSourceSpec(
            source_id="raw",
            backend="raw_zjh",
            input_root=Path("/datasets/readonly/raw"),
            layout="raw_zjh_metadata",
            fingerprint="raw-fp",
        ),
        DataSourceSpec(
            source_id="wds",
            backend="webdataset_tar",
            input_root=Path("/datasets/readonly/wds"),
            layout="tar_shards",
            fingerprint="wds-fp",
        ),
    )
    plan = BatchBalancePlan(
        request=BalancedBatchRequest(batch_size=8, total_steps=2, seed=3),
        sources=sources,
    )

    rows = plan.to_table_rows()

    assert rows == (
        {
            "backend": "raw_zjh",
            "balance_status": "PLANNED_NO_DATA_READ",
            "missing_data_status": "metadata_probe_required",
            "planned_batches": 2,
            "planned_samples": 8,
            "requested_ratio": 0.5,
            "normalized_ratio": 0.5,
            "source_id": "raw",
        },
        {
            "backend": "webdataset_tar",
            "balance_status": "PLANNED_NO_DATA_READ",
            "missing_data_status": "metadata_probe_required",
            "planned_batches": 2,
            "planned_samples": 8,
            "requested_ratio": 0.5,
            "normalized_ratio": 0.5,
            "source_id": "wds",
        },
    )
