"""校验 M10 活跃模型路由、临时子代理生命周期和并行边界。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypeGuard

GOAL: Final = "AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001"
POLICY_PATH: Final = Path("coordination/MODEL_ROUTING_POLICY.yaml")
VALIDATION_POLICY_PATH: Final = Path("coordination/VALIDATION_POLICY.yaml")
LIFECYCLE_POLICY_PATH: Final = Path("coordination/AGENT_LIFECYCLE_POLICY.yaml")
PARALLEL_POLICY_PATH: Final = Path("coordination/PARALLEL_EXECUTION_POLICY.yaml")

EXPECTED_POLICY: Final[dict[str, object]] = {
    "schema_version": 6,
    "policy_name": "autovla-manager-max-medium-ephemeral-children",
    "active_goal": GOAL,
    "cutover_timestamp": "2026-07-15T08:50:01Z",
    "ledger_cutover_rule": (
        "creation_timestamp_before_cutover_is_historical_otherwise_schema_v6_required"
    ),
    "model": "gpt-5.6-sol",
    "president_manager_model": "gpt-5.6-sol",
    "president_manager_reasoning": "max",
    "president_manager_route_immutable": True,
    "child_execution_model": "gpt-5.6-sol",
    "child_execution_reasoning": "medium",
    "child_return_model": "gpt-5.6-sol",
    "child_return_reasoning": "medium",
    "inherit_parent_model": False,
    "inherit_parent_reasoning": False,
    "implicit_reasoning_escalation": False,
    "persistent_owners_enabled": False,
    "automatic_owner_fanout": False,
    "manager_return_model": "gpt-5.6-sol",
    "manager_return_reasoning": "medium",
    "default_milestone_mode": (
        "architectural_construction_first_manager_controlled_parallel_execution"
    ),
    "validation_policy": str(VALIDATION_POLICY_PATH),
    "lifecycle_policy": str(LIFECYCLE_POLICY_PATH),
    "parallel_execution_policy": str(PARALLEL_POLICY_PATH),
    "final_review_agent_count": 4,
    "final_review_swarm_count": 1,
    "second_review_swarm_allowed": False,
    "focused_repair_waves_until_acceptance": True,
    "manager_only_integration_and_publication": True,
}

EXPECTED_VALIDATION_POLICY: Final[dict[str, object]] = {
    "schema_version": 3,
    "policy_name": "autovla-m10-production-model-zoo-runtime-validation",
    "active_goal": GOAL,
    "default_milestone_mode": (
        "architectural_construction_first_manager_controlled_parallel_execution"
    ),
    "source_accurate_architecture_first": True,
    "official_asset_checkpoint_compatibility_required": True,
    "real_cuda_validation_primary": True,
    "real_backend_consumption_required_for_full_status": True,
    "distributed_runtime_required_for_full_status": True,
    "cross_node_runtime_required_for_full_status": True,
    "efficiency_evidence_required_for_full_status": True,
    "remote_ci_required_for_draft_publication": False,
    "cpu_model_runtime_required": False,
    "broad_suite_required": False,
    "coverage_campaign_required": False,
    "fsdp_or_fsdp2_supported": False,
    "backend_winner_required": False,
    "final_review_agent_count": 4,
    "final_review_swarm_count": 1,
    "second_review_swarm_allowed": False,
    "focused_repair_waves_until_acceptance": True,
    "active_model_families": ["gr00t_n1d6", "gr00t_n1d7", "pi0_5"],
    "deferred_model_families": ["pi0", "pi0_fast"],
    "canonical_model_asset_root": "/home/cz-jzb/workspace/vla-flywheel/base_model",
    "model_asset_tracking_allowed": False,
    "training_implicit_asset_download_allowed": False,
    "remote_model_code_allowed": False,
    "arbitrary_pickle_allowed": False,
}

EXPECTED_LIFECYCLE_POLICY: Final[dict[str, object]] = {
    "schema_version": 6,
    "policy_name": "autovla-ephemeral-child-lifecycle",
    "active_goal": GOAL,
    "startup_cleanup_required": True,
    "persistent_owners": False,
    "automatic_owner_fanout": False,
    "current_prompt_scope_required": True,
    "reusable_after_completion": False,
    "close_on_task_completion": True,
    "remove_terminal_from_active_registry": True,
    "wave_barrier_requires_prior_children_closed": True,
    "candidate_freeze_requires_zero_active_children": True,
    "review_start_requires_zero_active_children": True,
    "repair_start_requires_reviewers_closed": True,
    "publication_requires_zero_active_children": True,
}

EXPECTED_PARALLEL_POLICY: Final[dict[str, object]] = {
    "schema_version": 6,
    "policy_name": "autovla-manager-controlled-disjoint-parallelism",
    "active_goal": GOAL,
    "max_active_children": 6,
    "max_source_writers": 3,
    "max_shared_core_writers": 1,
    "max_compute_agents": 6,
    "max_review_agents": 4,
    "max_repair_writers": 4,
    "max_integration_branch_writers": 1,
    "isolated_worktree_required_for_writers": True,
    "common_frozen_source_sha_required": True,
    "disjoint_owned_paths_required": True,
    "overlapping_parallel_writes_allowed": False,
    "child_integration_branch_write_allowed": False,
    "child_pr_mutation_allowed": False,
    "child_cross_branch_merge_allowed": False,
    "manager_only_integration_and_publication": True,
}

ACTIVE_TEXT_FILES: Final[tuple[Path, ...]] = (
    Path("AGENTS.md"),
    Path("docs/coordination/CODEX_MANAGER_GOVERNANCE.md"),
    Path("docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md"),
    Path("docs/coordination/OWNER_DISPATCH_GOVERNANCE.md"),
    Path("docs/coordination/TEAM_OPERATING_MODEL.md"),
    Path("docs/coordination/MANAGER_ENTRYPOINT.md"),
    Path("docs/coordination/OWNER_RUNTIME_SMOKE.md"),
    Path("docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md"),
    Path("docs/coordination/NEW_THREAD_BOOTSTRAP.md"),
    Path(".agents/instructions/workflow.instructions.md"),
    Path(".agents/skills/thread-team/SKILL.md"),
)

ACTIVE_MACHINE_FILES: Final[tuple[Path, ...]] = (
    POLICY_PATH,
    VALIDATION_POLICY_PATH,
    LIFECYCLE_POLICY_PATH,
    PARALLEL_POLICY_PATH,
    Path("coordination/THREAD_REGISTRY.yaml"),
    Path("coordination/OWNER_DISPATCH_MEMORY.yaml"),
    Path("coordination/OWNER_ROLE_REGISTRY.yaml"),
)

CURRENT_ROUTE_ROLES: Final[frozenset[str]] = frozenset(
    {
        "research_agent",
        "source_writer",
        "asset_agent",
        "compute_agent",
        "validation_agent",
        "final_review_agent",
        "repair_agent",
    }
)

LEDGER_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "agent_id",
        "role",
        "wave",
        "creation_timestamp",
        "policy_name",
        "model",
        "reasoning",
        "return_model",
        "return_reasoning",
        "inherit_parent_model",
        "inherit_parent_reasoning",
        "source_sha",
        "worktree",
        "branch",
        "owned_paths",
        "forbidden_paths",
        "evidence_root",
        "expected_handoff",
        "expected_commit_or_no_commit",
        "close_condition",
        "status",
        "final_return_count",
    }
)


def _load_json(path: Path) -> object:
    """读取采用 YAML 1.2 兼容 JSON 语法的机器策略。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _is_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态值是否为映射。"""
    return isinstance(value, Mapping)


def _string_mapping(value: object) -> dict[str, object] | None:
    """验证映射键并返回字符串键副本。"""
    if not _is_mapping(value):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def _validate_json_policy(
    root: Path,
    relative: Path,
    expected: Mapping[str, object],
    label: str,
    issues: list[str],
) -> dict[str, object]:
    """校验一份严格 JSON 机器策略的关键字段。"""
    path = root / relative
    if not path.is_file():
        issues.append(f"missing_{label}={relative}")
        return {}
    try:
        policy = _string_mapping(_load_json(path))
    except (json.JSONDecodeError, OSError) as exc:
        issues.append(f"invalid_{label}={relative}:{exc}")
        return {}
    if policy is None:
        issues.append(f"{label}_not_object")
        return {}
    for field, expected_value in expected.items():
        actual = policy.get(field)
        if actual != expected_value:
            issues.append(f"{label}_drift={field}:{actual!r}!={expected_value!r}")
    return policy


def _validate_active_files(root: Path, issues: list[str]) -> None:
    """确认活动文档和模板声明 M10 临时子代理覆盖。"""
    for relative in ACTIVE_TEXT_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_file={relative}")
            continue
        text = path.read_text(encoding="utf-8")
        normalized = text.lower()
        required = ("gpt-5.6-sol", "medium", "persistent")
        for marker in required:
            if marker not in normalized:
                issues.append(f"missing_active_marker={relative}:{marker}")
        if "m10" not in normalized and "prompt-scoped" not in normalized:
            issues.append(f"missing_active_marker={relative}:m10_or_prompt_scoped")

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    root_markers = (
        "President Manager route is immutable",
        "`gpt-5.6-sol / max`",
        "`gpt-5.6-sol / medium`",
        "must not inherit",
        "Persistent Owner threads and automatic Owner fan-out are disabled",
        "Exactly one fresh four-agent final review swarm",
        "no second review swarm is allowed",
        "Publication requires active-child count zero",
        "NO_BACKEND_WINNER",
    )
    normalized_agents = " ".join(agents.lower().split())
    for marker in root_markers:
        if marker.lower() not in normalized_agents:
            issues.append(f"missing_root_protocol_marker={marker}")

    registry = (root / "coordination/THREAD_REGISTRY.yaml").read_text(encoding="utf-8")
    registry_markers = (
        "thread_registry_schema_version: 2",
        "registry_publication_mode: prompt_scoped_ephemeral_template",
        "persistent_owner_threads_enabled: false",
        "automatic_owner_fanout_enabled: false",
        "active_children: []",
        "inherit_parent_model: false",
        "inherit_parent_reasoning: false",
    )
    for marker in registry_markers:
        if marker not in registry:
            issues.append(f"registry_drift={marker}")
    if "/home/" in registry or "thread_id: 019" in registry:
        issues.append("registry_contains_runtime_identity")

    memory = (root / "coordination/OWNER_DISPATCH_MEMORY.yaml").read_text(encoding="utf-8")
    memory_markers = (
        "persistent_owner_dispatch:",
        "enabled: false",
        "prompt_scoped_child_dispatch:",
        "child_execution_reasoning: medium",
        "child_return_reasoning: medium",
        "active_child_count: 0",
    )
    for marker in memory_markers:
        if marker not in memory:
            issues.append(f"dispatch_memory_drift={marker}")

    roles = (root / "coordination/OWNER_ROLE_REGISTRY.yaml").read_text(encoding="utf-8")
    role_markers = (
        "active_dispatch_mode: prompt_scoped_ephemeral_children",
        "persistent_owner_dispatch_enabled: false",
        "historical_role_catalog_only: true",
        "president_manager_may_spawn_prompt_scoped_children: true",
    )
    for marker in role_markers:
        if marker not in roles:
            issues.append(f"owner_role_registry_drift={marker}")


def _parse_timestamp(value: object, line_number: int, issues: list[str]) -> datetime | None:
    """解析 UTC 时间戳; 无效记录失败关闭。"""
    if not isinstance(value, str):
        issues.append(f"ledger_invalid_creation_timestamp={line_number}")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(f"ledger_invalid_creation_timestamp={line_number}")
        return None
    if parsed.tzinfo is None:
        issues.append(f"ledger_naive_creation_timestamp={line_number}")
        return None
    return parsed.astimezone(timezone.utc)


def _validate_ledger(path: Path, issues: list[str]) -> int:
    """校验 M10 切换后的临时子代理终态账本。"""
    count = 0
    current_epoch_seen = False
    cutover = datetime.fromisoformat(
        str(EXPECTED_POLICY["cutover_timestamp"]).replace("Z", "+00:00")
    )
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        count += 1
        try:
            record = _string_mapping(json.loads(line))
        except json.JSONDecodeError:
            issues.append(f"ledger_invalid_json={line_number}")
            continue
        if record is None:
            issues.append(f"ledger_record_not_object={line_number}")
            continue
        created_at = _parse_timestamp(record.get("creation_timestamp"), line_number, issues)
        if created_at is None:
            continue
        if created_at < cutover:
            continue
        current_epoch_seen = True
        missing = sorted(LEDGER_REQUIRED_FIELDS - record.keys())
        if missing:
            issues.append(f"ledger_missing_fields={line_number}:{','.join(missing)}")
            continue
        expected = {
            "policy_name": EXPECTED_POLICY["policy_name"],
            "model": "gpt-5.6-sol",
            "reasoning": "medium",
            "return_model": "gpt-5.6-sol",
            "return_reasoning": "medium",
            "inherit_parent_model": False,
            "inherit_parent_reasoning": False,
        }
        for field, expected_value in expected.items():
            if record.get(field) != expected_value:
                issues.append(
                    f"ledger_routing_drift={line_number}:{field}:"
                    f"{record.get(field)!r}!={expected_value!r}"
                )
        if record.get("role") not in CURRENT_ROUTE_ROLES:
            issues.append(f"ledger_invalid_role={line_number}:{record.get('role')}")
        if record.get("status") != "closed":
            issues.append(f"ledger_child_not_closed={line_number}:{record.get('status')}")
        if record.get("final_return_count") != 1:
            issues.append(f"ledger_invalid_final_return_count={line_number}")
        for field in ("owned_paths", "forbidden_paths"):
            if not isinstance(record.get(field), list):
                issues.append(f"ledger_invalid_list={line_number}:{field}")
    if count and not current_epoch_seen:
        issues.append("ledger_current_policy_epoch_missing")
    return count


def main() -> int:
    """运行治理策略校验并输出稳定 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--ledger-only", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("root_argument", nargs="?", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    if args.root_argument is not None and args.root_argument.resolve() != root:
        parser.error("positional root must match --root")
    issues: list[str] = []
    policy = _validate_json_policy(root, POLICY_PATH, EXPECTED_POLICY, "policy", issues)
    validation = _validate_json_policy(
        root,
        VALIDATION_POLICY_PATH,
        EXPECTED_VALIDATION_POLICY,
        "validation_policy",
        issues,
    )
    _validate_json_policy(
        root,
        LIFECYCLE_POLICY_PATH,
        EXPECTED_LIFECYCLE_POLICY,
        "lifecycle_policy",
        issues,
    )
    _validate_json_policy(
        root,
        PARALLEL_POLICY_PATH,
        EXPECTED_PARALLEL_POLICY,
        "parallel_policy",
        issues,
    )
    for field in (
        "default_milestone_mode",
        "final_review_agent_count",
        "final_review_swarm_count",
        "second_review_swarm_allowed",
        "focused_repair_waves_until_acceptance",
    ):
        if policy.get(field) != validation.get(field):
            issues.append(
                f"routing_validation_policy_drift={field}:"
                f"{policy.get(field)!r}!={validation.get(field)!r}"
            )
    if not args.ledger_only:
        _validate_active_files(root, issues)
    ledger_count = 0
    if args.ledger is not None:
        ledger_path = args.ledger if args.ledger.is_absolute() else root / args.ledger
        if not ledger_path.is_file():
            issues.append(f"missing_ledger={args.ledger}")
        else:
            ledger_count = _validate_ledger(ledger_path, issues)

    payload = {
        "result": "PASS" if not issues else "FAIL",
        "policy_path": str(POLICY_PATH),
        "policy_name": policy.get("policy_name"),
        "validation_policy_path": str(VALIDATION_POLICY_PATH),
        "validation_policy_name": validation.get("policy_name"),
        "default_milestone_mode": validation.get("default_milestone_mode"),
        "model": policy.get("model"),
        "owner_model": policy.get("owner_model"),
        "owner_reasoning": policy.get("owner_reasoning"),
        "president_manager_reasoning": policy.get("president_manager_reasoning"),
        "execution_reasoning": policy.get("child_execution_reasoning"),
        "manager_return_reasoning": policy.get("manager_return_reasoning"),
        "persistent_owners_enabled": policy.get("persistent_owners_enabled"),
        "final_review_agent_count": policy.get("final_review_agent_count"),
        "active_file_count": len(ACTIVE_TEXT_FILES) + len(ACTIVE_MACHINE_FILES),
        "ledger_record_count": ledger_count,
        "issues": issues,
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        output = args.output if args.output.is_absolute() else root / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
