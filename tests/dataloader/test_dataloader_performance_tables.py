"""DataLoader synthetic 性能表契约测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autovla.dataloader.perf.synthetic import (
    SyntheticDataloaderBenchmarkConfig,
    run_synthetic_dataloader_benchmark,
)

EXPECTED_TABLES = {
    "benchmark_matrix",
    "throughput_summary",
    "stage_latency",
    "data_io_summary",
    "regression_gate",
    "missing_telemetry",
    "performance_environment",
}


def test_synthetic_dataloader_benchmark_should_emit_required_tables(tmp_path: Path) -> None:
    """验证 synthetic backend 生成七张稳定性能表。"""
    result = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "tables",
            table_formats=("json", "csv", "md"),
        )
    )

    assert set(result.tables) == EXPECTED_TABLES
    assert result.files["json"].is_file()
    payload = json.loads(result.files["json"].read_text(encoding="utf-8"))

    assert payload["schema_version"] == "autovla.dataloader_perf_tables.v1"
    assert {table["name"] for table in payload["tables"]} == EXPECTED_TABLES
    assert payload["summary"]["backend"] == "synthetic"
    assert payload["summary"]["fixture"] == "tiny"


@pytest.mark.parametrize(
    "metric",
    (
        "samples_per_second",
        "batch_latency_ms_p50",
        "batch_latency_ms_p95",
        "batch_latency_ms_max",
        "input_prepare_ms_p50",
        "collate_ms_p50",
        "object_assembly_ms_p50",
        "artifact_write_ms_p50",
        "file_open_count",
        "bytes_read",
        "bytes_written",
        "missing_telemetry",
    ),
)
def test_synthetic_dataloader_tables_should_cover_required_metrics(
    tmp_path: Path,
    metric: str,
) -> None:
    """验证必需指标全部进入表格。"""
    result = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "metrics",
        )
    )
    metrics = {
        row["metric"] for table in result.tables.values() for row in table.rows if "metric" in row
    }

    assert metric in metrics


def test_synthetic_dataloader_benchmark_should_reject_real_runtime_scope(
    tmp_path: Path,
) -> None:
    """验证 Stage 3 scaffold 拒绝非 synthetic 范围。"""
    with pytest.raises(ValueError, match="fixture"):
        SyntheticDataloaderBenchmarkConfig(
            fixture="real_dataset",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "bad",
        )
    with pytest.raises(ValueError, match="max_samples"):
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=0,
            batch_size=4,
            output_dir=tmp_path / "bad",
        )
    with pytest.raises(ValueError, match="batch_size"):
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=True,  # type: ignore[arg-type]
            output_dir=tmp_path / "bad",
        )
