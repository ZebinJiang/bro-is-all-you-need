"""验证 M10 活跃模型路由和临时子代理终态账本。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def repo_root() -> Path:
    """返回当前测试对应的仓库根目录。"""
    return Path(__file__).resolve().parents[2]


def run_validator(*args: str) -> subprocess.CompletedProcess[str]:
    """通过当前解释器运行治理校验器。"""
    root = repo_root()
    return subprocess.run(
        [
            sys.executable,
            str(root / "scripts/coordination/validate_model_routing.py"),
            "--root",
            str(root),
            *args,
        ],
        check=False,
        capture_output=True,
        text=True,
    )


def test_active_model_routing_policy_passes() -> None:
    """确认 President max、临时子代理 medium 和单次四人审查。"""
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
        "autovla-m10-production-model-zoo-runtime-validation"
    )
    assert payload["default_milestone_mode"] == (
        "architectural_construction_first_manager_controlled_parallel_execution"
    )


def test_active_model_routing_policy_accepts_matching_positional_root() -> None:
    """确认 Manager 命令末尾的冗余仓库根保持向后兼容。"""
    result = run_validator(".")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["active_file_count"] == 18


def routing_record(**overrides: object) -> dict[str, object]:
    """构造 M10 切换后的最小合法终态记录。"""
    record: dict[str, object] = {
        "agent_id": "m10-smoke-agent",
        "role": "research_agent",
        "wave": "wave_1",
        "creation_timestamp": "2026-07-15T08:50:02Z",
        "policy_name": "autovla-manager-max-medium-ephemeral-children",
        "model": "gpt-5.6-sol",
        "reasoning": "medium",
        "return_model": "gpt-5.6-sol",
        "return_reasoning": "medium",
        "inherit_parent_model": False,
        "inherit_parent_reasoning": False,
        "source_sha": "0" * 40,
        "worktree": "/repo/.worktrees/m10-read-only",
        "branch": "none",
        "owned_paths": [],
        "forbidden_paths": ["integration-branch", "pr-mutation"],
        "evidence_root": "runs/tmp/m10/agents/m10-smoke-agent",
        "expected_handoff": "runs/tmp/m10/agents/m10-smoke-agent/handoff.yaml",
        "expected_commit_or_no_commit": "none",
        "close_condition": "one structured handoff",
        "status": "closed",
        "final_return_count": 1,
    }
    record.update(overrides)
    return record


def test_routing_ledger_accepts_historical_then_current_policy(tmp_path: Path) -> None:
    """确认切换前记录保持历史有效且 M10 记录强制 schema v6。"""
    ledger = tmp_path / "ledger.jsonl"
    historical = routing_record(
        creation_timestamp="2026-07-14T08:00:00Z",
        policy_name="autovla-sol-medium-agents-sol-xhigh-president-manager",
        reasoning="xhigh",
        return_reasoning="xhigh",
    )
    ledger.write_text(
        json.dumps(historical) + "\n" + json.dumps(routing_record()) + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_record_count"] == 2


def test_routing_ledger_accepts_all_prompt_scoped_roles(tmp_path: Path) -> None:
    """确认所有 M10 临时角色均使用 medium 执行和返回。"""
    ledger = tmp_path / "ledger.jsonl"
    roles = (
        "research_agent",
        "source_writer",
        "asset_agent",
        "compute_agent",
        "validation_agent",
        "final_review_agent",
        "repair_agent",
    )
    records = [routing_record(agent_id=f"agent-{role}", role=role) for role in roles]
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_record_count"] == len(roles)


def test_routing_ledger_rejects_parent_reasoning_inheritance(tmp_path: Path) -> None:
    """确认子代理不能继承 President max 路由。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(routing_record(reasoning="max", inherit_parent_reasoning=True)) + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_elevated_child_return(tmp_path: Path) -> None:
    """确认子代理最终返回不能提升到 xhigh 或 max。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(routing_record(return_reasoning="xhigh")) + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_unclosed_child(tmp_path: Path) -> None:
    """确认终态账本不接受仍活动的子代理。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(json.dumps(routing_record(status="running")) + "\n", encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_child_not_closed" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_persistent_owner_role(tmp_path: Path) -> None:
    """确认 M10 账本不接受 persistent Owner 路由。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(routing_record(role="owner_execution")) + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_invalid_role" in issue for issue in json.loads(result.stdout)["issues"])
