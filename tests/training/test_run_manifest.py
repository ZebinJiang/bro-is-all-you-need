"""M3 本地 runner dry-run manifest 测试。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from autovla.training.config import LocalRunnerDryRunConfig
from autovla.training.run_manifest import (
    build_dry_run_manifest,
    write_dry_run_manifest,
)


def _config(tmp_path: Path) -> LocalRunnerDryRunConfig:
    """返回只写 tmp_path 的 dry-run config。"""
    return LocalRunnerDryRunConfig(
        run_id="tiny-dry-run",
        seed=7,
        model_registry_key="deterministic-test-framework",
        dataset_fingerprint="dataset-a",
        transform_fingerprint="transform-a",
        statistics_fingerprint="stats-a",
        action_horizon=2,
        action_dim=3,
        max_steps=2,
        output_dir=tmp_path / "runs",
        mode="dry-run",
    )


def test_build_dry_run_manifest_should_be_device_neutral_and_local_only(
    tmp_path: Path,
) -> None:
    """验证 manifest 记录 dry-run 边界而不声明真实训练。"""
    manifest = build_dry_run_manifest(_config(tmp_path))
    action = cast(Mapping[str, object], manifest["action"])
    local_runner_config = cast(Mapping[str, object], manifest["local_runner_config"])

    assert manifest["schema_version"] == "m3-runner-config-cli-dry-run.v1"
    assert manifest["dry_run"] is True
    assert manifest["mode"] == "dry-run"
    assert action["horizon"] == 2
    assert action["dim"] == 3
    assert local_runner_config["run_root"] == "."
    assert manifest["external_effects"] == {
        "checkpoint_weight_load": False,
        "endpoint": False,
        "external_dataset": False,
        "gpu": False,
        "hf": False,
        "network": False,
        "real_model": False,
        "real_training": False,
        "robot": False,
        "slurm": False,
        "wandb": False,
    }


def test_write_dry_run_manifest_should_be_deterministic(tmp_path: Path) -> None:
    """验证 manifest 文件内容稳定且仅写 output_dir/run_id。"""
    config = _config(tmp_path)

    first_path = write_dry_run_manifest(config)
    first_text = first_path.read_text(encoding="utf-8")
    second_path = write_dry_run_manifest(config)
    second_text = second_path.read_text(encoding="utf-8")

    assert first_path == tmp_path / "runs" / "tiny-dry-run" / "dry_run_manifest.json"
    assert second_path == first_path
    assert first_text == second_text
    assert first_text == json.dumps(json.loads(first_text), indent=2, sort_keys=True) + "\n"
    assert first_path.resolve().is_relative_to(tmp_path.resolve())
