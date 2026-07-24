"""校验 M12 活跃模型路由、临时子代理生命周期和并行边界。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypeGuard

import yaml

GOAL: Final = "AUTOVLA-M12-ARCHITECTURE-FIRST-RUNTIME-SUBSTRATE-" "OFFICIAL-FAMILY-ACTIVATION-001"
POLICY_PATH: Final = Path("coordination/MODEL_ROUTING_POLICY.yaml")
VALIDATION_POLICY_PATH: Final = Path("coordination/VALIDATION_POLICY.yaml")
LIFECYCLE_POLICY_PATH: Final = Path("coordination/AGENT_LIFECYCLE_POLICY.yaml")
PARALLEL_POLICY_PATH: Final = Path("coordination/PARALLEL_EXECUTION_POLICY.yaml")
DISPATCH_MEMORY_PATH: Final = Path("coordination/OWNER_DISPATCH_MEMORY.yaml")
LEDGER_SCHEMA: Final = "autovla-m12-child-lifecycle-events-v1"

EXPECTED_POLICY: Final[dict[str, object]] = {
    "schema_version": 7,
    "policy_name": "autovla-ultra-president-high-ephemeral-children",
    "active_goal": GOAL,
    "cutover_timestamp": "2026-07-24T03:13:22Z",
    "ledger_cutover_rule": (
        "creation_timestamp_before_cutover_is_historical_otherwise_schema_v7_required"
    ),
    "model": "gpt-5.6-sol",
    "president_manager_model": "gpt-5.6-sol",
    "president_manager_reasoning": "ultra",
    "president_manager_route_immutable": True,
    "child_execution_model": "gpt-5.6-sol",
    "child_execution_reasoning": "high",
    "child_return_model": "gpt-5.6-sol",
    "child_return_reasoning": "high",
    "inherit_parent_model": False,
    "inherit_parent_reasoning": False,
    "implicit_reasoning_escalation": False,
    "child_messages_can_mutate_president_route": False,
    "persistent_owners_enabled": False,
    "automatic_owner_fanout": False,
    "manager_return_model": "gpt-5.6-sol",
    "manager_return_reasoning": "ultra",
    "unsupported_route_behavior": "block_without_aliasing",
    "literal_route_enforcement_required": True,
    "routing_smoke_required_before_wave_1": True,
    "default_milestone_mode": (
        "architectural_construction_first_president_controlled_parallel_execution_"
        "official_family_runtime_activation"
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
    "schema_version": 7,
    "policy_name": "autovla-m12-official-family-runtime-activation-validation",
    "active_goal": GOAL,
    "default_milestone_mode": (
        "architectural_construction_first_president_controlled_parallel_execution_"
        "official_family_runtime_activation"
    ),
    "source_accurate_architecture_first": True,
    "official_asset_checkpoint_compatibility_required": True,
    "canonical_multi_receipt_readiness_evidence_required": True,
    "versioned_m11_readiness_reader_required": True,
    "checkpoint_loadable_torch_module_required": True,
    "isolated_family_runtime_profiles_required": True,
    "dataset_model_binding_required": True,
    "contract_fixture_must_not_claim_real_data": True,
    "contract_and_real_data_evidence_must_remain_distinct": True,
    "checkpoint_resume_required_for_full_status": True,
    "upstream_oracle_conformance_required_for_full_status": True,
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
    "canonical_runtime_environment_root": "/home/cz-jzb/workspace/vla-flywheel/.autovla_envs",
    "canonical_runtime_cache_root": "/home/cz-jzb/workspace/vla-flywheel/.autovla_cache",
    "model_asset_tracking_allowed": False,
    "training_implicit_asset_download_allowed": False,
    "remote_model_code_allowed": False,
    "arbitrary_pickle_allowed": False,
    "maximum_total_slurm_submissions": 128,
    "maximum_total_a100_gpu_hours": 1024,
    "maximum_active_a100_jobs": 8,
    "maximum_per_job_nodes": 2,
    "maximum_per_job_a100_gpus": 16,
    "maximum_wall_time_hours": 8,
    "maximum_causal_debug_submissions_per_active_family": 32,
}

EXPECTED_LIFECYCLE_POLICY: Final[dict[str, object]] = {
    "schema_version": 7,
    "policy_name": "autovla-m12-ephemeral-child-lifecycle",
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
    "schema_version": 7,
    "policy_name": "autovla-m12-president-controlled-disjoint-parallelism",
    "active_goal": GOAL,
    "max_active_children": 8,
    "max_source_writers": 4,
    "max_shared_core_writers": 1,
    "max_family_writers": 3,
    "max_environment_agents": 3,
    "max_asset_agents": 3,
    "max_compute_agents": 8,
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
    "shared_contract_writer_concurrency": 1,
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

CHILD_START_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "event",
        "timestamp_utc",
        "agent_id",
        "role",
        "wave",
        "model",
        "reasoning",
        "return_model",
        "return_reasoning",
        "inherit_parent_model",
        "inherit_parent_reasoning",
        "depth",
        "descendants_allowed",
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
    }
)
CHILD_CLOSE_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {"event", "timestamp_utc", "agent_id", "role", "descendants", "retired"}
)
CHILD_EVENTS: Final[frozenset[str]] = frozenset({"launch", "resume", "close"})


@dataclass(frozen=True)
class LedgerStats:
    """保存事件账本的确定性回放统计。"""

    record_count: int = 0
    child_event_count: int = 0
    non_child_event_count: int = 0
    historical_record_count: int = 0
    active_count: int = 0


def _load_yaml(path: Path) -> object:
    """使用质量环境固定的 PyYAML 读取机器治理文件。"""
    loaded: object = yaml.safe_load(path.read_text(encoding="utf-8"))
    return loaded


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


def _validate_yaml_policy(
    root: Path,
    relative: Path,
    expected: Mapping[str, object],
    label: str,
    issues: list[str],
) -> dict[str, object]:
    """校验一份结构化 YAML 机器策略的关键字段。"""
    path = root / relative
    if not path.is_file():
        issues.append(f"missing_{label}={relative}")
        return {}
    try:
        policy = _string_mapping(_load_yaml(path))
    except (OSError, yaml.YAMLError) as exc:
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


def _load_dispatch_memory(root: Path, issues: list[str]) -> dict[str, object]:
    """结构化读取 Owner Dispatch Memory, 拒绝非映射或无效 YAML。"""
    path = root / DISPATCH_MEMORY_PATH
    if not path.is_file():
        issues.append(f"missing_dispatch_memory={DISPATCH_MEMORY_PATH}")
        return {}
    try:
        memory = _string_mapping(_load_yaml(path))
    except (OSError, yaml.YAMLError) as exc:
        issues.append(f"invalid_dispatch_memory={DISPATCH_MEMORY_PATH}:{exc}")
        return {}
    if memory is None:
        issues.append("dispatch_memory_not_object")
        return {}
    return memory


def _validate_active_files(
    root: Path, dispatch_memory: Mapping[str, object], issues: list[str]
) -> None:
    """确认活动文档和模板声明 M12 临时子代理覆盖。"""
    for relative in ACTIVE_TEXT_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_file={relative}")
            continue
        text = path.read_text(encoding="utf-8")
        normalized = text.lower()
        required = ("gpt-5.6-sol", "ultra", "high", "persistent")
        for marker in required:
            if marker not in normalized:
                issues.append(f"missing_active_marker={relative}:{marker}")
        if "m12" not in normalized and "prompt-scoped" not in normalized:
            issues.append(f"missing_active_marker={relative}:m12_or_prompt_scoped")

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    root_markers = (
        "President Manager route is immutable",
        "`gpt-5.6-sol / ultra`",
        "`gpt-5.6-sol / high`",
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
        "thread_registry_schema_version: 7",
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

    persistent = _string_mapping(dispatch_memory.get("persistent_owner_dispatch"))
    prompt_scoped = _string_mapping(dispatch_memory.get("prompt_scoped_child_dispatch"))
    if persistent is None or persistent.get("enabled") is not False:
        issues.append("dispatch_memory_drift=persistent_owner_dispatch.enabled")
    expected_dispatch = {
        "enabled": True,
        "president_manager_reasoning": "ultra",
        "child_execution_reasoning": "high",
        "child_return_reasoning": "high",
        "inherit_parent_model": False,
        "inherit_parent_reasoning": False,
        "task_local_ledger_schema": LEDGER_SCHEMA,
        "publication_requires_ledger_replay": True,
        "publication_requires_zero_active_children": True,
    }
    if prompt_scoped is None:
        issues.append("dispatch_memory_drift=prompt_scoped_child_dispatch")
    else:
        for field, expected in expected_dispatch.items():
            if prompt_scoped.get(field) != expected:
                issues.append(
                    f"dispatch_memory_drift={field}:" f"{prompt_scoped.get(field)!r}!={expected!r}"
                )

    roles = (root / "coordination/OWNER_ROLE_REGISTRY.yaml").read_text(encoding="utf-8")
    role_markers = (
        "active_dispatch_mode: prompt_scoped_ephemeral_children",
        "persistent_owner_dispatch_enabled: false",
        "historical_role_catalog_only: true",
        "president_manager_may_spawn_prompt_scoped_children: true",
        "child_execution_reasoning: high",
        "child_return_reasoning: high",
        "president_manager_reasoning: ultra",
    )
    for marker in role_markers:
        if marker not in roles:
            issues.append(f"owner_role_registry_drift={marker}")


def _parse_timestamp(value: object, line_number: int, issues: list[str]) -> datetime | None:
    """解析 canonical UTC 时间戳; 无效或非 Z 格式记录失败关闭。"""
    if not isinstance(value, str) or not value.endswith("Z"):
        issues.append(f"ledger_invalid_timestamp={line_number}")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        issues.append(f"ledger_invalid_timestamp={line_number}")
        return None
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        issues.append(f"ledger_invalid_timestamp={line_number}")
        return None
    return parsed.astimezone(timezone.utc)


def _required_string(
    record: Mapping[str, object], field: str, line_number: int, issues: list[str]
) -> str | None:
    """读取必需非空字符串字段。"""
    value = record.get(field)
    if not isinstance(value, str) or not value:
        issues.append(f"ledger_invalid_field={line_number}:{field}")
        return None
    return value


def _validate_child_start(
    record: Mapping[str, object], line_number: int, issues: list[str]
) -> tuple[str, str] | None:
    """校验 launch/resume 的 M12 路由和深度契约。"""
    missing = sorted(CHILD_START_REQUIRED_FIELDS - record.keys())
    if missing:
        issues.append(f"ledger_missing_fields={line_number}:{','.join(missing)}")
        return None
    agent_id = _required_string(record, "agent_id", line_number, issues)
    role = _required_string(record, "role", line_number, issues)
    expected = {
        "model": "gpt-5.6-sol",
        "reasoning": "high",
        "return_model": "gpt-5.6-sol",
        "return_reasoning": "high",
        "inherit_parent_model": False,
        "inherit_parent_reasoning": False,
        "depth": 1,
        "descendants_allowed": False,
        "status": "active",
    }
    for field, expected_value in expected.items():
        if record.get(field) != expected_value:
            issues.append(
                f"ledger_routing_drift={line_number}:{field}:"
                f"{record.get(field)!r}!={expected_value!r}"
            )
    if agent_id is None or role is None:
        return None
    return agent_id, role


def _validate_child_close(
    record: Mapping[str, object], line_number: int, issues: list[str]
) -> tuple[str, str] | None:
    """校验 close 的退休、后代和残留进程约束。"""
    missing = sorted(CHILD_CLOSE_REQUIRED_FIELDS - record.keys())
    if missing:
        issues.append(f"ledger_missing_fields={line_number}:{','.join(missing)}")
        return None
    agent_id = _required_string(record, "agent_id", line_number, issues)
    role = _required_string(record, "role", line_number, issues)
    if record.get("retired") is not True:
        issues.append(f"ledger_child_not_retired={line_number}")
    if record.get("descendants") != 0:
        issues.append(f"ledger_nonzero_descendants={line_number}")
    if "residual_processes" in record and record.get("residual_processes") != 0:
        issues.append(f"ledger_nonzero_residual_processes={line_number}")
    if agent_id is None or role is None:
        return None
    return agent_id, role


def _validate_ledger(path: Path, issues: list[str]) -> LedgerStats:
    """按事件顺序回放 M12 子代理账本并要求终态无活动代理。"""
    record_count = 0
    child_event_count = 0
    non_child_event_count = 0
    historical_record_count = 0
    active_agents: dict[str, str] = {}
    known_agents: set[str] = set()
    previous_timestamp: datetime | None = None
    cutover = datetime.fromisoformat(
        str(EXPECTED_POLICY["cutover_timestamp"]).replace("Z", "+00:00")
    )
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        record_count += 1
        try:
            record = _string_mapping(json.loads(line))
        except json.JSONDecodeError:
            issues.append(f"ledger_invalid_json={line_number}")
            continue
        if record is None:
            issues.append(f"ledger_record_not_object={line_number}")
            continue
        timestamp = _parse_timestamp(record.get("timestamp_utc"), line_number, issues)
        if timestamp is None:
            continue
        if previous_timestamp is not None and timestamp < previous_timestamp:
            issues.append(f"ledger_timestamp_regression={line_number}")
        previous_timestamp = timestamp
        if timestamp < cutover:
            historical_record_count += 1
            continue
        event = record.get("event")
        if not isinstance(event, str) or not event:
            issues.append(f"ledger_invalid_event={line_number}")
            continue
        if event not in CHILD_EVENTS:
            non_child_event_count += 1
            if "agent_id" in record or "role" in record:
                issues.append(f"ledger_invalid_non_child_schema={line_number}:{event}")
            continue
        child_event_count += 1
        if event in {"launch", "resume"}:
            identity = _validate_child_start(record, line_number, issues)
            if identity is None:
                continue
            agent_id, role = identity
            if event == "launch":
                if agent_id in known_agents:
                    issues.append(f"ledger_duplicate_launch={line_number}:{agent_id}")
                    continue
                known_agents.add(agent_id)
            elif agent_id not in known_agents:
                issues.append(f"ledger_orphan_resume={line_number}:{agent_id}")
                continue
            if agent_id in active_agents:
                issues.append(f"ledger_duplicate_open={line_number}:{agent_id}")
                continue
            active_agents[agent_id] = role
            continue
        identity = _validate_child_close(record, line_number, issues)
        if identity is None:
            continue
        agent_id, role = identity
        active_role = active_agents.get(agent_id)
        if active_role is None:
            issues.append(f"ledger_orphan_close={line_number}:{agent_id}")
            continue
        if active_role != role:
            issues.append(f"ledger_close_role_mismatch={line_number}:{role!r}!={active_role!r}")
        del active_agents[agent_id]
    if record_count == 0:
        issues.append("ledger_empty")
    if active_agents:
        issues.append(f"ledger_active_children={','.join(sorted(active_agents))}")
    return LedgerStats(
        record_count=record_count,
        child_event_count=child_event_count,
        non_child_event_count=non_child_event_count,
        historical_record_count=historical_record_count,
        active_count=len(active_agents),
    )


def main() -> int:
    """运行治理策略校验并输出稳定 JSON。"""
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--ledger", type=Path)
    parser.add_argument("--publication", action="store_true")
    parser.add_argument("--ledger-only", action="store_true")
    parser.add_argument("--output", type=Path)
    parser.add_argument("root_argument", nargs="?", type=Path)
    args = parser.parse_args()

    root = args.root.resolve()
    if args.root_argument is not None and args.root_argument.resolve() != root:
        parser.error("positional root must match --root")
    if args.publication and args.ledger is not None:
        parser.error("--publication loads the configured ledger; do not pass --ledger")
    issues: list[str] = []
    policy = _validate_yaml_policy(root, POLICY_PATH, EXPECTED_POLICY, "policy", issues)
    validation = _validate_yaml_policy(
        root,
        VALIDATION_POLICY_PATH,
        EXPECTED_VALIDATION_POLICY,
        "validation_policy",
        issues,
    )
    _validate_yaml_policy(
        root,
        LIFECYCLE_POLICY_PATH,
        EXPECTED_LIFECYCLE_POLICY,
        "lifecycle_policy",
        issues,
    )
    _validate_yaml_policy(
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
    dispatch_memory = _load_dispatch_memory(root, issues)
    if not args.ledger_only:
        _validate_active_files(root, dispatch_memory, issues)

    ledger_mode = "not_requested"
    ledger_status = "not_requested"
    ledger_display_path: str | None = None
    ledger_stats = LedgerStats()
    ledger_argument = args.ledger
    if args.publication:
        ledger_mode = "configured_publication"
        prompt_scoped = _string_mapping(dispatch_memory.get("prompt_scoped_child_dispatch"))
        if prompt_scoped is None:
            issues.append("missing_configured_ledger=prompt_scoped_child_dispatch")
        else:
            configured_schema = prompt_scoped.get("task_local_ledger_schema")
            if configured_schema != LEDGER_SCHEMA:
                issues.append(
                    f"configured_ledger_schema_drift={configured_schema!r}!={LEDGER_SCHEMA!r}"
                )
            configured_path = prompt_scoped.get("task_local_ledger")
            if isinstance(configured_path, str) and configured_path:
                ledger_argument = Path(configured_path)
            else:
                issues.append("missing_configured_ledger=task_local_ledger")
    elif ledger_argument is not None:
        ledger_mode = "explicit"

    if ledger_argument is not None:
        ledger_display_path = str(ledger_argument)
        ledger_path = ledger_argument if ledger_argument.is_absolute() else root / ledger_argument
        if not ledger_path.is_file():
            issue_name = "missing_configured_ledger" if args.publication else "missing_ledger"
            issues.append(f"{issue_name}={ledger_argument}")
            ledger_status = "missing"
        else:
            ledger_issue_start = len(issues)
            ledger_stats = _validate_ledger(ledger_path, issues)
            if ledger_stats.active_count:
                ledger_status = "active_children"
            elif len(issues) > ledger_issue_start:
                ledger_status = "invalid"
            else:
                ledger_status = "valid"

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
        "ledger_mode": ledger_mode,
        "ledger_status": ledger_status,
        "ledger_path": ledger_display_path,
        "ledger_schema": LEDGER_SCHEMA if ledger_mode != "not_requested" else None,
        "ledger_record_count": ledger_stats.record_count,
        "ledger_child_event_count": ledger_stats.child_event_count,
        "ledger_non_child_event_count": ledger_stats.non_child_event_count,
        "ledger_historical_record_count": ledger_stats.historical_record_count,
        "ledger_active_count": ledger_stats.active_count,
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
