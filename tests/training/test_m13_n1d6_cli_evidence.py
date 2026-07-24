"""M13 N1D6 训练 CLI 收据门与 harness 静态契约回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import autovla.assets.authorization as asset_authorization
import autovla.cli.train as train_cli
from autovla.assets.errors import ModelAssetAuthorizationError
from autovla.cli.train import (
    _asset_evidence_paths,
    _load_checkout_json,
    _resolve_family_authorized_assets,
    build_parser,
)
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


def test_training_cli_dispatches_n1d6_and_rejects_other_families_before_parsing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """N1D6 使用精确解析器,其他 family 不得进入 N1D6 证据语义。"""

    evidence_paths = {"gr00t_n1d6": ROOT / "base.json"}
    parsed_values: list[tuple[str, ...]] = []
    resolved_calls: list[tuple[Path, dict[str, Path]]] = []

    def _parse_once(
        repository_root: Path,
        values: tuple[str, ...],
    ) -> dict[str, Path]:
        """记录唯一允许的 N1D6 证据解析。"""

        assert repository_root == ROOT
        parsed_values.append(values)
        return evidence_paths

    def _resolve_once(
        *,
        asset_root: Path,
        evidence_paths: dict[str, Path],
    ) -> tuple[()]:
        """记录 N1D6 精确 resolver 分派。"""

        resolved_calls.append((asset_root, evidence_paths))
        return ()

    monkeypatch.setattr(train_cli, "_asset_evidence_paths", _parse_once)
    monkeypatch.setattr(asset_authorization, "resolve_n1d6_authorized_assets", _resolve_once)
    assert (
        _resolve_family_authorized_assets(
            family_key="gr00t_n1d6",
            repository_root=ROOT,
            asset_root=ROOT / "assets",
            evidence_values=("gr00t_n1d6=base.json",),
        )
        == ()
    )
    assert parsed_values == [("gr00t_n1d6=base.json",)]
    assert resolved_calls == [(ROOT / "assets", evidence_paths)]

    with pytest.raises(ModelAssetAuthorizationError) as captured:
        _resolve_family_authorized_assets(
            family_key="pi0_5",
            repository_root=ROOT,
            asset_root=ROOT / "assets",
            evidence_values=("gr00t_n1d6=base.json",),
        )
    assert captured.value.blocker == "FAMILY_ASSET_AUTHORIZATION_UNAVAILABLE"
    assert captured.value.asset_key == "pi0_5"
    assert len(parsed_values) == 1
    assert len(resolved_calls) == 1


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
