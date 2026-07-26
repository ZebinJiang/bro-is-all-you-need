"""M13 N1D6 训练 CLI 收据门与 harness 静态契约回归。"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import autovla.assets.authorization as asset_authorization
import autovla.cli.train as train_cli
import scripts.validation.m13_n1d6_harness as m13_harness
from autovla.assets.errors import ModelAssetAuthorizationError
from autovla.cli.train import (
    _asset_evidence_paths,
    _load_checkout_json,
    _resolve_family_authorized_assets,
    build_parser,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from scripts.validation.m13_n1d6_harness import TASK_ID, _write_json

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
    assert 'str(python),\n        "-I",\n        "-m"' in harness
    assert slurm["partition"] == "a100" and slurm["gres"] == "gpu:1"


def test_m13_fixture_launch_uses_canonical_paths_from_unrelated_cwd(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """fixture argv 在无关 cwd 中仍只引用真实 checkout 和隔离环境。"""

    project_root = tmp_path / "checkout"
    workspace_root = tmp_path / "workspace"
    source_sha = "a" * 40
    lock_fingerprint = "b" * 64
    environment_relative = f".autovla_envs/gr00t_n1d6_runtime/{lock_fingerprint}/.venv"
    python = workspace_root / environment_relative / "bin" / "python"
    python.parent.mkdir(parents=True)
    python.touch()

    relative_files = {
        "config": Path(m13_harness.CONTRACT_FIXTURE_CONFIG),
        "lock": Path(f"runs/tmp/{TASK_ID}/receipts/lock.json"),
        "environment": Path(f"runs/tmp/{TASK_ID}/receipts/environment.json"),
        "base_asset": Path(f"runs/tmp/{TASK_ID}/evidence/base.json"),
        "eagle_asset": Path(f"runs/tmp/{TASK_ID}/evidence/eagle.json"),
    }
    for relative in relative_files.values():
        path = project_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n", encoding="utf-8")
    fixture_relative = Path(f"runs/tmp/{TASK_ID}/fixture")
    fixture = project_root / fixture_relative
    fixture.mkdir(parents=True)

    environment = type(
        "Environment",
        (),
        {
            "source_sha": source_sha,
            "environment_path": environment_relative,
            "validate_lock": lambda self, lock: None,
        },
    )()
    monkeypatch.setattr(m13_harness, "_source_head", lambda root: source_sha)
    monkeypatch.setattr(
        m13_harness.ResolvedRuntimeLock,
        "from_dict",
        staticmethod(lambda payload: object()),
    )
    monkeypatch.setattr(
        m13_harness.RuntimeEnvironmentReceipt,
        "from_dict",
        staticmethod(lambda payload: environment),
    )
    monkeypatch.setattr(
        m13_harness.AssetLifecycleEvidence,
        "from_dict",
        staticmethod(lambda payload: object()),
    )

    unrelated = tmp_path / "unrelated"
    shadow = unrelated / m13_harness.CONTRACT_FIXTURE_CONFIG
    shadow.parent.mkdir(parents=True)
    shadow.write_text("shadow: true\n", encoding="utf-8")
    (unrelated / "autovla/cli").mkdir(parents=True)
    (unrelated / "autovla/cli/train.py").write_text("raise RuntimeError\n", encoding="utf-8")
    monkeypatch.chdir(unrelated)

    launch = m13_harness.build_contract_fixture_launch(
        {
            "schema_version": m13_harness.FIXTURE_SCHEMA,
            "task_id": TASK_ID,
            "source_head": source_sha,
            "fixture_kind": "contract_fixture_only",
            "fixture_root": fixture_relative.as_posix(),
            "fixture_identity": "c" * 64,
            "fixture_sample_count": 1,
            "embodiment": "gr1",
            "backend_decision": "NO_BACKEND_WINNER",
            "max_steps": 1,
            "runtime_lock_receipt": relative_files["lock"].as_posix(),
            "runtime_environment_receipt": relative_files["environment"].as_posix(),
            "asset_evidence": {
                "gr00t_n1d6": relative_files["base_asset"].as_posix(),
                "gr00t_n1d6_eagle_support": relative_files["eagle_asset"].as_posix(),
            },
        },
        project_root,
        workspace_root,
    )
    command = launch["command"]
    assert isinstance(command, list)
    assert command[:4] == [str(python), "-I", "-m", "autovla.cli.train"]
    assert command[4] == str((project_root / relative_files["config"]).resolve())
    assert command[command.index("--runtime-lock-receipt") + 1] == str(
        (project_root / relative_files["lock"]).resolve()
    )
    assert command[command.index("--runtime-environment-receipt") + 1] == str(
        (project_root / relative_files["environment"]).resolve()
    )
    assert f"gr00t_n1d6={(project_root / relative_files['base_asset']).resolve()}" in command
    assert (
        f"gr00t_n1d6_eagle_support=" f"{(project_root / relative_files['eagle_asset']).resolve()}"
    ) in command
    assert f"data.datasets[0].root={fixture.resolve()}" in command
    assert str(shadow) not in command


def test_m13_harness_output_is_task_local_atomic_and_no_clobber(tmp_path: Path) -> None:
    """harness 只原子发布任务目录输出,且不覆盖无关既有内容。"""

    output = Path(f"runs/tmp/{TASK_ID}/evidence/result.json")
    payload = {"status": "pass"}
    _write_json(tmp_path, output, payload)
    absolute = tmp_path / output
    expected = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    assert absolute.read_text(encoding="utf-8") == expected
    assert not tuple(absolute.parent.glob(f".{absolute.name}.*.tmp"))

    _write_json(tmp_path, output, payload)
    absolute.write_text('{"unrelated":true}\n', encoding="utf-8")
    with pytest.raises(ValueError, match="unrelated content"):
        _write_json(tmp_path, output, payload)
    assert absolute.read_text(encoding="utf-8") == '{"unrelated":true}\n'


@pytest.mark.parametrize(
    "output",
    (
        Path("/tmp/result.json"),
        Path(f"runs/tmp/{TASK_ID}/../result.json"),
        Path("runs/tmp/other-task/result.json"),
        f"runs//tmp/{TASK_ID}/result.json",
        f"runs/tmp/{TASK_ID}/./result.json",
    ),
)
def test_m13_harness_rejects_absolute_traversal_and_wrong_task_output(
    tmp_path: Path,
    output: str | Path,
) -> None:
    """绝对、父级穿越和非本任务输出在写入前失败。"""

    with pytest.raises(ValueError):
        _write_json(tmp_path, output, {"status": "pass"})


def test_m13_harness_rejects_output_symlink_ancestry(tmp_path: Path) -> None:
    """任务输出父级不得通过符号链接逃逸。"""

    task_root = tmp_path / "runs/tmp" / TASK_ID
    task_root.mkdir(parents=True)
    external = tmp_path / "external"
    external.mkdir()
    (task_root / "link").symlink_to(external, target_is_directory=True)
    with pytest.raises(ValueError, match="symbolic links"):
        _write_json(
            tmp_path,
            Path(f"runs/tmp/{TASK_ID}/link/result.json"),
            {"status": "pass"},
        )
    assert not (external / "result.json").exists()
