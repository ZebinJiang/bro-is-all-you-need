"""DataLoader synthetic 性能表 CLI 测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_synthetic_benchmark_should_emit_table_paths(tmp_path: Path) -> None:
    """验证 CLI 可生成 synthetic table scaffold。"""
    output_dir = tmp_path / "cli"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "benchmark",
            "--backend",
            "synthetic",
            "--fixture",
            "tiny",
            "--max-samples",
            "64",
            "--batch-size",
            "4",
            "--output-dir",
            str(output_dir),
            "--table-format",
            "json,csv,md",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "dataloader_performance_tables.json" in completed.stdout
    payload = json.loads((output_dir / "dataloader_performance_tables.json").read_text())
    assert payload["summary"]["backend"] == "synthetic"


def test_cli_synthetic_benchmark_should_reject_real_runtime_request(
    tmp_path: Path,
) -> None:
    """验证 CLI 拒绝非 synthetic fixture 且不产生局部产物。"""
    output_dir = tmp_path / "bad"
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "benchmark",
            "--backend",
            "synthetic",
            "--fixture",
            "real_dataset",
            "--max-samples",
            "64",
            "--batch-size",
            "4",
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "fixture" in completed.stderr
    assert not output_dir.exists()


def test_cli_synthetic_benchmark_help_should_not_expose_external_effects() -> None:
    """验证 synthetic benchmark help 不承诺外部 runtime。"""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "benchmark",
            "--help",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0
    assert "--backend" in completed.stdout
    assert "--table-format" in completed.stdout
    assert "wandb" not in completed.stdout.lower()
    assert "slurm" not in completed.stdout.lower()
