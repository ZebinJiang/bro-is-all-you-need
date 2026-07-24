"""验证 M11 模型路由策略和 canonical 子代理事件账本。"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path

import pytest
import yaml

POLICY_FILES = (
    Path("coordination/MODEL_ROUTING_POLICY.yaml"),
    Path("coordination/VALIDATION_POLICY.yaml"),
    Path("coordination/AGENT_LIFECYCLE_POLICY.yaml"),
    Path("coordination/PARALLEL_EXECUTION_POLICY.yaml"),
)
LEDGER_SCHEMA = "autovla-m11-child-lifecycle-events-v1"
CONFIGURED_LEDGER = Path(
    "runs/tmp/AUTOVLA-M11-ARCHITECTURE-FIRST-EXECUTABLE-FAMILIES-DATA-BINDING-001/"
    "governance/child-lifecycle.jsonl"
)


def repo_root() -> Path:
    """返回当前测试对应的仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def run_validator_at(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    """通过当前解释器在指定根目录运行治理校验器。"""
    return subprocess.run(
        [
            sys.executable,
            str(repo_root() / "scripts/coordination/validate_model_routing.py"),
            "--root",
            str(root),
            *args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def run_validator(*args: str) -> subprocess.CompletedProcess[str]:
    """在当前仓库运行治理校验器。"""
    return run_validator_at(repo_root(), *args)


def launch_record(**overrides: object) -> dict[str, object]:
    """构造 M11 切换后的 canonical launch 事件。"""
    record: dict[str, object] = {
        "event": "launch",
        "timestamp_utc": "2026-07-17T18:10:00Z",
        "role": "M11-GOVERNANCE-TEST-W1",
        "agent_id": "m11-governance-test-agent",
        "model": "gpt-5.6-sol",
        "reasoning": "medium",
        "depth": 1,
        "source_sha": "0" * 40,
        "worktree": "/repo/.worktrees/m11-governance-test-w1",
        "branch": "dev/m11-governance-test-w1",
        "capability": "sole_governance_test_writer",
        "descendants_allowed": False,
        "remote_authority": False,
        "status": "active",
    }
    record.update(overrides)
    return record


def close_record(**overrides: object) -> dict[str, object]:
    """构造与 canonical launch 匹配的 close 事件。"""
    record: dict[str, object] = {
        "event": "close",
        "timestamp_utc": "2026-07-17T18:11:00Z",
        "role": "M11-GOVERNANCE-TEST-W1",
        "agent_id": "m11-governance-test-agent",
        "conclusion": "PASS_TEST",
        "descendants": 0,
        "residual_processes": 0,
        "retired": True,
    }
    record.update(overrides)
    return record


def write_ledger(path: Path, *records: Mapping[str, object]) -> None:
    """按传入顺序写入 JSONL 事件夹具。"""
    path.write_text(
        "".join(json.dumps(record, sort_keys=True) + "\n" for record in records),
        encoding="utf-8",
    )


def make_publication_root(tmp_path: Path, ledger: Path) -> Path:
    """构造只含机器策略和 dispatch memory 的 clean-checkout 夹具根。"""
    root = tmp_path / "publication-root"
    for relative in POLICY_FILES:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo_root() / relative, target)
    memory = {
        "owner_dispatch_memory_schema_version": 2,
        "active_goal": "AUTOVLA-M11-ARCHITECTURE-FIRST-EXECUTABLE-FAMILIES-DATA-BINDING-001",
        "prompt_scoped_child_dispatch": {
            "task_local_ledger": str(ledger),
            "task_local_ledger_schema": LEDGER_SCHEMA,
        },
    }
    memory_path = root / "coordination/OWNER_DISPATCH_MEMORY.yaml"
    memory_path.write_text(yaml.safe_dump(memory, sort_keys=False), encoding="utf-8")
    return root


def test_active_model_routing_policy_passes_without_requesting_ledger() -> None:
    """确认 policy-only 模式明确不请求 ignored lifecycle evidence。"""
    result = run_validator()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["owner_model"] == "gpt-5.6-sol"
    assert payload["owner_reasoning"] == "medium"
    assert payload["president_manager_reasoning"] == "max"
    assert payload["execution_reasoning"] == "medium"
    assert payload["manager_return_reasoning"] == "medium"
    assert payload["persistent_owners_enabled"] is False
    assert payload["final_review_agent_count"] == 4
    assert payload["validation_policy_name"] == (
        "autovla-m11-executable-family-data-binding-runtime-validation"
    )
    assert payload["ledger_mode"] == "not_requested"
    assert payload["ledger_status"] == "not_requested"
    assert payload["ledger_record_count"] == 0
    assert payload["ledger_active_count"] == 0


def test_active_model_routing_policy_accepts_matching_positional_root() -> None:
    """确认 Manager 命令末尾的冗余仓库根保持向后兼容。"""
    result = run_validator(".")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["active_file_count"] == 18


def test_event_ledger_replays_launch_close_and_counts_non_child(tmp_path: Path) -> None:
    """确认 child replay 与 wave 记录分别计数且终态关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    wave = {
        "event": "wave_complete",
        "timestamp_utc": "2026-07-17T18:12:00Z",
        "active_children": 0,
    }
    write_ledger(ledger, launch_record(), close_record(), wave)
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ledger_record_count"] == 3
    assert payload["ledger_child_event_count"] == 2
    assert payload["ledger_non_child_event_count"] == 1
    assert payload["ledger_active_count"] == 0


def test_event_ledger_accepts_historical_pre_cutover_record(tmp_path: Path) -> None:
    """确认切换前旧记录仅作历史计数, 不伪装当前 M11 schema。"""
    ledger = tmp_path / "ledger.jsonl"
    historical = {
        "event": "legacy_owner_return",
        "timestamp_utc": "2026-07-17T18:00:00Z",
        "legacy_payload": True,
    }
    write_ledger(ledger, historical, launch_record(), close_record())
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ledger_historical_record_count"] == 1
    assert payload["ledger_child_event_count"] == 2


def test_event_ledger_rejects_open_child(tmp_path: Path) -> None:
    """确认 publication-oriented replay 不接受仍活动的子代理。"""
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(ledger, launch_record())
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ledger_active_count"] == 1
    assert any("ledger_active_children" in issue for issue in payload["issues"])


def test_event_ledger_rejects_orphan_close(tmp_path: Path) -> None:
    """确认 close 必须匹配同一账本中的活动代理。"""
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(ledger, close_record())
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_orphan_close" in issue for issue in json.loads(result.stdout)["issues"])


def test_event_ledger_accepts_resume_then_closes_again(tmp_path: Path) -> None:
    """确认已关闭同一代理可 resume, 但必须再次关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    resume = launch_record(
        event="resume",
        timestamp_utc="2026-07-17T18:12:00Z",
        role="M11-GOVERNANCE-TEST-W1-FOLLOWUP",
    )
    followup_close = close_record(
        timestamp_utc="2026-07-17T18:13:00Z",
        role="M11-GOVERNANCE-TEST-W1-FOLLOWUP",
    )
    write_ledger(ledger, launch_record(), close_record(), resume, followup_close)
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_active_count"] == 0


def test_event_ledger_rejects_duplicate_launch(tmp_path: Path) -> None:
    """确认同一 agent_id 不能重复 launch。"""
    ledger = tmp_path / "ledger.jsonl"
    duplicate = launch_record(timestamp_utc="2026-07-17T18:11:00Z")
    write_ledger(ledger, launch_record(), duplicate)
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_duplicate_launch" in issue for issue in json.loads(result.stdout)["issues"])


def test_event_ledger_rejects_resume_while_agent_is_open(tmp_path: Path) -> None:
    """确认 resume 不能覆盖仍活动的同一 agent_id。"""
    ledger = tmp_path / "ledger.jsonl"
    resume = launch_record(event="resume", timestamp_utc="2026-07-17T18:11:00Z")
    write_ledger(ledger, launch_record(), resume)
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_duplicate_open" in issue for issue in json.loads(result.stdout)["issues"])


@pytest.mark.parametrize(
    ("overrides", "expected_issue"),
    [
        ({"model": "gpt-5.6"}, "ledger_routing_drift"),
        ({"reasoning": "max"}, "ledger_routing_drift"),
        ({"depth": 2}, "ledger_routing_drift"),
        ({"descendants_allowed": True}, "ledger_routing_drift"),
        ({"status": "closed"}, "ledger_routing_drift"),
        ({"timestamp_utc": "not-a-timestamp"}, "ledger_invalid_timestamp"),
    ],
)
def test_event_ledger_rejects_bad_route_or_timestamp(
    tmp_path: Path, overrides: dict[str, object], expected_issue: str
) -> None:
    """确认 M11 launch 路由和 UTC 时间戳偏移均失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    write_ledger(ledger, launch_record(**overrides), close_record())
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any(expected_issue in issue for issue in json.loads(result.stdout)["issues"])


def test_event_ledger_rejects_missing_schema_field(tmp_path: Path) -> None:
    """确认缺少 canonical launch 字段时失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    launch = launch_record()
    del launch["depth"]
    write_ledger(ledger, launch, close_record())
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_missing_fields" in issue for issue in json.loads(result.stdout)["issues"])


def test_publication_rejects_missing_configured_ledger(tmp_path: Path) -> None:
    """确认 clean checkout 缺少 ignored configured ledger 时 publication 失败关闭。"""
    root = make_publication_root(tmp_path, Path("runs/tmp/m11/missing.jsonl"))
    result = run_validator_at(root, "--ledger-only", "--publication")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ledger_mode"] == "configured_publication"
    assert payload["ledger_status"] == "missing"
    assert payload["ledger_record_count"] == 0
    assert any("missing_configured_ledger" in issue for issue in payload["issues"])


def test_publication_rejects_empty_configured_ledger(tmp_path: Path) -> None:
    """确认 publication 不接受 ledger_record_count 为零。"""
    ledger = tmp_path / "publication-root" / "runs/tmp/m11/empty.jsonl"
    ledger.parent.mkdir(parents=True, exist_ok=True)
    ledger.write_text("", encoding="utf-8")
    root = make_publication_root(tmp_path, Path("runs/tmp/m11/empty.jsonl"))
    result = run_validator_at(root, "--ledger-only", "--publication")
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["ledger_record_count"] == 0
    assert "ledger_empty" in payload["issues"]


def test_publication_accepts_terminal_configured_ledger(tmp_path: Path) -> None:
    """确认 publication 从 dispatch memory 加载并回放非空终态账本。"""
    relative = Path("runs/tmp/m11/terminal.jsonl")
    ledger = tmp_path / "publication-root" / relative
    ledger.parent.mkdir(parents=True, exist_ok=True)
    write_ledger(ledger, launch_record(), close_record())
    root = make_publication_root(tmp_path, relative)
    result = run_validator_at(root, "--ledger-only", "--publication")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["ledger_status"] == "valid"
    assert payload["ledger_record_count"] == 2
    assert payload["ledger_active_count"] == 0


def test_actual_configured_ledger_obeys_publication_semantics() -> None:
    """直接检查当前 ignored evidence; clean checkout 缺失时也必须明确失败关闭。"""
    result = run_validator("--publication")
    payload = json.loads(result.stdout)
    assert payload["ledger_mode"] == "configured_publication"
    assert payload["ledger_path"] == str(CONFIGURED_LEDGER)
    if payload["ledger_status"] == "missing":
        assert result.returncode == 1
        assert any("missing_configured_ledger" in issue for issue in payload["issues"])
    else:
        assert payload["ledger_record_count"] > 0
        if payload["ledger_active_count"] == 0:
            assert result.returncode == 0, result.stdout + result.stderr
        else:
            assert result.returncode == 1
            assert any("ledger_active_children" in issue for issue in payload["issues"])
