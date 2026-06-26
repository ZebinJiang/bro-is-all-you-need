"""M3 local-smoke execution manifest 测试。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import cast

from genesisvla.training.config import LocalRunnerDryRunConfig
from genesisvla.training.execution_manifest import (
    build_execution_manifest,
    write_execution_manifest,
)


def _config(tmp_path: Path) -> LocalRunnerDryRunConfig:
    """返回只写 tmp_path 的 local-smoke 配置。"""
    return LocalRunnerDryRunConfig(
        run_id="tiny-local-smoke",
        seed=5,
        model_registry_key="deterministic-test-framework",
        dataset_fingerprint="dataset-smoke",
        transform_fingerprint="transform-smoke",
        statistics_fingerprint="stats-smoke",
        action_horizon=2,
        action_dim=3,
        max_steps=2,
        output_dir=tmp_path / "runs",
        mode="dry-run",
    )


def test_build_execution_manifest_should_record_local_smoke_boundaries(
    tmp_path: Path,
) -> None:
    """验证 execution manifest 只声明 local-smoke 边界。"""
    config = _config(tmp_path)
    checkpoint_path = tmp_path / "runs" / "tiny-local-smoke" / "checkpoints" / "step-2.json"

    manifest = build_execution_manifest(
        config,
        train_metrics={"masked_action_mse": 1.0, "step": 2.0},
        eval_metrics={"masked_action_mse": 1.0, "step": 2.0},
        checkpoint_manifest_path=checkpoint_path,
        resumed_step=2,
    )

    artifacts = cast(Mapping[str, object], manifest["artifacts"])
    external_effects = cast(Mapping[str, object], manifest["external_effects"])
    resume = cast(Mapping[str, object], manifest["resume"])
    assert manifest["schema_version"] == "m3-cli-local-smoke-execution.v1"
    assert manifest["mode"] == "local-smoke"
    assert manifest["local_smoke"] is True
    assert manifest["dry_run"] is False
    assert artifacts["execution_manifest"] == "tiny-local-smoke/execution_manifest.json"
    assert artifacts["checkpoint_manifest"] == "tiny-local-smoke/checkpoints/step-2.json"
    assert resume["resumed_step"] == 2
    assert resume["compatible"] is True
    assert all(value is False for value in external_effects.values())


def test_write_execution_manifest_should_be_deterministic(tmp_path: Path) -> None:
    """验证 execution manifest 重复写入字节稳定。"""
    config = _config(tmp_path)
    checkpoint_path = tmp_path / "runs" / "tiny-local-smoke" / "checkpoints" / "step-2.json"

    first_path = write_execution_manifest(
        config,
        train_metrics={"masked_action_mse": 1.0, "step": 2.0},
        eval_metrics={"masked_action_mse": 1.0, "step": 2.0},
        checkpoint_manifest_path=checkpoint_path,
        resumed_step=2,
    )
    first_text = first_path.read_text(encoding="utf-8")
    second_path = write_execution_manifest(
        config,
        train_metrics={"masked_action_mse": 1.0, "step": 2.0},
        eval_metrics={"masked_action_mse": 1.0, "step": 2.0},
        checkpoint_manifest_path=checkpoint_path,
        resumed_step=2,
    )
    second_text = second_path.read_text(encoding="utf-8")

    assert first_path == tmp_path / "runs" / "tiny-local-smoke" / "execution_manifest.json"
    assert second_path == first_path
    assert first_text == second_text
    assert first_text == json.dumps(json.loads(first_text), indent=2, sort_keys=True) + "\n"
    assert first_path.resolve().is_relative_to(tmp_path.resolve())
