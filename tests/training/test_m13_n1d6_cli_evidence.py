"""M13 N1D6 训练 CLI 收据门与 harness 静态契约回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from autovla.assets.errors import ModelAssetAuthorizationError
from autovla.cli.train import _asset_evidence_paths, _load_checkout_json, build_parser
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

ROOT = Path(__file__).resolve().parents[2]


def test_training_cli_names_missing_runtime_and_asset_evidence_fields() -> None:
    """缺失收据以稳定字段/代码失败,且 parser 不提供绕过开关。"""

    parser = build_parser()
    destinations = {action.dest for action in parser._actions}
    assert {
        "runtime_lock_receipt",
        "runtime_environment_receipt",
        "asset_evidence",
    } <= destinations
    assert not {"skip_asset_check", "accept_terms", "allow_unverified"} & destinations
    with pytest.raises(RuntimeEnvironmentError) as captured:
        _load_checkout_json(
            ROOT,
            None,
            field="runtime_lock_receipt",
            missing_code="M13_RUNTIME_LOCK_RECEIPT_REQUIRED",
        )
    assert captured.value.code == "M13_RUNTIME_LOCK_RECEIPT_REQUIRED"
    with pytest.raises(
        ModelAssetAuthorizationError,
        match="ASSET_EVIDENCE_PATH_MISSING",
    ):
        _asset_evidence_paths(ROOT, ())


def test_m13_harnesses_are_offline_wrapper_bound_and_fixture_truthful() -> None:
    """环境脚本只走项目 wrapper,fixture harness 不声称执行或后端胜出。"""

    submit = (ROOT / "scripts/slurm/m13_submit_n1d6_environment.sh").read_text(encoding="utf-8")
    job = (ROOT / "scripts/slurm/m13_n1d6_environment.sbatch").read_text(encoding="utf-8")
    harness = (ROOT / "scripts/validation/m13_n1d6_harness.py").read_text(encoding="utf-8")
    slurm = json.loads(
        (ROOT / "configs/slurm/m13_n1d6_environment_a100.json").read_text(encoding="utf-8")
    )
    assert "scripts/slurm/submit_sandbox_job.sh" in submit
    assert "envs/model-gr00t-n1d6/.venv" not in submit + job + harness
    assert "UV_OFFLINE=1" in job
    assert "cache_prime_performed" in job
    assert '"preflight", "materialize", "verify"' in harness
    assert '"NO_BACKEND_WINNER"' in harness
    assert '"real_data_claim": False' in harness
    assert '"model_execution_performed": False' in harness
    assert slurm["partition"] == "a100" and slurm["gres"] == "gpu:1"
