"""M3 本地 runner dry-run JSON 配置与 CLI 测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest

from genesisvla.training.config import (
    LocalRunnerDryRunConfig,
    load_local_runner_dry_run_config,
)
from genesisvla.training.local_runner import LocalRunnerConfig


def _valid_config(tmp_path: Path) -> dict[str, object]:
    """返回完整且只写 tmp_path 的 dry-run JSON 配置。"""
    return {
        "run_id": "tiny-dry-run",
        "seed": 17,
        "model_registry_key": "deterministic-test-framework",
        "dataset_fingerprint": "dataset-a",
        "transform_fingerprint": "transform-a",
        "statistics_fingerprint": "stats-a",
        "action_horizon": 2,
        "action_dim": 3,
        "max_steps": 2,
        "output_dir": str(tmp_path / "runs"),
        "mode": "dry-run",
    }


def _write_config(path: Path, payload: dict[str, object]) -> Path:
    """写入稳定 JSON 配置。"""
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def test_load_config_should_build_local_runner_config(tmp_path: Path) -> None:
    """验证 JSON 配置会转换为 LocalRunnerConfig。"""
    path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))

    config = load_local_runner_dry_run_config(path)
    local_runner_config = config.to_local_runner_config()

    assert isinstance(config, LocalRunnerDryRunConfig)
    assert isinstance(local_runner_config, LocalRunnerConfig)
    assert local_runner_config.run_id == "tiny-dry-run"
    assert local_runner_config.seed == 17
    assert local_runner_config.max_steps == 2
    assert local_runner_config.run_root == tmp_path / "runs"
    assert config.action_horizon == 2
    assert config.action_dim == 3


@pytest.mark.parametrize(
    ("field", "value", "message"),
    (
        ("dataset_fingerprint", "", "dataset_fingerprint.*empty"),
        ("transform_fingerprint", "  ", "transform_fingerprint.*empty"),
        ("statistics_fingerprint", "", "statistics_fingerprint.*empty"),
        ("seed", True, "seed.*int"),
        ("seed", "17", "seed.*int"),
        ("seed", -1, "seed.*non-negative"),
        ("action_horizon", 0, "action_horizon.*positive"),
        ("action_horizon", True, "action_horizon.*int"),
        ("action_dim", 0, "action_dim.*positive"),
        ("max_steps", 0, "max_steps.*positive"),
        ("mode", "train", "mode.*dry-run"),
    ),
)
def test_load_config_should_reject_invalid_fields(
    tmp_path: Path,
    field: str,
    value: object,
    message: str,
) -> None:
    """验证字段级错误拒绝无效 JSON 值。"""
    payload = _valid_config(tmp_path)
    payload[field] = value
    path = _write_config(tmp_path / "config.json", payload)

    with pytest.raises(ValueError, match=message):
        load_local_runner_dry_run_config(path)


def test_load_config_should_reject_invalid_json(tmp_path: Path) -> None:
    """验证非法 JSON 会以配置错误返回。"""
    path = tmp_path / "broken.json"
    path.write_text("{not-json", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_local_runner_dry_run_config(path)


def test_load_config_should_reject_missing_and_unknown_fields(tmp_path: Path) -> None:
    """验证缺失字段和未知字段不会被静默接受。"""
    missing = _valid_config(tmp_path)
    del missing["run_id"]
    with pytest.raises(ValueError, match="missing required field: run_id"):
        load_local_runner_dry_run_config(_write_config(tmp_path / "missing.json", missing))

    unknown = _valid_config(tmp_path)
    unknown["extra"] = "nope"
    with pytest.raises(ValueError, match="unknown config field: extra"):
        load_local_runner_dry_run_config(_write_config(tmp_path / "unknown.json", unknown))


def test_cli_dry_run_should_write_manifest_under_tmp_path(tmp_path: Path) -> None:
    """验证模块 CLI 成功 dry-run 并只写 tmp_path 下 manifest。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_dir = tmp_path / "override-runs"
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "genesisvla.training.cli",
            "--config",
            str(config_path),
            "--dry-run",
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=tmp_path,
        env=env,
    )

    assert result.returncode == 0
    stdout = json.loads(result.stdout)
    manifest_path = Path(cast(str, stdout["manifest_path"]))
    assert manifest_path == output_dir / "tiny-dry-run" / "dry_run_manifest.json"
    assert manifest_path.is_file()
    assert manifest_path.resolve().is_relative_to(tmp_path.resolve())
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["dry_run"] is True
    assert manifest["mode"] == "dry-run"
    assert manifest["local_runner_config"]["seed"] == 17


def test_cli_should_return_nonzero_for_validation_failure(tmp_path: Path) -> None:
    """验证 CLI 配置错误返回非零退出码且不写 manifest。"""
    payload = _valid_config(tmp_path)
    payload["seed"] = "17"
    config_path = _write_config(tmp_path / "config.json", payload)

    from genesisvla.training.cli import main

    exit_code = main(["--config", str(config_path), "--dry-run"])

    assert exit_code == 2
    assert not (tmp_path / "runs" / "tiny-dry-run" / "dry_run_manifest.json").exists()
