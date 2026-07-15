"""AutoVLA 训练 runner dry-run 测试。"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, cast

import pytest

from autovla.models.family import ModelFamilySpec as LegacyModelFamilySpec
from autovla.models.registry import get as get_model_family
from autovla.training.fixtures import build_tiny_training_batch
from autovla.training.runner import DryRunConfig, run_training_dry_run


def _config(output_dir: Path, *, seed: int = 7) -> DryRunConfig:
    """构造测试用 dry-run 配置。"""
    return DryRunConfig(
        family_key="gr00t-n1d6",
        fixture="tiny",
        output_dir=output_dir,
        run_id="dryrun-a",
        seed=seed,
        steps=2,
    )


def _read_json(path: Path) -> Any:
    """读取 JSON 文件。"""
    return json.loads(path.read_text(encoding="utf-8"))


def test_runner_should_execute_gr00t_dryrun_dataflow(tmp_path: Path) -> None:
    """验证 TrainingBatch 到遥测和 checkpoint manifest 的完整 dry-run 链。"""
    result = run_training_dry_run(_config(tmp_path))

    assert result.output_dir == tmp_path
    assert result.resumed_step == 2
    resume_validation = cast(dict[str, Any], result.resume_validation)
    assert resume_validation["compatible"] is True
    assert resume_validation["incompatible"]["field_errors"]["dataset_fingerprint"]
    assert result.files["run_manifest"].name == "run_manifest.json"

    run_manifest = _read_json(result.files["run_manifest"])
    state = _read_json(result.files["runner_state"])
    metrics = _read_json(result.files["step_metrics"])
    telemetry = _read_json(result.files["efficiency_telemetry"])
    checkpoint = _read_json(result.files["checkpoint_manifest"])

    assert run_manifest == {
        "family_key": "gr00t-n1d6",
        "fixture": "tiny",
        "mode": "cpu_dry_run",
        "run_id": "dryrun-a",
        "seed": 7,
        "steps": 2,
    }
    assert state["step"] == 2
    assert state["model_family_key"] == "gr00t-n1d6"
    assert len(metrics) == 2
    assert metrics[0]["loss"] == pytest.approx(0.01)
    assert telemetry["policy_forward_time_ms"] > 0.0
    assert telemetry["total_step_time_ms"] > 0.0
    assert telemetry["rejected_sample_count"] == 0
    assert telemetry["rejection_reasons"] == ["none"]
    assert checkpoint["compatibility"]["model_family_key"] == "gr00t-n1d6"
    assert "weights" not in checkpoint


def test_runner_outputs_should_be_byte_identical_for_same_seed(tmp_path: Path) -> None:
    """验证相同 seed 的规范输出字节完全一致。"""
    first = tmp_path / "first"
    second = tmp_path / "second"

    first_result = run_training_dry_run(_config(first, seed=17))
    second_result = run_training_dry_run(_config(second, seed=17))

    for name in (
        "runner_state",
        "efficiency_telemetry",
        "checkpoint_manifest",
        "resume_validation",
    ):
        assert first_result.files[name].read_bytes() == second_result.files[name].read_bytes()


def test_runner_should_reject_resume_mismatches_with_field_errors(tmp_path: Path) -> None:
    """验证 resume 校验提供字段级 mismatch。"""
    result = run_training_dry_run(_config(tmp_path))
    payload = _read_json(result.files["resume_validation"])

    assert payload["compatible"] is True
    assert payload["compatible_step"] == 2
    assert payload["incompatible"]["compatible"] is False
    assert payload["incompatible"]["field_errors"] == {
        "dataset_fingerprint": {
            "actual": "autovla-tiny-dataset-v1",
            "expected": "wrong-dataset",
        }
    }


def test_runner_should_lookup_pi_metadata_without_heavy_imports() -> None:
    """验证 Pi roadmap 查询不导入 JAX/Flax/OpenPI。"""
    before = set(sys.modules)

    pi_spec = get_model_family("pi0-roadmap")
    batch = build_tiny_training_batch()

    loaded = set(sys.modules) - before
    assert isinstance(pi_spec, LegacyModelFamilySpec)
    assert pi_spec.runtime_status == ("roadmap_only", "no_import")
    assert batch.batch_size == 2
    assert "jax" not in loaded
    assert "flax" not in loaded
    assert "openpi" not in loaded
