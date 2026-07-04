"""训练 benchmark CLI 测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """运行训练 CLI 子进程。"""
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.cli", *args],
        capture_output=True,
        check=False,
        text=True,
    )


def test_cli_benchmark_should_emit_required_table_paths(tmp_path: Path) -> None:
    """验证 benchmark CLI 产出结构化性能表路径。"""
    result = _run_cli(
        "benchmark",
        "--family",
        "gr00t-n1d6",
        "--fixture",
        "tiny",
        "--steps",
        "8",
        "--warmup-steps",
        "2",
        "--repeats",
        "3",
        "--output-dir",
        str(tmp_path),
        "--table-format",
        "json,csv,md",
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "benchmark"
    assert "throughput_summary" in payload["tables"]
    for path in payload["files"].values():
        resolved = Path(path).resolve()
        assert resolved.is_file()
        assert resolved.is_relative_to(tmp_path.resolve())


def test_cli_benchmark_should_reject_invalid_config_without_partial_outputs(tmp_path: Path) -> None:
    """验证 CLI 配置错误返回 2 且不写表格。"""
    result = _run_cli(
        "benchmark",
        "--family",
        "gr00t-n1d6",
        "--fixture",
        "tiny",
        "--steps",
        "0",
        "--warmup-steps",
        "2",
        "--repeats",
        "3",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 2
    assert "steps" in result.stderr
    assert not (tmp_path / "performance_raw.json").exists()


def test_cli_benchmark_should_keep_external_effects_out_of_surface(tmp_path: Path) -> None:
    """验证 CLI 帮助和输出不暴露真实训练/GPU/Slurm 入口。"""
    help_result = _run_cli("benchmark", "--help")
    assert help_result.returncode == 0
    assert "benchmark" in help_result.stdout
    assert "slurm" not in help_result.stdout.lower()
    assert "gpu" not in help_result.stdout.lower()
    assert "wandb" not in help_result.stdout.lower()
