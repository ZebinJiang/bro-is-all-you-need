"""校验 AutoVLA 活跃模型路由与线程返回账本。"""

from __future__ import annotations

import argparse
import json
import re
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Final, TypeGuard

POLICY_PATH: Final = Path("coordination/MODEL_ROUTING_POLICY.yaml")
VALIDATION_POLICY_PATH: Final = Path("coordination/VALIDATION_POLICY.yaml")
EXPECTED_POLICY: Final[dict[str, object]] = {
    "schema_version": 5,
    "policy_name": "autovla-sol-medium-non-president-max-president",
    "cutover_timestamp": "2026-07-14T19:06:48Z",
    "ledger_cutover_rule": (
        "creation_timestamp_before_cutover_is_historical_" "otherwise_schema_v5_required"
    ),
    "model": "gpt-5.6-sol",
    "president_manager_model": "gpt-5.6-sol",
    "president_manager_reasoning": "max",
    "child_execution_model": "gpt-5.6-sol",
    "child_execution_reasoning": "medium",
    "owner_model": "gpt-5.6-sol",
    "owner_reasoning": "medium",
    "manager_return_model": "gpt-5.6-sol",
    "manager_return_reasoning": "medium",
    "same_thread_return_override": "not_required",
    "return_synthesizer_fallback": False,
    "return_synthesizer_model": "gpt-5.6-sol",
    "return_synthesizer_reasoning": "medium",
    "return_synthesizer_max_count": 0,
    "max_default": False,
    "max_forbidden": False,
    "active_max_roles": ["president_manager"],
    "explicit_reasoning_overrides_allowed": ["low", "medium", "high", "xhigh", "max"],
    "unsupported_post_cutover_route_behavior": "block_exact_requested_route_without_aliasing",
    "review_cadence": "architecture_first_single_final_review",
    "default_milestone_mode": "architectural_construction_first",
    "validation_policy": "coordination/VALIDATION_POLICY.yaml",
    "final_owner_fanout_count": 1,
    "consolidated_repair_pass_count": 1,
    "owner_rereview_after_repair": False,
}

EXPECTED_VALIDATION_POLICY: Final[dict[str, object]] = {
    "schema_version": 2,
    "policy_name": "autovla-architecture-first-validation",
    "active_goal": (
        "AUTOVLA-M9-ARCHITECTURE-COMPLETION-UNIFIED-SEMANTICS-" "UPSTREAM-INTEGRATION-001"
    ),
    "default_milestone_mode": "architectural_construction_first",
    "remote_ci_required_for_draft_publication": False,
    "remote_ci_polling_enabled_by_default": False,
    "cpu_model_runtime_supported": False,
    "cpu_model_runtime_required": False,
    "broad_suite_required_for_architecture_draft": False,
    "repeated_cross_validation_allowed_by_default": False,
    "upstream_numerical_parity_required_for_architecture_draft": False,
    "final_owner_fanout_count": 1,
    "consolidated_repair_pass_count": 1,
    "owner_rereview_after_repair": False,
    "gpu_runtime_partition": "a100",
    "gpu_runtime_tier": "bounded_architecture_smoke",
    "bounded_a100_initial_job_count": 1,
    "bounded_a100_repair_retry_count": 1,
    "distributed_runtime_matrix_required": False,
    "architecture_completion_requires_gpu_smoke_success": False,
    "valid_source_path_placeholder_is_blocker": True,
    "fsdp_or_fsdp2_supported": False,
    "backend_winner_required": False,
    "unchanged_external_state_reaudit_enabled_by_default": False,
    "production_model_and_training_runtime": "gpu_only",
    "supported_training_strategies": [
        "single_gpu",
        "distributed_data_parallel",
        "deepspeed_zero_1",
        "deepspeed_zero_2",
        "deepspeed_zero_3",
    ],
    "canonical_model_asset_root": "/home/cz-jzb/workspace/vla-flywheel/base_model",
    "model_asset_tracking_allowed": False,
    "training_implicit_asset_download_allowed": False,
    "remote_model_code_allowed": False,
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
    Path("coordination/loops/templates/TOP_LEVEL_LOOP_PROMPT.md"),
    Path("coordination/loops/templates/NEW_THREAD_START.md"),
    Path("coordination/loops/templates/OWNER_THREAD_START.md"),
    Path("coordination/loops/templates/OWNER_TASK_PACKET.md"),
    Path("coordination/loops/templates/plan.md"),
)

ACTIVE_VALIDATION_TEXT_FILES: Final[tuple[Path, ...]] = (
    Path("AGENTS.md"),
    Path("docs/coordination/CODEX_MANAGER_GOVERNANCE.md"),
    Path("docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md"),
    Path("docs/coordination/TEAM_OPERATING_MODEL.md"),
    Path("docs/coordination/MANAGER_ENTRYPOINT.md"),
    Path("coordination/loops/templates/TOP_LEVEL_LOOP_PROMPT.md"),
    Path("coordination/loops/templates/NEW_THREAD_START.md"),
    Path("coordination/loops/templates/OWNER_THREAD_START.md"),
    Path("coordination/loops/templates/plan.md"),
)

ACTIVE_STATE_FILES: Final[tuple[Path, ...]] = (
    Path("coordination/THREAD_REGISTRY.yaml"),
    Path("coordination/OWNER_DISPATCH_MEMORY.yaml"),
    Path("coordination/COMPUTE_EXECUTION_STATE.yaml"),
    Path("coordination/LOOP_STATE.yaml"),
    Path("coordination/OWNER_ROLE_REGISTRY.yaml"),
    Path("coordination/TOOL_MEMORY.yaml"),
    Path("coordination/LOOP_BACKLOG.yaml"),
    Path("coordination/PROGRAM_STATE.yaml"),
)

ACTIVE_TEMPLATE_YAML_FILES: Final[tuple[Path, ...]] = (
    Path("coordination/loops/templates/loop.yaml"),
    Path("coordination/loops/templates/OWNER_SUBAGENT_PLAN.yaml"),
)

ACTIVE_JSON_FILES: Final[tuple[Path, ...]] = (
    Path("coordination/loops/templates/loop.resolved.json"),
    Path("coordination/loops/templates/state.json"),
)

FORBIDDEN_DIRECTIVES: Final[tuple[tuple[re.Pattern[str], str], ...]] = (
    (re.compile(r"\bultra\b", re.IGNORECASE), "stale_ultra"),
    (re.compile(r"gpt-5\.6-luna", re.IGNORECASE), "stale_luna_route"),
    (
        re.compile(r"(?:owner_)?model_label\s*:\s*`?gpt-5\.6-luna", re.IGNORECASE),
        "stale_luna_model_label",
    ),
    (
        re.compile(r"active owner model label\s*:\s*`?gpt-5\.6-luna", re.IGNORECASE),
        "stale_luna_owner_start",
    ),
    (
        re.compile(r"(?:owner|child) execution reasoning\s*:\s*`?(?:xhigh|max)", re.IGNORECASE),
        "stale_non_president_xhigh_execution",
    ),
    (
        re.compile(
            r"Manager-facing return(?: model and)? reasoning\s*:\s*`?(?:xhigh|max)", re.IGNORECASE
        ),
        "stale_elevated_manager_return",
    ),
    (
        re.compile(r"President Manager(?: model and)? reasoning\s*:\s*`?xhigh", re.IGNORECASE),
        "stale_xhigh_president",
    ),
    (
        re.compile(r"(?:xhigh|max) Return Synthesizer", re.IGNORECASE),
        "stale_elevated_return_synthesizer",
    ),
    (
        re.compile(r"\bimplementation-first\b", re.IGNORECASE),
        "stale_implementation_first_cadence",
    ),
    (re.compile(r"active_model_label\s*:\s*gpt-5\.5", re.IGNORECASE), "gpt_5_5_default"),
)

ROUTING_SNIPPETS: Final[tuple[str, ...]] = (
    "active_model_label: gpt-5.6-sol",
    "validation_policy: coordination/VALIDATION_POLICY.yaml",
    "execution_reasoning: medium",
    "owner_model_label: gpt-5.6-sol",
    "owner_execution_reasoning: medium",
    "president_manager_model_label: gpt-5.6-sol",
    "manager_return_model_label: gpt-5.6-sol",
    "president_manager_reasoning: max",
    "manager_return_reasoning: medium",
    "same_thread_return_override: not_required",
    "return_synthesizer_fallback: false",
    "max_default: false",
    "max_forbidden: false",
)

LEDGER_REQUIRED_FIELDS: Final[frozenset[str]] = frozenset(
    {
        "thread_name",
        "purpose",
        "creation_timestamp",
        "route_role",
        "execution_model",
        "execution_reasoning",
        "return_model",
        "return_reasoning",
        "return_route",
        "artifact_path",
        "return_path",
        "blocker_count",
        "final_return_count",
        "retirement_status",
        "bootstrap_validated_before_create",
    }
)


def _load_json(path: Path) -> object:
    """读取严格 JSON; 规范 YAML 采用 YAML 1.2 兼容的 JSON 语法。"""
    return json.loads(path.read_text(encoding="utf-8"))


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态值是否可作为对象映射读取。"""

    return isinstance(value, Mapping)


def _string_object_mapping(value: object) -> dict[str, object] | None:
    """逐键验证动态 JSON 对象并返回字符串键副本。"""

    if not _is_object_mapping(value):
        return None
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            return None
        result[key] = item
    return result


def _validate_policy(root: Path, issues: list[str]) -> dict[str, object]:
    """校验机器可读策略的关键字段。"""
    path = root / POLICY_PATH
    if not path.is_file():
        issues.append(f"missing_policy={POLICY_PATH}")
        return {}
    policy = _string_object_mapping(_load_json(path))
    if policy is None:
        issues.append("policy_not_object")
        return {}
    for field, expected in EXPECTED_POLICY.items():
        actual = policy.get(field)
        if actual != expected:
            issues.append(f"policy_drift={field}:{actual!r}!={expected!r}")
    scope = policy.get("effective_scope")
    if not isinstance(scope, list) or not scope:
        issues.append("policy_effective_scope_missing")
    return policy


def _validate_validation_policy(root: Path, issues: list[str]) -> dict[str, object]:
    """校验 architecture-first 验证层策略。"""
    path = root / VALIDATION_POLICY_PATH
    if not path.is_file():
        issues.append(f"missing_validation_policy={VALIDATION_POLICY_PATH}")
        return {}
    policy = _string_object_mapping(_load_json(path))
    if policy is None:
        issues.append("validation_policy_not_object")
        return {}
    for field, expected in EXPECTED_VALIDATION_POLICY.items():
        actual = policy.get(field)
        if actual != expected:
            issues.append(f"validation_policy_drift={field}:{actual!r}!={expected!r}")
    advisory = policy.get("draft_architecture_advisory_limitations")
    blockers = policy.get("hard_blocker_classes")
    if not isinstance(advisory, list) or not advisory:
        issues.append("validation_policy_advisory_limitations_missing")
    if not isinstance(blockers, list) or not blockers:
        issues.append("validation_policy_hard_blockers_missing")
    return policy


def _validate_active_files(root: Path, issues: list[str]) -> None:
    """检查活跃 Markdown、状态和模板没有旧路由指令。"""
    for relative in ACTIVE_TEXT_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_file={relative}")
            continue
        text = path.read_text(encoding="utf-8")
        if "coordination/MODEL_ROUTING_POLICY.yaml" not in text:
            issues.append(f"missing_policy_reference={relative}")
        for pattern, label in FORBIDDEN_DIRECTIVES:
            if pattern.search(text):
                issues.append(f"forbidden_directive={relative}:{label}")

    for relative in ACTIVE_VALIDATION_TEXT_FILES:
        text = (root / relative).read_text(encoding="utf-8")
        if "coordination/VALIDATION_POLICY.yaml" not in text:
            issues.append(f"missing_validation_policy_reference={relative}")

    for relative in ACTIVE_STATE_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_state={relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in ROUTING_SNIPPETS:
            if snippet not in text:
                issues.append(f"state_routing_drift={relative}:{snippet}")
        for pattern, label in FORBIDDEN_DIRECTIVES:
            if pattern.search(text):
                issues.append(f"forbidden_state_directive={relative}:{label}")

    template_snippets = (
        "model_label: gpt-5.6-sol",
        "coordination/VALIDATION_POLICY.yaml",
        "execution_reasoning: medium",
        "owner_model_label: gpt-5.6-sol",
        "owner_execution_reasoning: medium",
        "president_manager_model_label: gpt-5.6-sol",
        "manager_return_model_label: gpt-5.6-sol",
        "president_manager_reasoning: max",
        "manager_return_reasoning: medium",
        "same_thread_return_override: not_required",
        "return_synthesizer_fallback: false",
        "max_default: false",
        "max_forbidden: false",
    )
    for relative in ACTIVE_TEMPLATE_YAML_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_template={relative}")
            continue
        text = path.read_text(encoding="utf-8")
        for snippet in template_snippets:
            if snippet not in text:
                issues.append(f"template_routing_drift={relative}:{snippet}")
        for pattern, label in FORBIDDEN_DIRECTIVES:
            if pattern.search(text):
                issues.append(f"forbidden_template_directive={relative}:{label}")

    for relative in ACTIVE_JSON_FILES:
        path = root / relative
        if not path.is_file():
            issues.append(f"missing_active_json={relative}")
            continue
        value = _string_object_mapping(_load_json(path))
        if value is None:
            issues.append(f"active_json_not_object={relative}")
            continue
        if value.get("model_label") != "gpt-5.6-sol":
            issues.append(f"json_model_drift={relative}:{value.get('model_label')}")
        routing_value = value.get("model_routing", value.get("runtime_memory_compute_policy"))
        routing = _string_object_mapping(routing_value)
        if routing is None:
            issues.append(f"json_routing_not_object={relative}")
            continue
        expected_routing = {
            "president_manager_reasoning": "max",
            "manager_return_reasoning": "medium",
            "return_synthesizer_fallback": False,
            "max_default": False,
            "max_forbidden": False,
        }
        for field, expected in expected_routing.items():
            if routing.get(field) != expected:
                issues.append(
                    f"json_routing_drift={relative}:{field}:"
                    f"{routing.get(field)!r}!={expected!r}"
                )

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    protocol = (root / "docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md").read_text(
        encoding="utf-8"
    )
    required_markers = (
        "President Manager: `gpt-5.6-sol / max`",
        "`gpt-5.6-sol / medium`",
        "non-President execution and Manager-facing return",
        "architectural_construction_first",
        "remote CI",
        "FSDP/FSDP2",
        "exactly one final Owner fan-out",
        "one consolidated repair pass",
        "no Owner re-review",
    )
    combined = f"{agents}\n{protocol}"
    for marker in required_markers:
        if marker not in combined:
            issues.append(f"missing_root_protocol_marker={marker}")


def _parse_timestamp(value: object, line_number: int, issues: list[str]) -> datetime | None:
    """解析账本 UTC 时间戳, 无效值按行失败关闭。"""
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
    """按确定性切换时间校验新记录, 并保留切换前历史记录。"""
    count = 0
    current_epoch_seen = False
    synthesizer_routes = 0
    cutover = datetime.fromisoformat(
        str(EXPECTED_POLICY["cutover_timestamp"]).replace("Z", "+00:00")
    )
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        count += 1
        value: object = json.loads(line)
        record = _string_object_mapping(value)
        if record is None:
            issues.append(f"ledger_record_not_object={line_number}")
            continue
        missing = sorted(LEDGER_REQUIRED_FIELDS - record.keys())
        if missing:
            issues.append(f"ledger_missing_fields={line_number}:{','.join(missing)}")
            continue
        created_at = _parse_timestamp(record["creation_timestamp"], line_number, issues)
        if created_at is None:
            continue
        is_historical = created_at < cutover
        if is_historical:
            if record["route_role"] not in {
                "execution",
                "owner_execution",
                "return_synthesizer",
            }:
                issues.append(
                    f"ledger_invalid_historical_route_role={line_number}:{record['route_role']}"
                )
            continue

        current_epoch_seen = True
        policy_name = record.get("policy_name")
        if policy_name != EXPECTED_POLICY["policy_name"]:
            issues.append(f"ledger_policy_epoch_missing={line_number}")
        route_role = record["route_role"]
        expected_execution_reasoning = "medium"
        expected_return_route = record.get("return_route")
        if route_role == "return_synthesizer":
            synthesizer_routes += 1
            issues.append(f"ledger_return_synthesizer_disabled={line_number}")
        if expected_return_route != "same_thread_medium":
            issues.append(f"ledger_invalid_return_route={line_number}:{expected_return_route}")
        expected = {
            "execution_model": "gpt-5.6-sol",
            "execution_reasoning": expected_execution_reasoning,
            "return_model": "gpt-5.6-sol",
            "return_reasoning": "medium",
            "bootstrap_validated_before_create": True,
        }
        for field, expected_value in expected.items():
            if record.get(field) != expected_value:
                issues.append(
                    f"ledger_routing_drift={line_number}:{field}:"
                    f"{record.get(field)!r}!={expected_value!r}"
                )
        if route_role not in {"execution", "owner_execution", "return_synthesizer"}:
            issues.append(f"ledger_invalid_post_cutover_route_role={line_number}:{route_role}")
        if (
            route_role == "return_synthesizer"
            and record.get("return_route") != expected_return_route
        ):
            issues.append(
                f"ledger_routing_drift={line_number}:return_route:"
                f"{record.get('return_route')!r}!={expected_return_route!r}"
            )
        blocker_count = record["blocker_count"]
        if type(blocker_count) is not int or blocker_count < 0:
            issues.append(f"ledger_invalid_blocker_count={line_number}")
        if record["final_return_count"] not in {0, 1}:
            issues.append(f"ledger_invalid_final_return_count={line_number}")
    if count == 0:
        issues.append("ledger_empty")
    if count and not current_epoch_seen:
        issues.append("ledger_current_policy_epoch_missing")
    if synthesizer_routes:
        issues.append(f"ledger_return_synthesizer_count_gt_0={synthesizer_routes}")
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
    policy = _validate_policy(root, issues)
    validation_policy = _validate_validation_policy(root, issues)
    for field in (
        "default_milestone_mode",
        "final_owner_fanout_count",
        "consolidated_repair_pass_count",
        "owner_rereview_after_repair",
    ):
        if policy.get(field) != validation_policy.get(field):
            issues.append(
                f"routing_validation_policy_drift={field}:"
                f"{policy.get(field)!r}!={validation_policy.get(field)!r}"
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
        "validation_policy_name": validation_policy.get("policy_name"),
        "default_milestone_mode": validation_policy.get("default_milestone_mode"),
        "model": policy.get("model"),
        "owner_model": policy.get("owner_model"),
        "owner_reasoning": policy.get("owner_reasoning"),
        "president_manager_reasoning": policy.get("president_manager_reasoning"),
        "execution_reasoning": policy.get("child_execution_reasoning"),
        "manager_return_reasoning": policy.get("manager_return_reasoning"),
        "active_file_count": (
            len(ACTIVE_TEXT_FILES)
            + len(ACTIVE_STATE_FILES)
            + len(ACTIVE_TEMPLATE_YAML_FILES)
            + len(ACTIVE_JSON_FILES)
        ),
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
