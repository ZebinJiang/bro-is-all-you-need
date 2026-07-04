"""DataBackend bakeoff 报告稳定性测试。"""

from __future__ import annotations

import json
from pathlib import Path

from autovla.dataloader.perf.bakeoff import DataBackendBakeoffConfig, run_backend_bakeoff


def test_bakeoff_reports_should_be_deterministic(tmp_path: Path) -> None:
    """验证 bakeoff 输出对相同输入字节稳定。"""
    first = run_backend_bakeoff(
        DataBackendBakeoffConfig(
            backends=("synthetic",),
            input_root=tmp_path / "missing",
            max_samples=4,
            max_files=8,
            max_bytes_read=4096,
            output_dir=tmp_path / "first",
            table_format=("json", "csv", "md"),
            allow_missing_input_root=True,
        )
    )
    second = run_backend_bakeoff(
        DataBackendBakeoffConfig(
            backends=("synthetic",),
            input_root=tmp_path / "missing",
            max_samples=4,
            max_files=8,
            max_bytes_read=4096,
            output_dir=tmp_path / "second",
            table_format=("json", "csv", "md"),
            allow_missing_input_root=True,
        )
    )

    assert first.summary["backend_count"] == 1
    assert (first.output_dir / "backend_bakeoff_raw.json").read_text().replace(
        str(first.output_dir), "<out>"
    ) == (second.output_dir / "backend_bakeoff_raw.json").read_text().replace(
        str(second.output_dir), "<out>"
    )


def test_bakeoff_reports_should_include_required_tables(tmp_path: Path) -> None:
    """验证输出表格覆盖 prompt 指定表面。"""
    result = run_backend_bakeoff(
        DataBackendBakeoffConfig(
            backends=("synthetic", "raw_zjh"),
            input_root=tmp_path / "missing",
            max_samples=4,
            max_files=8,
            max_bytes_read=4096,
            output_dir=tmp_path / "out",
            table_format=("json", "csv", "md"),
            allow_missing_input_root=True,
        )
    )
    payload = json.loads((result.output_dir / "backend_bakeoff_raw.json").read_text())

    assert set(payload["tables"]) >= {
        "backend_environment_table",
        "backend_io_table",
        "backend_latency_table",
        "backend_probe_matrix",
        "dataset_preview_table",
        "missing_telemetry_table",
        "reuse_license_table",
    }
    assert payload["summary"]["bytes_written"] >= 0
    assert payload["summary"]["no_dataset_mutation"] is True
