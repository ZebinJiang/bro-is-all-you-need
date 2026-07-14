"""验证活跃模型路由策略和线程账本。"""

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
    """确认非 President 全部使用 sol/medium。"""
    result = run_validator()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["owner_model"] == "gpt-5.6-sol"
    assert payload["owner_reasoning"] == "medium"
    assert payload["goal_manager_reasoning"] == "xhigh"
    assert payload["execution_reasoning"] == "medium"
    assert payload["manager_return_reasoning"] == "medium"


def test_active_model_routing_policy_accepts_matching_positional_root() -> None:
    """确认 Manager 命令末尾的冗余仓库根保持向后兼容。"""
    result = run_validator(".")
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["active_file_count"] == 28


def routing_record(**overrides: object) -> dict[str, object]:
    """构造切换后的最小合法路由记录。"""
    record: dict[str, object] = {
        "thread_name": "smoke-execution",
        "policy_name": "autovla-sol-medium-agents-sol-xhigh-president-manager",
        "purpose": "bounded routing smoke",
        "creation_timestamp": "2026-07-14T03:41:21Z",
        "route_role": "execution",
        "execution_model": "gpt-5.6-sol",
        "execution_reasoning": "medium",
        "return_model": "gpt-5.6-sol",
        "return_reasoning": "medium",
        "return_route": "same_thread_medium",
        "artifact_path": "runs/tmp/smoke/execution.json",
        "return_path": "runs/tmp/smoke/return.json",
        "blocker_count": 0,
        "final_return_count": 1,
        "retirement_status": "retired",
        "bootstrap_validated_before_create": True,
    }
    record.update(overrides)
    return record


def test_routing_ledger_accepts_historical_then_sol_medium(tmp_path: Path) -> None:
    """确认切换前历史记录保持有效且新记录强制新策略。"""
    ledger = tmp_path / "ledger.jsonl"
    historical = routing_record(
        policy_name="autovla-sol-xhigh-worker-luna-max-owner-sol-xhigh-return",
        creation_timestamp="2026-07-14T03:23:06Z",
        execution_reasoning="xhigh",
        return_reasoning="xhigh",
        return_route="same_thread_xhigh",
    )
    current = routing_record()
    ledger.write_text(
        json.dumps(historical) + "\n" + json.dumps(current) + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_record_count"] == 2


def test_routing_ledger_accepts_post_cutover_sol_medium(tmp_path: Path) -> None:
    """确认切换后的 Owner 与 worker 均可使用 sol/medium。"""
    ledger = tmp_path / "ledger.jsonl"
    records = [
        routing_record(thread_name="worker"),
        routing_record(thread_name="owner", route_role="owner_execution"),
    ]
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_record_count"] == 2


def test_routing_ledger_rejects_post_cutover_xhigh(tmp_path: Path) -> None:
    """确认切换后的普通 xhigh 记录失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            routing_record(
                execution_reasoning="xhigh",
                return_reasoning="xhigh",
                return_route="same_thread_xhigh",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_post_cutover_luna_max(tmp_path: Path) -> None:
    """确认切换后的 luna/max Owner 记录失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            routing_record(
                route_role="owner_execution",
                execution_model="gpt-5.6-luna",
                execution_reasoning="max",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])
