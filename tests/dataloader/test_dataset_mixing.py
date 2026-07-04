"""Dataset mixing substrate 测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from autovla.dataloader.backends import DataSourceSpec
from autovla.dataloader.mixing import (
    DatasetMixSpec,
    DeterministicRoundRobinMixScheduler,
    MixPlanValidationError,
    SourceRatioSpec,
    WeightedDeterministicMixScheduler,
)


def _source(source_id: str, backend: str = "synthetic") -> DataSourceSpec:
    """构造不读取数据的 source spec。"""
    return DataSourceSpec(
        source_id=source_id,
        backend=backend,
        input_root=Path(f"/datasets/readonly/{source_id}"),
        layout="metadata_only",
        fingerprint=f"fp-{source_id}",
    )


def test_dataset_mix_spec_normalizes_ratios_deterministically() -> None:
    """正权重 source ratio 应稳定归一化为表格行。"""
    spec = DatasetMixSpec(
        sources=(_source("raw"), _source("wds", "webdataset_tar")),
        ratios=(SourceRatioSpec("raw", 2), SourceRatioSpec("wds", 1)),
        seed=7,
        total_steps=3,
        batch_size=6,
    )

    rows = spec.to_table_rows()

    assert [row["source_id"] for row in rows] == ["raw", "wds"]
    assert rows[0]["normalized_ratio"] == pytest.approx(2 / 3)
    assert rows[1]["normalized_ratio"] == pytest.approx(1 / 3)
    assert rows[0]["planned_samples"] == 12
    assert rows[1]["planned_samples"] == 6
    assert rows[0]["balance_status"] == "PLANNED_NO_DATA_READ"


def test_dataset_mix_spec_rejects_non_positive_ratios() -> None:
    """混合权重必须为正, 防止静默丢 source。"""
    with pytest.raises(MixPlanValidationError, match="positive"):
        DatasetMixSpec(
            sources=(_source("raw"),),
            ratios=(SourceRatioSpec("raw", 0),),
            seed=1,
            total_steps=2,
            batch_size=2,
        )


def test_mix_schedulers_are_deterministic_without_dataloader() -> None:
    """调度器只产出计划, 不创建 DataLoader 或 multiprocessing。"""
    spec = DatasetMixSpec(
        sources=(_source("a"), _source("b")),
        ratios=(SourceRatioSpec("a", 1), SourceRatioSpec("b", 1)),
        seed=11,
        total_steps=6,
        batch_size=4,
    )

    rr = DeterministicRoundRobinMixScheduler().plan(spec)
    weighted_first = WeightedDeterministicMixScheduler().plan(spec)
    weighted_second = WeightedDeterministicMixScheduler().plan(spec)

    assert [row.source_id for row in rr] == ["a", "b", "a", "b", "a", "b"]
    assert weighted_first == weighted_second
    assert all(row.planned_batch_size == 4 for row in weighted_first)
