"""DataBackend bakeoff CLI 测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_bakeoff_should_emit_required_reports_for_missing_root(tmp_path: Path) -> None:
    """验证缺失 input_root 时可生成有界审查报告而不读取数据。"""
    output_dir = tmp_path / "out"
    missing_root = tmp_path / "missing"

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "bakeoff",
            "--backend",
            "synthetic,raw_zjh,lerobot_local,webdataset_tar",
            "--input-root",
            str(missing_root),
            "--max-samples",
            "4",
            "--max-files",
            "8",
            "--max-bytes-read",
            "4096",
            "--output-dir",
            str(output_dir),
            "--table-format",
            "json,csv,md",
            "--allow-missing-input-root",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stderr
    assert "backend_bakeoff_raw.json" in completed.stdout
    required = {
        "backend_bakeoff_raw.json",
        "backend_bakeoff_summary.csv",
        "backend_bakeoff_summary.md",
        "backend_probe_matrix.md",
        "dataset_preview_table.md",
        "backend_latency_table.md",
        "backend_io_table.md",
        "missing_telemetry_table.md",
        "backend_environment_table.md",
        "reuse_license_table.md",
    }
    assert required <= {path.name for path in output_dir.iterdir()}

    payload = json.loads((output_dir / "backend_bakeoff_raw.json").read_text())
    assert payload["schema_version"] == "autovla.databackend_bakeoff.v1"
    assert set(payload["results"]) == {
        "lerobot_local",
        "raw_zjh",
        "synthetic",
        "webdataset_tar",
    }
    assert payload["summary"]["no_media_decode"] is True


def test_cli_bakeoff_should_reject_media_decode_request(tmp_path: Path) -> None:
    """验证 CLI 不允许媒体解码进入本 tranche。"""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "bakeoff",
            "--backend",
            "raw_zjh",
            "--input-root",
            str(tmp_path),
            "--output-dir",
            str(tmp_path / "out"),
            "--decode-media",
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "decode_media" in completed.stderr
    assert not (tmp_path / "out").exists()


def test_cli_bakeoff_should_reject_missing_root_without_allow_flag(tmp_path: Path) -> None:
    """验证缺失 input_root 默认失败, 防止误把无数据 probe 当成真实通过。"""
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.dataloader.perf",
            "bakeoff",
            "--backend",
            "raw_zjh",
            "--input-root",
            str(tmp_path / "missing"),
            "--output-dir",
            str(tmp_path / "out"),
        ],
        check=False,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 2
    assert "allow-missing-input-root" in completed.stderr
    assert not (tmp_path / "out").exists()
