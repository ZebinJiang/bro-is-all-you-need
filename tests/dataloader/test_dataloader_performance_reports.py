"""DataLoader synthetic 性能报告产物测试。"""

from __future__ import annotations

from pathlib import Path

from autovla.dataloader.perf.synthetic import (
    SyntheticDataloaderBenchmarkConfig,
    run_synthetic_dataloader_benchmark,
)


def test_synthetic_dataloader_reports_should_be_byte_deterministic(
    tmp_path: Path,
) -> None:
    """验证相同输入生成 byte-identical 报告。"""
    first = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "first",
            table_formats=("json", "csv", "md"),
        )
    )
    second = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "second",
            table_formats=("json", "csv", "md"),
        )
    )

    assert first.files["json"].read_bytes() == second.files["json"].read_bytes()
    assert first.files["csv"].read_bytes() == second.files["csv"].read_bytes()
    assert first.files["md"].read_bytes() == second.files["md"].read_bytes()


def test_synthetic_dataloader_reports_should_stay_under_output_dir(
    tmp_path: Path,
) -> None:
    """验证产物只写入 output_dir。"""
    output_dir = tmp_path / "scoped"
    result = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=output_dir,
            table_formats=("json", "csv", "md"),
        )
    )

    resolved_output = output_dir.resolve()
    for path in result.files.values():
        assert path.resolve().is_relative_to(resolved_output)

    assert sorted(path.name for path in output_dir.iterdir()) == [
        "dataloader_performance_tables.csv",
        "dataloader_performance_tables.json",
        "dataloader_performance_tables.md",
    ]


def test_synthetic_dataloader_markdown_should_state_non_goal_boundaries(
    tmp_path: Path,
) -> None:
    """验证 Markdown 报告明确记录非真实数据/训练证据。"""
    result = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture="tiny",
            max_samples=64,
            batch_size=4,
            output_dir=tmp_path / "md",
            table_formats=("md",),
        )
    )

    report = result.files["md"].read_text(encoding="utf-8")

    assert "Benchmark Matrix" in report
    assert "synthetic_metadata_only" in report
    assert "No real dataset read" in report
    assert "No GPU, Slurm, W&B, Hugging Face, endpoint, or robot action" in report
