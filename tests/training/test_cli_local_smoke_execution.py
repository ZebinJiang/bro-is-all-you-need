"""M3 CLI local-smoke 执行测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast


def _valid_config(tmp_path: Path) -> dict[str, object]:
    """返回严格 JSON local-smoke 配置。"""
    return {
        "run_id": "tiny-local-smoke",
        "seed": 23,
        "model_registry_key": "deterministic-test-framework",
        "dataset_fingerprint": "dataset-smoke",
        "transform_fingerprint": "transform-smoke",
        "statistics_fingerprint": "stats-smoke",
        "action_horizon": 2,
        "action_dim": 3,
        "max_steps": 2,
        "output_dir": str(tmp_path / "runs"),
        "mode": "dry-run",
    }


def _write_config(path: Path, payload: Mapping[str, object]) -> Path:
    """写入稳定 JSON 配置。"""
    path.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _run_local_smoke(config_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    """通过模块入口运行 local-smoke。"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.training.cli",
            "--config",
            str(config_path),
            "--local-smoke",
            "--output-dir",
            str(output_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=output_dir.parent,
        env=env,
    )


def test_cli_local_smoke_should_write_bounded_deterministic_outputs(
    tmp_path: Path,
) -> None:
    """验证 CLI local-smoke 只在 tmp_path 下写稳定输出。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_dir = tmp_path / "override-runs"

    result = _run_local_smoke(config_path, output_dir)

    assert result.returncode == 0, result.stderr
    stdout = cast(dict[str, object], json.loads(result.stdout))
    execution_manifest_path = Path(cast(str, stdout["execution_manifest_path"]))
    checkpoint_manifest_path = Path(cast(str, stdout["checkpoint_manifest_path"]))
    assert stdout["local_smoke"] is True
    assert stdout["mode"] == "local-smoke"
    assert stdout["resumed_step"] == 2
    assert execution_manifest_path == output_dir / "tiny-local-smoke" / "execution_manifest.json"
    assert (
        checkpoint_manifest_path == output_dir / "tiny-local-smoke" / "checkpoints" / "step-2.json"
    )
    assert execution_manifest_path.is_file()
    assert checkpoint_manifest_path.is_file()
    assert execution_manifest_path.resolve().is_relative_to(tmp_path.resolve())
    assert checkpoint_manifest_path.resolve().is_relative_to(tmp_path.resolve())

    first_text = execution_manifest_path.read_text(encoding="utf-8")
    second_result = _run_local_smoke(config_path, output_dir)
    assert second_result.returncode == 0, second_result.stderr
    assert execution_manifest_path.read_text(encoding="utf-8") == first_text

    manifest = cast(dict[str, object], json.loads(first_text))
    resume = cast(dict[str, object], manifest["resume"])
    external_effects = cast(dict[str, object], manifest["external_effects"])
    assert manifest["schema_version"] == "m3-cli-local-smoke-execution.v1"
    assert manifest["local_smoke"] is True
    assert manifest["dry_run"] is False
    assert resume["resumed_step"] == 2
    assert resume["compatible"] is True
    assert all(value is False for value in external_effects.values())


def test_cli_local_smoke_should_return_nonzero_without_partial_outputs(
    tmp_path: Path,
) -> None:
    """验证配置校验失败不会留下 local-smoke 输出。"""
    payload = _valid_config(tmp_path)
    payload["seed"] = "23"
    config_path = _write_config(tmp_path / "bad-config.json", payload)
    output_dir = tmp_path / "runs"

    result = _run_local_smoke(config_path, output_dir)

    assert result.returncode == 2
    assert "seed" in result.stderr
    assert not (output_dir / "tiny-local-smoke" / "execution_manifest.json").exists()
    assert not (output_dir / "tiny-local-smoke" / "checkpoints" / "step-2.json").exists()
