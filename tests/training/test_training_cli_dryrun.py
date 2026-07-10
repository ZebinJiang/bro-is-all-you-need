"""训练 runner dry-run CLI 测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    """运行 CLI 子进程。"""
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.cli", *args],
        check=False,
        text=True,
        capture_output=True,
    )


def test_cli_dry_run_should_emit_manifest_paths(tmp_path: Path) -> None:
    """验证 CLI dry-run 产出确定性 JSON 文件。"""
    result = _run_cli(
        "dry-run",
        "--family",
        "gr00t-n1d6",
        "--fixture",
        "tiny",
        "--steps",
        "2",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "cpu_dry_run"
    assert payload["family_key"] == "gr00t-n1d6"
    assert Path(payload["files"]["efficiency_telemetry"]).is_file()
    assert Path(payload["files"]["checkpoint_manifest"]).is_file()


def test_cli_dry_run_should_reject_invalid_family(tmp_path: Path) -> None:
    """验证未知模型族返回字段级错误。"""
    result = _run_cli(
        "dry-run",
        "--family",
        "missing-family",
        "--fixture",
        "tiny",
        "--steps",
        "2",
        "--output-dir",
        str(tmp_path),
    )

    assert result.returncode == 2
    assert "family" in result.stderr
    assert "missing-family" in result.stderr


def test_cli_dry_run_should_reject_output_file(tmp_path: Path) -> None:
    """验证 output-dir 指向文件时 fail closed。"""
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("x", encoding="utf-8")

    result = _run_cli(
        "dry-run",
        "--family",
        "gr00t-n1d6",
        "--fixture",
        "tiny",
        "--steps",
        "2",
        "--output-dir",
        str(output_file),
    )

    assert result.returncode == 2
    assert "output_dir" in result.stderr


def test_cli_should_run_both_modular_presets(tmp_path: Path) -> None:
    """验证两个显式 preset 通过同一 dry-run 子命令。"""
    expected = (
        ("modular_skeleton_webdataset.yaml", "webdataset_tar"),
        ("modular_skeleton_robodm.yaml", "robodm_container_v1"),
    )
    for config_name, backend in expected:
        result = _run_cli(
            "dry-run",
            "--config",
            f"configs/training/{config_name}",
            "--output-dir",
            str(tmp_path / backend),
        )
        assert result.returncode == 0, result.stderr
        payload = json.loads(result.stdout)
        assert payload["backend"] == backend
        assert payload["model_metadata_key"] == "test_double"
        assert payload["status"] == "PASS_DRY_RUN"
        assert payload["step_count"] == 2
