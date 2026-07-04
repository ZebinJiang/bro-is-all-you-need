"""训练效率遥测 harness 测试。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autovla.training.efficiency import EfficiencyTelemetry
from autovla.training.runner import DryRunConfig, run_training_dry_run


def test_efficiency_telemetry_should_publish_required_alias_fields() -> None:
    """验证遥测输出包含 runner harness 需要的字段。"""
    telemetry = EfficiencyTelemetry(
        samples_per_second=4.0,
        batches_per_second=2.0,
        batch_latency_ms_p50=10.0,
        batch_latency_ms_p95=12.0,
        data_wait_time_ms=1.0,
        collate_time_ms=0.5,
        adapter_time_ms=2.0,
        forward_time_ms=3.0,
        loss_time_ms=0.25,
        checkpoint_manifest_time_ms=0.75,
        memory_envelope_mb=64.0,
    )

    payload = json.loads(telemetry.to_stable_json())

    assert payload["policy_forward_time_ms"] == 3.0
    assert payload["total_step_time_ms"] == pytest.approx(7.5)
    assert payload["rejected_sample_count"] == 0
    assert payload["rejection_reasons"] == ["none"]
    assert payload["memory_rss_mb"] == 64.0


def test_dryrun_should_write_only_under_output_dir(tmp_path: Path) -> None:
    """验证 dry-run 只在 output_dir 下写出小型 JSON 产物。"""
    result = run_training_dry_run(
        DryRunConfig(
            family_key="gr00t-n1d6",
            fixture="tiny",
            output_dir=tmp_path,
            run_id="dryrun-output",
            seed=3,
            steps=2,
        )
    )

    assert set(result.files) == {
        "checkpoint_manifest",
        "efficiency_telemetry",
        "resume_validation",
        "run_manifest",
        "runner_state",
        "step_metrics",
    }
    for path in result.files.values():
        assert path.is_file()
        assert path.resolve().is_relative_to(tmp_path.resolve())
        assert path.suffix == ".json"
        assert path.stat().st_size < 4096
