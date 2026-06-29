"""M3 runner readiness CLI 测试。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast


def _valid_config(tmp_path: Path) -> dict[str, object]:
    """返回严格 JSON readiness 配置。"""
    return {
        "run_id": "tiny-readiness",
        "seed": 31,
        "model_registry_key": "deterministic-test-framework",
        "dataset_fingerprint": "dataset-readiness",
        "transform_fingerprint": "transform-readiness",
        "statistics_fingerprint": "stats-readiness",
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


def _run_cli(args: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    """通过模块入口运行 Training CLI。"""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPATH"] = str(Path.cwd())
    return subprocess.run(
        [sys.executable, "-m", "autovla.training.cli", *args],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
        cwd=cwd,
        env=env,
    )


def _run_readiness(config_path: Path, output_dir: Path) -> subprocess.CompletedProcess[str]:
    """运行 readiness 子命令。"""
    return _run_cli(
        [
            "readiness",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
        cwd=output_dir.parent,
    )


def test_cli_help_should_show_readiness_subcommand(tmp_path: Path) -> None:
    """验证帮助文本公开 canonical readiness 子命令。"""
    result = _run_cli(["--help"], cwd=tmp_path)

    assert result.returncode == 0
    assert "readiness" in result.stdout
    assert "real training" not in result.stdout.lower()


def test_cli_readiness_should_write_bounded_deterministic_manifest(tmp_path: Path) -> None:
    """验证 readiness 只在 tmp_path 下写稳定 manifest。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_dir = tmp_path / "override-runs"

    first_result = _run_readiness(config_path, output_dir)

    assert first_result.returncode == 0, first_result.stderr
    stdout = cast(dict[str, object], json.loads(first_result.stdout))
    readiness_manifest_path = Path(cast(str, stdout["readiness_manifest_path"]))
    checkpoint_manifest_path = Path(cast(str, stdout["checkpoint_manifest_path"]))
    assert stdout["readiness"] is True
    assert stdout["mode"] == "readiness"
    assert stdout["resumed_step"] == 2
    assert readiness_manifest_path == output_dir / "tiny-readiness" / "readiness_manifest.json"
    assert checkpoint_manifest_path == output_dir / "tiny-readiness" / "checkpoints" / "step-2.json"
    assert readiness_manifest_path.is_file()
    assert checkpoint_manifest_path.is_file()
    assert readiness_manifest_path.resolve().is_relative_to(tmp_path.resolve())
    assert checkpoint_manifest_path.resolve().is_relative_to(tmp_path.resolve())

    first_text = readiness_manifest_path.read_text(encoding="utf-8")
    second_result = _run_readiness(config_path, output_dir)
    assert second_result.returncode == 0, second_result.stderr
    assert readiness_manifest_path.read_text(encoding="utf-8") == first_text
    assert first_text == json.dumps(json.loads(first_text), indent=2, sort_keys=True) + "\n"


def test_cli_readiness_manifest_should_preserve_runner_boundaries(tmp_path: Path) -> None:
    """验证 readiness manifest 不声明真实训练或外部效果。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_dir = tmp_path / "runs"

    result = _run_readiness(config_path, output_dir)

    assert result.returncode == 0, result.stderr
    readiness_manifest_path = Path(
        cast(str, cast(dict[str, object], json.loads(result.stdout))["readiness_manifest_path"])
    )
    manifest = cast(dict[str, object], json.loads(readiness_manifest_path.read_text("utf-8")))
    external_effects = cast(dict[str, object], manifest["external_effects"])
    metrics = cast(dict[str, object], manifest["metrics"])
    runner_state = cast(dict[str, object], manifest["runner_state"])
    fixture_summary = cast(dict[str, object], manifest["fixture_summary"])

    assert manifest["schema_version"] == "m3-runner-readiness.v1"
    assert manifest["mode"] == "readiness"
    assert manifest["package_name"] == "autovla"
    assert manifest["cli_module"] == "autovla.training.cli"
    assert manifest["run_id"] == "tiny-readiness"
    assert manifest["dataset_fingerprint"] == "dataset-readiness"
    assert manifest["transform_fingerprint"] == "transform-readiness"
    assert manifest["statistics_fingerprint"] == "stats-readiness"
    assert manifest["model_registry_key"] == "deterministic-test-framework"
    assert manifest["seed"] == 31
    assert manifest["action_horizon"] == 2
    assert manifest["action_dim"] == 3
    assert manifest["compatibility_shim_present"] is False
    assert manifest["checkpoint_manifest_path"] == "tiny-readiness/checkpoints/step-2.json"
    assert runner_state == {"epoch": 0, "setup_complete": True, "step": 2}
    assert fixture_summary == {
        "batch_size": 2,
        "dataset": "in-memory-local-smoke",
        "sample_count": 2,
    }
    assert "train" in metrics
    assert "eval" in metrics
    assert all(value is False for value in external_effects.values())
    assert "generated_at" not in manifest


def test_cli_readiness_should_return_nonzero_without_partial_outputs(tmp_path: Path) -> None:
    """验证配置错误不留下 readiness/local-smoke 输出。"""
    payload = _valid_config(tmp_path)
    payload["seed"] = "31"
    config_path = _write_config(tmp_path / "bad-config.json", payload)
    output_dir = tmp_path / "runs"

    result = _run_readiness(config_path, output_dir)

    assert result.returncode == 2
    assert "seed" in result.stderr
    assert not (output_dir / "tiny-readiness" / "readiness_manifest.json").exists()
    assert not (output_dir / "tiny-readiness" / "execution_manifest.json").exists()
    assert not (output_dir / "tiny-readiness" / "checkpoints" / "step-2.json").exists()


def test_cli_readiness_should_reject_invalid_output_dir_without_partial_outputs(
    tmp_path: Path,
) -> None:
    """验证 output_dir 为文件时 readiness 失败且不写局部输出。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_file = tmp_path / "not-a-directory"
    output_file.write_text("not a directory\n", encoding="utf-8")

    result = _run_readiness(config_path, output_file)

    assert result.returncode == 2
    assert "output_dir" in result.stderr
    assert output_file.read_text(encoding="utf-8") == "not a directory\n"


def test_cli_readiness_should_preserve_existing_local_smoke_mode(tmp_path: Path) -> None:
    """验证新增子命令不破坏已有 local-smoke flag 模式。"""
    config_path = _write_config(tmp_path / "config.json", _valid_config(tmp_path))
    output_dir = tmp_path / "local-smoke-runs"

    result = _run_cli(
        [
            "--config",
            str(config_path),
            "--local-smoke",
            "--output-dir",
            str(output_dir),
        ],
        cwd=tmp_path,
    )

    assert result.returncode == 0, result.stderr
    stdout = cast(dict[str, object], json.loads(result.stdout))
    assert stdout["local_smoke"] is True
    assert stdout["mode"] == "local-smoke"
