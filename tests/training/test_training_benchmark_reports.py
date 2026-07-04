"""训练 benchmark 报告产物测试。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from autovla.training.benchmark import TrainingBenchmarkConfig, run_training_benchmark


def _config(output_dir: Path) -> TrainingBenchmarkConfig:
    """构造测试用 benchmark 配置。"""
    return TrainingBenchmarkConfig(
        family_key="gr00t-n1d6",
        fixture="tiny",
        output_dir=output_dir,
        repeats=3,
        steps=8,
        warmup_steps=2,
    )


def _read_json(path: Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8"))


def test_benchmark_should_write_required_structured_reports(tmp_path: Path) -> None:
    """验证 benchmark 写出所有要求的结构化表格产物。"""
    result = run_training_benchmark(_config(tmp_path))

    assert set(result.files) == {
        "missing_telemetry_table",
        "performance_environment_table",
        "performance_gate_table",
        "performance_raw",
        "performance_summary_csv",
        "performance_summary_md",
    }
    for path in result.files.values():
        assert path.is_file()
        assert path.resolve().is_relative_to(tmp_path.resolve())
        assert path.stat().st_size < 20000

    raw = _read_json(result.files["performance_raw"])
    assert sorted(raw["tables"]) == [
        "benchmark_matrix",
        "data_io_summary",
        "missing_telemetry",
        "performance_environment",
        "regression_gate",
        "stage_latency",
        "throughput_summary",
    ]
    assert raw["benchmark"]["mode"] == "benchmark"
    assert len(raw["repeats"]) == 3
    assert "Throughput Summary" in result.files["performance_summary_md"].read_text(
        encoding="utf-8"
    )
    assert "SYNTHETIC_ONLY" in result.files["missing_telemetry_table"].read_text(encoding="utf-8")


def test_benchmark_should_be_byte_deterministic(tmp_path: Path) -> None:
    """验证 synthetic clock benchmark 的公开表格可字节级复现。"""
    first = run_training_benchmark(_config(tmp_path / "first"))
    second = run_training_benchmark(_config(tmp_path / "second"))

    for name in (
        "performance_raw",
        "performance_summary_csv",
        "performance_summary_md",
        "performance_gate_table",
        "missing_telemetry_table",
        "performance_environment_table",
    ):
        assert first.files[name].read_bytes() == second.files[name].read_bytes()


def test_benchmark_config_should_reject_real_runtime_scope(tmp_path: Path) -> None:
    """验证 benchmark 配置 fail closed 到 tiny/gr00t-n1d6/synthetic 范围。"""
    bad_output = tmp_path / "not-a-dir"
    bad_output.write_text("x", encoding="utf-8")

    cases = [
        {"family_key": "pi0-roadmap"},
        {"fixture": "real-dataset"},
        {"steps": 0},
        {"warmup_steps": -1},
        {"repeats": 0},
        {"table_formats": ("html",)},
        {"output_dir": bad_output},
    ]
    for override in cases:
        kwargs: dict[str, object] = {
            "family_key": "gr00t-n1d6",
            "fixture": "tiny",
            "output_dir": tmp_path,
            "repeats": 1,
            "steps": 1,
            "warmup_steps": 0,
        }
        kwargs.update(override)
        try:
            TrainingBenchmarkConfig(**kwargs)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        raise AssertionError(f"case should fail closed: {override}")
