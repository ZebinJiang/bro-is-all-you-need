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
    """确认执行、President 和 Manager-facing return 使用各自显式路由。"""
    result = run_validator()
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["result"] == "PASS"
    assert payload["model"] == "gpt-5.6-sol"
    assert payload["owner_model"] == "gpt-5.6-sol"
    assert payload["owner_reasoning"] == "medium"
    assert payload["president_manager_reasoning"] == "max"
    assert payload["execution_reasoning"] == "medium"
    assert payload["manager_return_reasoning"] == "max"
    assert payload["validation_policy_name"] == "autovla-architecture-first-validation"
    assert payload["default_milestone_mode"] == "architectural_construction_first"


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
        "policy_name": "autovla-sol-medium-execution-max-president-max-return",
        "purpose": "bounded routing smoke",
        "creation_timestamp": "2026-07-14T08:27:39Z",
        "route_role": "execution",
        "execution_model": "gpt-5.6-sol",
        "execution_reasoning": "medium",
        "return_model": "gpt-5.6-sol",
        "return_reasoning": "max",
        "return_route": "same_thread_max",
        "artifact_path": "runs/tmp/smoke/execution.json",
        "return_path": "runs/tmp/smoke/return.json",
        "blocker_count": 0,
        "final_return_count": 1,
        "retirement_status": "retired",
        "bootstrap_validated_before_create": True,
    }
    record.update(overrides)
    return record


def test_routing_ledger_accepts_historical_then_current_policy(tmp_path: Path) -> None:
    """确认切换前历史记录保持有效且新记录强制新策略。"""
    ledger = tmp_path / "ledger.jsonl"
    historical = routing_record(
        policy_name="autovla-sol-medium-agents-sol-xhigh-president-manager",
        creation_timestamp="2026-07-14T08:00:00Z",
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


def test_routing_ledger_accepts_medium_execution_and_max_return(tmp_path: Path) -> None:
    """确认切换后的 Owner 与 worker 均为 medium 执行、max 返回。"""
    ledger = tmp_path / "ledger.jsonl"
    records = [
        routing_record(thread_name="worker"),
        routing_record(thread_name="owner", route_role="owner_execution"),
    ]
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["ledger_record_count"] == 2


def test_routing_ledger_accepts_one_max_return_synthesizer(tmp_path: Path) -> None:
    """确认运行时无法切换时可使用一个只读 max return synthesizer。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            routing_record(
                thread_name="return-synthesizer",
                route_role="return_synthesizer",
                execution_reasoning="max",
                return_route="return_synthesizer_max",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr


def test_routing_ledger_accepts_execution_plus_one_return_synthesizer(tmp_path: Path) -> None:
    """确认执行记录与唯一 synthesizer 记录可同时保留。"""
    ledger = tmp_path / "ledger.jsonl"
    records = [
        routing_record(thread_name="worker", return_route="return_synthesizer_max"),
        routing_record(
            thread_name="return-synthesizer",
            route_role="return_synthesizer",
            execution_reasoning="max",
            return_route="return_synthesizer_max",
        ),
    ]
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 0, result.stdout + result.stderr


def test_routing_ledger_rejects_non_president_execution_xhigh(tmp_path: Path) -> None:
    """确认切换后的普通执行 xhigh 记录失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            routing_record(
                execution_reasoning="xhigh",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_medium_manager_return(tmp_path: Path) -> None:
    """确认 Manager-facing return 回退到 medium 时失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(routing_record(return_reasoning="medium", return_route="same_thread_medium"))
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_post_cutover_luna_execution(tmp_path: Path) -> None:
    """确认切换后的 luna 执行记录失败关闭。"""
    ledger = tmp_path / "ledger.jsonl"
    ledger.write_text(
        json.dumps(
            routing_record(
                route_role="owner_execution",
                execution_model="gpt-5.6-luna",
            )
        )
        + "\n",
        encoding="utf-8",
    )
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert any("ledger_routing_drift" in issue for issue in json.loads(result.stdout)["issues"])


def test_routing_ledger_rejects_two_return_synthesizers(tmp_path: Path) -> None:
    """确认单任务最多只有一个 return synthesizer。"""
    ledger = tmp_path / "ledger.jsonl"
    records = [
        routing_record(
            thread_name=f"return-synthesizer-{index}",
            route_role="return_synthesizer",
            execution_reasoning="max",
            return_route="return_synthesizer_max",
        )
        for index in range(2)
    ]
    ledger.write_text("".join(json.dumps(record) + "\n" for record in records), encoding="utf-8")
    result = run_validator("--ledger-only", "--ledger", str(ledger))
    assert result.returncode == 1
    assert "ledger_return_synthesizer_count_gt_1=2" in json.loads(result.stdout)["issues"]
