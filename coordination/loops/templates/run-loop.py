"""治理用循环规范检查器。

该脚本只检查已解析 JSON 规范是否包含必需字段、激活生命周期和线程级
Owner 运行时结构。它不执行训练、不调用连接器、不修改 PR、不提交
Slurm 作业，也不改变仓库状态。通过本脚本只证明规范形状合格，不证明
真实 Owner 线程已经完成运行时派发。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Iterable


PLACEHOLDER_PATTERN = re.compile(r"<[^<>\n]+>")
FORBIDDEN_MODEL_LABEL = "gpt-" + "5.6"

REQUIRED_FIELDS = {
    "loop_id",
    "task_id",
    "model_label",
    "top_level_prompt",
    "objective",
    "in_scope",
    "out_of_scope",
    "branch",
    "base_head",
    "expected_head",
    "allowed_write_paths",
    "protected_paths",
    "owner_topology",
    "owner_routes",
    "owner_thread_plan",
    "owner_subagent_plan",
    "owner_dispatch_memory_path",
    "tool_memory_policy",
    "budget_policy",
    "timeout_policy",
    "connector_action_policy",
    "compute_policy",
    "validation_evidence_ledger",
    "plan_gate",
    "delivery_gate",
    "scan_gate",
    "pr_visibility_gate",
    "draft_state_policy",
    "completion_gate",
    "rollback_policy",
    "activation_gate",
    "final_allowed_states",
}

REQUIRED_NESTED_FIELDS = (
    ("owner_topology", "task_class"),
    ("owner_topology", "spec_owner"),
    ("owner_topology", "delivery_owner"),
    ("owner_topology", "reviewer_owners"),
    ("owner_topology", "fallback_policy", "blocked_status"),
    ("owner_topology", "fallback_policy", "compatibility_shim_decision"),
    ("activation_gate", "governance_state"),
    ("activation_gate", "installed"),
    ("activation_gate", "activated"),
    ("activation_gate", "normal_loop_mode_allowed"),
    ("activation_gate", "normal_loop_mode_requested"),
    ("activation_gate", "activation_required_task"),
    ("activation_gate", "activation_task"),
    ("activation_gate", "runtime_smoke_required"),
    ("activation_gate", "runtime_smoke_status"),
    ("activation_gate", "runtime_smoke_evidence_path"),
    ("activation_gate", "normal_loop_blocked_status"),
    ("activation_gate", "owner_dispatch_blocked_status"),
    ("activation_gate", "owner_thread_required_status"),
    ("activation_gate", "missing_spec_status"),
    ("activation_gate", "spec_validation_is_runtime_dispatch_proof"),
    ("owner_routes", "primary"),
    ("owner_routes", "reviewers"),
    ("owner_thread_plan", "primary_owner"),
    ("owner_thread_plan", "required_reviewers"),
    ("owner_thread_plan", "owner_concurrency", "max_parallel_owner_threads"),
    ("owner_thread_plan", "owner_threads"),
    ("owner_thread_plan", "owner_packet_paths"),
    ("owner_thread_plan", "owner_report_paths"),
    ("owner_subagent_plan",),
    ("plan_gate", "reviewers"),
    ("plan_gate", "child_reports_cannot_bypass_owner_report"),
    ("plan_gate", "required_owner_reports"),
    ("plan_gate", "pass_condition"),
    ("delivery_gate", "reviewers"),
    ("delivery_gate", "child_reports_cannot_bypass_owner_report"),
    ("delivery_gate", "required_owner_reports"),
    ("delivery_gate", "pass_condition"),
    ("tool_memory_policy", "path"),
    ("tool_memory_policy", "authority"),
    ("budget_policy", "authority"),
    ("budget_policy", "applies_to"),
    ("budget_policy", "exhausted_evidence_path"),
    ("budget_policy", "exhausted_status"),
    ("budget_policy", "continuation_requires_prompt"),
    ("timeout_policy", "authority"),
    ("timeout_policy", "applies_to"),
    ("timeout_policy", "timeout_evidence_path"),
    ("timeout_policy", "timeout_status"),
    ("timeout_policy", "continuation_requires_prompt"),
    ("connector_action_policy", "authorized_actions"),
    ("connector_action_policy", "fallback"),
    ("compute_policy", "compute_authorized"),
    ("compute_policy", "authorized_actions"),
    ("compute_policy", "purpose"),
    ("compute_policy", "command_or_wrapper"),
    ("compute_policy", "execution_location"),
    ("compute_policy", "resource_class"),
    ("compute_policy", "resource_source"),
    ("compute_policy", "evidence_path"),
    ("compute_policy", "safety_stop_condition"),
    ("compute_policy", "expected_output"),
    ("compute_policy", "rollback_or_cleanup_note"),
    ("compute_policy", "authorizing_prompt_or_task"),
    ("compute_policy", "slurm_authorized"),
    ("compute_policy", "escalation_authorized"),
    ("compute_policy", "scheduler_policy_ack"),
    ("compute_policy", "scheduler_rejection_status"),
    ("validation_evidence_ledger", "path"),
    ("scan_gate", "required"),
    ("scan_gate", "blocker_status"),
    ("scan_gate", "evidence_path"),
    ("scan_gate", "blockers_present"),
    ("pr_visibility_gate", "expected_state"),
    ("pr_visibility_gate", "target_pr_number"),
    ("pr_visibility_gate", "target_pr_url"),
    ("pr_visibility_gate", "expected_remote_head"),
    ("pr_visibility_gate", "current_visibility"),
    ("pr_visibility_gate", "mutation_authorized"),
    ("pr_visibility_gate", "authorized_mutations"),
    ("pr_visibility_gate", "visibility_evidence_path"),
    ("draft_state_policy", "preserve_draft"),
    ("draft_state_policy", "ready_transition_authorized"),
    ("draft_state_policy", "ready_transition_authority"),
    ("draft_state_policy", "unauthorized_ready_status"),
    ("connector_action_policy", "target"),
    ("connector_action_policy", "pr_mutation_allowed"),
    ("connector_action_policy", "publication_allowed"),
    ("connector_action_policy", "ready_transition_allowed"),
    ("connector_action_policy", "merge_allowed"),
    ("connector_action_policy", "exact_head_required"),
    ("completion_gate", "missing_spec_status"),
    ("final_allowed_states",),
)

OWNER_REQUIRED_TRUE_FIELDS = (
    "thread_level",
    "can_spawn_child_agents",
    "requires_role_refresh_before_dispatch",
    "owner_report_required",
)

OWNER_REQUIRED_FALSE_FIELDS = ("completed_no_output_is_approval",)

OWNER_CHILD_REQUIRED_FIELDS = (
    "child_id",
    "type",
    "capability",
    "allowed_write_paths",
    "protected_paths",
    "required_output",
    "conclusion_values",
    "starts_after",
    "retires_before",
)

SPECIAL_OWNER_CHILD_TYPES = {
    "toolenvrunner": "tooling",
    "computerunner": "compute_hpc",
    "publisher": "quality",
}

OWNER_TOPOLOGY_TASK_CLASSES = {
    "small_domain_task",
    "governance_task",
    "tooling_task",
    "packaging_task",
    "cross_cutting_refactor",
    "repo_wide_rename",
    "publication_task",
    "compute_task",
}

OWNER_TOPOLOGY_CROSS_CUTTING_TASKS = {
    "cross_cutting_refactor",
    "repo_wide_rename",
}

TOOL_RECOVERY_ACTIONS = {
    "dependency_fill",
    "dependency_install",
    "dependency_install_fill",
    "tool_recovery",
    "toolenv_recovery",
    "wheelhouse_fill",
}

NOOP_ACTIONS = {
    "none",
    "noop",
    "no_op",
    "not_applicable",
    "not_applicable_no_compute",
}

COMPUTE_SENSITIVE_ACTIONS = {
    "compute_execution",
    "gpu_execution",
    "slurm_submission",
    "scheduler_submission",
    "dependency_install",
    "dependency_fill",
    "dependency_install_fill",
    "external_execution",
}

EXECUTION_ACTIONS_REQUIRING_RUNNER = {
    "compute_execution",
    "gpu_execution",
    "slurm_submission",
    "scheduler_submission",
    "external_execution",
}

SLURM_SCHEDULER_ACTIONS = {
    "slurm_submission",
    "scheduler_submission",
}

PR_MUTATION_ACTIONS = {
    "branch_update",
    "draft_publication",
    "merge",
    "pr_body_update",
    "pr_comment",
    "pr_label",
    "pr_merge",
    "pr_mutation",
    "pr_ready",
    "pr_state_update",
    "pr_update",
    "publication",
    "push",
    "ready_for_review",
    "remote_branch_update",
}

PR_PUBLICATION_ACTIONS = {
    "draft_publication",
    "publication",
    "push",
    "remote_branch_update",
}

PR_READY_ACTIONS = {
    "pr_ready",
    "ready_for_review",
}

PR_MERGE_ACTIONS = {
    "merge",
    "pr_merge",
}

RAW_SCHEDULER_COMMANDS = {
    "sbatch",
    "srun",
    "scancel",
    "salloc",
}

MISSING = object()


def _field_path(parent: str, child: str) -> str:
    """拼接用于诊断输出的字段路径。"""
    if not parent:
        return child
    return f"{parent}.{child}"


def load_spec(path: Path) -> dict[str, object]:
    """读取已解析 JSON 规范并返回字典。"""
    with path.open("r", encoding="utf-8") as handle:
        loaded = json.load(handle)
    if not isinstance(loaded, dict):
        raise TypeError("resolved loop spec must be a JSON object")
    return loaded


def unresolved_placeholder_fields(value: object, field_path: str = "") -> list[str]:
    """递归返回仍包含 ``<...>`` 模板占位符的字段路径。"""
    if isinstance(value, str):
        return [field_path] if PLACEHOLDER_PATTERN.search(value) else []
    if isinstance(value, list):
        placeholders: list[str] = []
        for index, item in enumerate(value):
            placeholders.extend(
                unresolved_placeholder_fields(item, f"{field_path}[{index}]")
            )
        return placeholders
    if isinstance(value, dict):
        placeholders = []
        for key, item in sorted(value.items()):
            placeholders.extend(
                unresolved_placeholder_fields(item, _field_path(field_path, str(key)))
            )
        return placeholders
    return []


def recursively_empty_fields(value: object, field_path: str = "") -> list[str]:
    """递归返回任意空字符串、空列表、空字典或空值所在路径。"""
    if value is None:
        return [field_path]
    if isinstance(value, str):
        return [field_path] if value.strip() == "" else []
    if isinstance(value, list):
        if not value:
            return [field_path]
        empty: list[str] = []
        for index, item in enumerate(value):
            empty.extend(recursively_empty_fields(item, f"{field_path}[{index}]"))
        return empty
    if isinstance(value, dict):
        if not value:
            return [field_path]
        empty = []
        for key, item in sorted(value.items()):
            empty.extend(
                recursively_empty_fields(item, _field_path(field_path, str(key)))
            )
        return empty
    return []


def missing_required_fields(spec: dict[str, object]) -> list[str]:
    """返回缺失或为空的必需字段列表。"""
    missing: list[str] = []
    for field in sorted(REQUIRED_FIELDS):
        value = spec.get(field)
        if value is None or value == "" or value == [] or value == {}:
            missing.append(field)
    return missing


def _format_path(path_parts: tuple[str, ...]) -> str:
    """把字段路径元组格式化为点分路径。"""
    return ".".join(path_parts)


def _nested_value(spec: dict[str, object], path_parts: tuple[str, ...]) -> object:
    """读取嵌套字段；中途缺失或类型不匹配时返回缺失哨兵。"""
    current: object = spec
    for part in path_parts:
        if not isinstance(current, dict) or part not in current:
            return MISSING
        current = current[part]
    return current


def _is_empty_required_leaf(value: object) -> bool:
    """判断必需叶子是否为空；列表内的空元素同样视为未解析。"""
    if value is MISSING or value is None:
        return True
    if isinstance(value, str):
        return value.strip() == ""
    if isinstance(value, list):
        return not value or any(_is_empty_required_leaf(item) for item in value)
    if isinstance(value, dict):
        return not value
    return False


def empty_required_nested_fields(spec: dict[str, object]) -> list[str]:
    """返回缺失、空白或仍未解析的必需嵌套叶子路径。"""
    empty: list[str] = []
    for path_parts in REQUIRED_NESTED_FIELDS:
        value = _nested_value(spec, path_parts)
        if _is_empty_required_leaf(value):
            empty.append(_format_path(path_parts))
    return empty


def _dedupe_paths(paths: Iterable[str]) -> list[str]:
    """按首次出现顺序去重诊断路径。"""
    deduped: list[str] = []
    seen: set[str] = set()
    for path in paths:
        if path in seen:
            continue
        deduped.append(path)
        seen.add(path)
    return deduped


def nested_empty_fields(spec: dict[str, object]) -> list[str]:
    """合并必需嵌套缺失检查和全规范递归空值检查。"""
    empty = _dedupe_paths(
        empty_required_nested_fields(spec) + recursively_empty_fields(spec)
    )
    compute_policy = spec.get("compute_policy")
    if isinstance(compute_policy, dict) and compute_policy.get("compute_authorized") is False:
        empty = [
            path
            for path in empty
            if path != "compute_policy.authorized_actions"
        ]
    return empty


def _normalize_owner_name(owner: object) -> str:
    """把 Owner 显示名规整成稳定比较键。"""
    text = str(owner).strip().lower()
    text = text.replace("owner", "")
    text = text.replace("·", " ")
    text = text.replace("/", "_")
    text = re.sub(r"^\d+\s*-\s*", "", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    aliases = {
        "product_spec": "product_spec",
        "product": "product_spec",
        "spec": "product_spec",
        "engineering": "engineering_codebase_migration",
        "codebase_migration": "engineering_codebase_migration",
        "engineering_codebase_migration": "engineering_codebase_migration",
        "architecture": "architecture",
        "training": "training",
        "data": "data",
        "model": "model",
        "deployment": "deployment",
        "quality": "quality",
        "tooling": "tooling",
        "compute": "compute_hpc",
        "hpc": "compute_hpc",
        "compute_hpc": "compute_hpc",
        "80_compute_hpc": "compute_hpc",
        "70_tooling": "tooling",
    }
    return aliases.get(text, text)


def _owner_entry_key(entry: object) -> str:
    """从字符串或对象 Owner 条目读取规整 Owner 键。"""
    if isinstance(entry, dict):
        for field in ("owner", "role", "name"):
            value = entry.get(field)
            if value is not None and str(value).strip():
                return _normalize_owner_name(value)
        return ""
    return _normalize_owner_name(entry)


def _owner_entry_keys(value: object) -> set[str]:
    """把 Owner 字段规整为键集合。"""
    if value is MISSING or value is None:
        return set()
    if isinstance(value, list):
        return {
            key
            for key in (_owner_entry_key(item) for item in value)
            if key
        }
    key = _owner_entry_key(value)
    return {key} if key else set()


def _topology_owner_keys(topology: dict[str, object], field: str) -> set[str]:
    """读取 owner_topology 中的单数/复数 Owner 字段。"""
    value = topology.get(field)
    if value is MISSING or value is None:
        plural = field + "s" if not field.endswith("s") else field
        value = topology.get(plural)
    return _owner_entry_keys(value)


def _topology_has_write_scope(topology: dict[str, object], spec: dict[str, object]) -> bool:
    """判断拓扑是否声明了非空实现写作用域。"""
    direct_scope = topology.get("write_scope")
    if direct_scope not in (MISSING, None, [], {}, ""):
        return True
    direct_scope = spec.get("write_scope")
    if direct_scope not in (MISSING, None, [], {}, ""):
        return True
    owners = topology.get("implementation_owners", topology.get("implementation_owner"))
    if not isinstance(owners, list):
        owners = [owners] if owners not in (MISSING, None) else []
    for owner in owners:
        if isinstance(owner, dict) and owner.get("write_scope") not in (None, [], {}, ""):
            return True
    return False


def _topology_owner_has_child_type(spec: dict[str, object], owner_key: str, child_type: str) -> bool:
    """检查指定 Owner 的 child-agent 序列中是否包含指定类型。"""
    plan = spec.get("owner_subagent_plan")
    if not isinstance(plan, dict):
        return False
    owner_plan = _mapping_entry(plan, owner_key)
    if not isinstance(owner_plan, dict):
        return False
    sequence = owner_plan.get("sequence")
    if not isinstance(sequence, list):
        return False
    wanted = _action_key(child_type)
    for child in sequence:
        if isinstance(child, dict) and _action_key(child.get("type")) == wanted:
            return True
    return False


def _as_owner_list(value: object) -> list[str]:
    """把单值或列表规整为 Owner 名称列表。"""
    if value is MISSING or value is None:
        return []
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]


def _mapping_entry(mapping: object, owner_key: str) -> object:
    """按规整 Owner 名称从映射中取值。"""
    if not isinstance(mapping, dict):
        return MISSING
    for key, value in mapping.items():
        if _normalize_owner_name(key) == owner_key:
            return value
    return MISSING


def routed_owners(spec: dict[str, object]) -> list[str]:
    """返回 owner_thread_plan 和旧 owner_routes 中声明的所有路由 Owner。"""
    owners: list[str] = []
    plan = spec.get("owner_thread_plan")
    if isinstance(plan, dict):
        owners.extend(_as_owner_list(plan.get("primary_owner")))
        owners.extend(_as_owner_list(plan.get("required_reviewers")))
        owners.extend(_as_owner_list(plan.get("consulted_owners")))
    routes = spec.get("owner_routes")
    if isinstance(routes, dict):
        owners.extend(_as_owner_list(routes.get("primary")))
        owners.extend(_as_owner_list(routes.get("reviewers")))
        owners.extend(_as_owner_list(routes.get("consulted")))
    normalized = [_normalize_owner_name(owner) for owner in owners if str(owner).strip()]
    return _dedupe_paths(normalized)


def _bool_field(value: object) -> bool:
    """只接受布尔真值；字符串不会被当作真。"""
    return value is True


def _false_field(value: object) -> bool:
    """只接受布尔假值；缺失或字符串都不是有效假值。"""
    return value is False


def _depth_value(value: object) -> int | None:
    """把深度值转成整数；无法转换则返回空。"""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _contains_short_lived_marker(value: object) -> bool:
    """判断字段值是否仍把角色描述为临时或平面回退角色。"""
    if not isinstance(value, str):
        return False
    normalized = value.lower().replace("_", " ").replace("-", " ")
    return "short lived" in normalized


def _action_key(value: object) -> str:
    """把授权动作规整成比较用键。"""
    text = str(value).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


def _authorized_action_keys(value: object) -> set[str]:
    """读取授权动作字段的动作键集合。"""
    if value is MISSING or value is None:
        return set()
    if isinstance(value, list):
        return {_action_key(item) for item in value if str(item).strip()}
    return {_action_key(value)} if str(value).strip() else set()


def _has_remote_or_pr_target(connector: dict[str, object], visibility: dict[str, object]) -> bool:
    """判断规范是否声明了需要精确 HEAD 保护的 PR 或远端目标。"""
    target_values = (
        connector.get("target"),
        visibility.get("target_pr_number"),
        visibility.get("target_pr_url"),
    )
    for value in target_values:
        key = _action_key(value)
        if key and key not in NOOP_ACTIONS:
            return True
    return False


def _is_project_slurm_wrapper(value: object) -> bool:
    """判断 Slurm/Scheduler 命令是否指向项目包装器而非原生命令。"""
    if not isinstance(value, str):
        return False
    normalized = value.strip().lower()
    first_token = normalized.split(maxsplit=1)[0] if normalized else ""
    if first_token in RAW_SCHEDULER_COMMANDS:
        return False
    return "scripts/slurm/" in normalized or "wrapper" in normalized


def _looks_like_child_report_path(value: object) -> bool:
    """判断报告路径是否指向子代理报告目录而不是 Owner 报告目录。"""
    if not isinstance(value, str):
        return False
    normalized = value.lower().replace("\\", "/")
    child_markers = (
        "/subagent-reports/",
        "/child-agent-reports/",
        "/child-reports/",
        "subagent-report",
        "child-agent-report",
    )
    return any(marker in normalized for marker in child_markers)


def _persistent_routed_owner_keys(spec: dict[str, object]) -> set[str]:
    """返回已经路由且声明为持久 Owner 的角色键。"""
    plan = spec.get("owner_thread_plan")
    if not isinstance(plan, dict):
        return set()
    owner_threads = plan.get("owner_threads")
    persistent: set[str] = set()
    for owner in routed_owners(spec):
        entry = _mapping_entry(owner_threads, owner)
        if isinstance(entry, dict) and entry.get("role_type") == "persistent_owner":
            persistent.add(owner)
    return persistent


def owner_thread_plan_reasons(spec: dict[str, object]) -> list[str]:
    """校验线程级 Owner 计划、包路径和报告路径。"""
    reasons: list[str] = []
    plan = spec.get("owner_thread_plan")
    if not isinstance(plan, dict):
        return ["owner_thread_plan_not_object"]

    owners = routed_owners(spec)
    if not owners:
        reasons.append("no_routed_owners")
        return reasons

    owner_threads = plan.get("owner_threads")
    packet_paths = plan.get("owner_packet_paths")
    report_paths = plan.get("owner_report_paths")

    for owner in owners:
        entry = _mapping_entry(owner_threads, owner)
        if not isinstance(entry, dict):
            reasons.append(f"owner_thread_missing={owner}")
            continue

        if entry.get("role_type") != "persistent_owner":
            reasons.append(f"owner_thread_invalid_role_type={owner}")
        if any(_contains_short_lived_marker(entry.get(field)) for field in entry):
            reasons.append(f"owner_thread_short_lived_only={owner}")
        for field in OWNER_REQUIRED_TRUE_FIELDS:
            if not _bool_field(entry.get(field)):
                reasons.append(f"owner_thread_false_or_missing={owner}.{field}")
        for field in OWNER_REQUIRED_FALSE_FIELDS:
            if not _false_field(entry.get(field)):
                reasons.append(f"owner_thread_not_false={owner}.{field}")

        depth = _depth_value(entry.get("child_agent_depth_limit"))
        if depth is None:
            reasons.append(f"owner_thread_missing_depth={owner}")
        elif depth > 1:
            reasons.append(f"owner_thread_depth_gt_1={owner}")

        if owner in {"tooling", "compute_hpc"}:
            lifecycle = entry.get("lifecycle")
            if lifecycle != "create_or_refresh_when_routed":
                reasons.append(f"owner_thread_invalid_lifecycle={owner}")

        packet_path = _mapping_entry(packet_paths, owner)
        if _is_empty_required_leaf(packet_path):
            reasons.append(f"owner_packet_path_missing={owner}")
        report_path = _mapping_entry(report_paths, owner)
        if _is_empty_required_leaf(report_path):
            reasons.append(f"owner_report_path_missing={owner}")

    return reasons


def owner_subagent_plan_reasons(spec: dict[str, object]) -> list[str]:
    """校验每个路由 Owner 的子代理计划和退休目标。"""
    reasons: list[str] = []
    plan = spec.get("owner_subagent_plan")
    if not isinstance(plan, dict):
        return ["owner_subagent_plan_not_object"]

    for owner in routed_owners(spec):
        entry = _mapping_entry(plan, owner)
        if not isinstance(entry, dict):
            reasons.append(f"owner_subagent_plan_missing={owner}")
            continue

        for field in ("max_child_agents", "peak_concurrency", "child_agent_depth_limit", "sequence"):
            if _is_empty_required_leaf(entry.get(field)):
                reasons.append(f"owner_subagent_field_missing={owner}.{field}")

        depth = _depth_value(entry.get("child_agent_depth_limit"))
        if depth is None:
            reasons.append(f"owner_subagent_depth_missing={owner}")
        elif depth > 1:
            reasons.append(f"owner_subagent_depth_gt_1={owner}")

        sequence = entry.get("sequence")
        if not isinstance(sequence, list):
            reasons.append(f"owner_subagent_sequence_not_list={owner}")
            continue

        for index, child in enumerate(sequence):
            child_path = f"{owner}.sequence[{index}]"
            if not isinstance(child, dict):
                reasons.append(f"child_not_object={child_path}")
                continue
            for field in OWNER_CHILD_REQUIRED_FIELDS:
                if _is_empty_required_leaf(child.get(field)):
                    reasons.append(f"child_field_missing={child_path}.{field}")
            child_type = str(child.get("type", "")).strip().lower()
            required_owner = SPECIAL_OWNER_CHILD_TYPES.get(child_type)
            if required_owner is not None and required_owner != owner:
                reasons.append(f"child_type_wrong_owner={child_path}.{child_type}")
            child_depth = _depth_value(child.get("child_agent_depth", 1))
            if child_depth is not None and child_depth > 1:
                reasons.append(f"child_depth_gt_1={child_path}")

    return reasons


def gate_reasons(spec: dict[str, object]) -> list[str]:
    """校验 plan_gate 和 delivery_gate 使用 Owner 报告而不是子报告。"""
    reasons: list[str] = []
    persistent_owners = _persistent_routed_owner_keys(spec)
    plan = spec.get("owner_thread_plan")
    owner_report_paths = plan.get("owner_report_paths") if isinstance(plan, dict) else MISSING
    for gate_name in ("plan_gate", "delivery_gate"):
        gate = spec.get(gate_name)
        if not isinstance(gate, dict):
            reasons.append(f"{gate_name}_not_object")
            continue

        if not _bool_field(gate.get("child_reports_cannot_bypass_owner_report")):
            reasons.append(f"{gate_name}_child_report_bypass_not_explicitly_forbidden")

        reviewers = gate.get("reviewers")
        reviewer_keys = {
            _normalize_owner_name(owner)
            for owner in _as_owner_list(reviewers)
            if str(owner).strip()
        }
        required_reports = gate.get("required_owner_reports")
        if not isinstance(required_reports, dict):
            reasons.append(f"{gate_name}_required_owner_reports_not_mapping")
            continue

        report_owner_keys = {
            _normalize_owner_name(owner)
            for owner in required_reports
            if str(owner).strip()
        }
        for owner in sorted(reviewer_keys | report_owner_keys):
            if owner not in persistent_owners:
                reasons.append(f"{gate_name}_owner_not_routed_persistent={owner}")

        for owner in sorted(reviewer_keys):
            if owner not in report_owner_keys:
                reasons.append(f"{gate_name}_reviewer_missing_required_owner_report={owner}")

        for owner, report_path in sorted(required_reports.items()):
            owner_key = _normalize_owner_name(owner)
            expected_path = _mapping_entry(owner_report_paths, owner_key)
            if _looks_like_child_report_path(report_path):
                reasons.append(f"{gate_name}_required_owner_report_is_child_path={owner_key}")
            if expected_path is MISSING or report_path != expected_path:
                reasons.append(f"{gate_name}_required_owner_report_path_mismatch={owner_key}")
    return reasons


def compute_policy_reasons(spec: dict[str, object]) -> list[str]:
    """校验 compute_policy 的授权、Owner 路由和 ComputeRunner 约束。"""
    reasons: list[str] = []
    policy = spec.get("compute_policy")
    if not isinstance(policy, dict):
        return ["compute_policy_not_object"]

    compute_authorized = policy.get("compute_authorized")
    if compute_authorized is not True and compute_authorized is not False:
        reasons.append("compute_authorized_not_boolean")

    actions = _authorized_action_keys(policy.get("authorized_actions"))
    active_actions = {action for action in actions if action not in NOOP_ACTIONS}
    sensitive_actions = active_actions & COMPUTE_SENSITIVE_ACTIONS
    execution_actions = active_actions & EXECUTION_ACTIONS_REQUIRING_RUNNER
    slurm_actions = active_actions & SLURM_SCHEDULER_ACTIONS

    if compute_authorized is False and sensitive_actions:
        reasons.append(
            "compute_actions_without_compute_authorization="
            + ",".join(sorted(sensitive_actions))
        )

    persistent_owners = _persistent_routed_owner_keys(spec)
    if execution_actions and "compute_hpc" not in persistent_owners:
        reasons.append("compute_hpc_owner_not_routed_persistent")

    if slurm_actions:
        if policy.get("slurm_authorized") is not True:
            reasons.append("slurm_actions_without_slurm_authorization")
        if policy.get("scheduler_policy_ack") is not True:
            reasons.append("scheduler_actions_without_scheduler_policy_ack")
        if not _is_project_slurm_wrapper(policy.get("command_or_wrapper")):
            reasons.append("slurm_actions_without_project_wrapper")

    if execution_actions and compute_authorized is True:
        reasons.extend(compute_runner_reasons(spec))

    return reasons


def activation_gate_reasons(spec: dict[str, object]) -> list[str]:
    """校验治理安装、激活和运行时冒烟之间的闸门关系。"""
    gate = spec.get("activation_gate")
    if not isinstance(gate, dict):
        return ["activation_gate_not_object"]

    reasons: list[str] = []
    allowed_states = {
        "GOVERNANCE_DRAFT",
        "GOVERNANCE_INSTALLED",
        "GOVERNANCE_ACTIVATED",
    }
    governance_state = gate.get("governance_state")
    installed = gate.get("installed")
    activated = gate.get("activated")
    normal_allowed = gate.get("normal_loop_mode_allowed")
    normal_requested = gate.get("normal_loop_mode_requested")
    activation_task = gate.get("activation_task")
    smoke_required = gate.get("runtime_smoke_required")
    smoke_status = gate.get("runtime_smoke_status")
    smoke_passed = smoke_status == "LOOP_V2_OWNER_RUNTIME_SMOKE_PASS"

    if governance_state not in allowed_states:
        reasons.append(f"invalid_governance_state={governance_state}")
    for field, value in (
        ("installed", installed),
        ("activated", activated),
        ("normal_loop_mode_allowed", normal_allowed),
        ("normal_loop_mode_requested", normal_requested),
        ("activation_task", activation_task),
        ("runtime_smoke_required", smoke_required),
    ):
        if value is not True and value is not False:
            reasons.append(f"{field}_not_boolean")

    if gate.get("normal_loop_blocked_status") != "LOOP_NOT_ACTIVATED":
        reasons.append("normal_loop_blocked_status_not_loop_not_activated")
    if gate.get("owner_dispatch_blocked_status") != "BLOCKED_OWNER_DISPATCH":
        reasons.append("owner_dispatch_blocked_status_not_blocked_owner_dispatch")
    if gate.get("owner_thread_required_status") != "OWNER_THREAD_REQUIRED":
        reasons.append("owner_thread_required_status_not_owner_thread_required")
    if gate.get("missing_spec_status") != "BLOCKED_LOOP_SPEC":
        reasons.append("missing_spec_status_not_blocked_loop_spec")
    if gate.get("spec_validation_is_runtime_dispatch_proof") is not False:
        reasons.append("spec_validation_claims_runtime_dispatch_proof")

    required_task = str(gate.get("activation_required_task", "")).strip()
    if activation_task is True and spec.get("task_id") != required_task:
        reasons.append("activation_task_id_mismatch")

    if activated is True and installed is not True:
        reasons.append("LOOP_NOT_ACTIVATED:activated_without_installed")
    if activated is True and governance_state != "GOVERNANCE_ACTIVATED":
        reasons.append("activated_true_without_activated_state")
    if normal_allowed is True and (installed is not True or activated is not True):
        reasons.append(
            "LOOP_NOT_ACTIVATED:normal_loop_allowed_without_installed_activation"
        )
    if activated is True and not smoke_passed:
        reasons.append("activation_without_runtime_smoke_pass")
    if normal_requested is True and (activated is not True or normal_allowed is not True):
        reasons.append("LOOP_NOT_ACTIVATED:normal_loop_requested_before_activation")
    if normal_requested is True and not smoke_passed:
        reasons.append("LOOP_NOT_ACTIVATED:normal_loop_requested_without_smoke_pass")
    if activation_task is not True and normal_requested is not True:
        reasons.append("neither_activation_task_nor_normal_loop_requested")
    if smoke_required is not True:
        reasons.append("runtime_smoke_not_required")

    return reasons


def pr_policy_reasons(spec: dict[str, object]) -> list[str]:
    """校验 PR 可见性、草稿状态、精确 HEAD 和扫描闸门。"""
    reasons: list[str] = []
    connector = spec.get("connector_action_policy")
    visibility = spec.get("pr_visibility_gate")
    draft_policy = spec.get("draft_state_policy")
    scan_gate = spec.get("scan_gate")
    if not isinstance(connector, dict):
        return ["connector_action_policy_not_object"]
    if not isinstance(visibility, dict):
        return ["pr_visibility_gate_not_object"]
    if not isinstance(draft_policy, dict):
        return ["draft_state_policy_not_object"]
    if not isinstance(scan_gate, dict):
        return ["scan_gate_not_object"]

    actions = _authorized_action_keys(connector.get("authorized_actions"))
    active_actions = {action for action in actions if action not in NOOP_ACTIONS}
    mutation_actions = active_actions & PR_MUTATION_ACTIONS
    publication_actions = active_actions & PR_PUBLICATION_ACTIONS
    ready_actions = active_actions & PR_READY_ACTIONS
    merge_actions = active_actions & PR_MERGE_ACTIONS
    mutation_or_publication = bool(mutation_actions or publication_actions)

    if visibility.get("current_visibility") != visibility.get("expected_state"):
        reasons.append("pr_visibility_mismatch")

    expected_remote_head = visibility.get("expected_remote_head")
    exact_head_required_for_target = (
        connector.get("exact_head_required") is True
        and _has_remote_or_pr_target(connector, visibility)
    )
    if exact_head_required_for_target and expected_remote_head != spec.get("expected_head"):
        reasons.append("pr_expected_remote_head_mismatch")
    if mutation_or_publication and connector.get("exact_head_required") is not True:
        reasons.append("pr_mutation_without_exact_head_required")

    if mutation_actions and connector.get("pr_mutation_allowed") is not True:
        reasons.append("pr_mutation_without_authorization")
    if publication_actions and connector.get("publication_allowed") is not True:
        reasons.append("publication_without_authorization")
    if ready_actions:
        if connector.get("ready_transition_allowed") is not True:
            reasons.append("ready_transition_without_connector_authorization")
        if draft_policy.get("ready_transition_authorized") is not True:
            reasons.append("draft_to_ready_without_authorization")
    if merge_actions and connector.get("merge_allowed") is not True:
        reasons.append("merge_without_authorization")

    target_pr = visibility.get("target_pr_number")
    if target_pr == 6 and mutation_actions and visibility.get("pr6_mutation_authorized") is not True:
        reasons.append("pr6_mutation_without_authorization")

    if mutation_or_publication:
        if scan_gate.get("required") is not True:
            reasons.append("scan_gate_not_required_for_pr_mutation")
        if scan_gate.get("blockers_present") is not False:
            reasons.append("scan_blocker_present_for_pr_mutation")
        if _is_empty_required_leaf(scan_gate.get("evidence_path")):
            reasons.append("scan_evidence_path_missing")

    return reasons


def owner_topology_reasons(spec: dict[str, object]) -> list[str]:
    """校验 Owner 拓扑的职责分离和 fail-closed 规则。"""
    reasons: list[str] = []
    topology = spec.get("owner_topology")
    if not isinstance(topology, dict):
        return ["owner_topology_not_object"]

    if topology.get("fallback_policy", {}).get("blocked_status") != "BLOCKED_OWNER_TOPOLOGY":
        reasons.append("fallback_status_not_blocked_owner_topology")
    if (
        topology.get("fallback_policy", {}).get("compatibility_shim_decision")
        != "READY_FOR_USER_DECISION_COMPATIBILITY_SHIM"
    ):
        reasons.append("compatibility_shim_decision_not_user_decision")

    task_class = _action_key(topology.get("task_class"))
    if task_class not in OWNER_TOPOLOGY_TASK_CLASSES:
        reasons.append(f"invalid_task_class={task_class}")

    implementation_owners = _topology_owner_keys(topology, "implementation_owner")
    reviewer_owners = _topology_owner_keys(topology, "reviewer_owner")
    publisher_owners = _topology_owner_keys(topology, "publisher_owner")
    tooling_owners = _topology_owner_keys(topology, "tooling_owner")
    compute_owners = _topology_owner_keys(topology, "compute_owner")

    plan = spec.get("owner_thread_plan")
    skipped_owners: set[str] = set()
    thread_reviewers: set[str] = set()
    if isinstance(plan, dict):
        skipped = plan.get("skipped_owners")
        if isinstance(skipped, dict):
            skipped_owners = {
                _normalize_owner_name(owner)
                for owner in skipped
                if str(owner).strip()
            }
        thread_reviewers = {
            _normalize_owner_name(owner)
            for owner in _as_owner_list(plan.get("required_reviewers"))
            if str(owner).strip()
        }
    routes = spec.get("owner_routes")
    route_reviewers: set[str] = set()
    if isinstance(routes, dict):
        route_reviewers = {
            _normalize_owner_name(owner)
            for owner in _as_owner_list(routes.get("reviewers"))
            if str(owner).strip()
        }
    reviewer_overlap = skipped_owners & (reviewer_owners | thread_reviewers | route_reviewers)
    if reviewer_overlap:
        reasons.append("reviewer_owner_marked_skipped=" + ",".join(sorted(reviewer_overlap)))

    if task_class in OWNER_TOPOLOGY_CROSS_CUTTING_TASKS:
        if not implementation_owners:
            reasons.append("cross_cutting_without_implementation_owner")
        if not reviewer_owners:
            reasons.append("cross_cutting_without_reviewer_owner")
        if not topology.get("spec_owner"):
            reasons.append("cross_cutting_without_spec_owner")
        if not topology.get("delivery_owner"):
            reasons.append("cross_cutting_without_delivery_owner")

    if _topology_has_write_scope(topology, spec) and not implementation_owners:
        reasons.append("write_scope_without_implementation_owner")

    connector = spec.get("connector_action_policy")
    active_actions: set[str] = set()
    if isinstance(connector, dict):
        active_actions = {
            action
            for action in _authorized_action_keys(connector.get("authorized_actions"))
            if action not in NOOP_ACTIONS
        }
    pr_actions = active_actions & (PR_MUTATION_ACTIONS | PR_PUBLICATION_ACTIONS | PR_READY_ACTIONS | PR_MERGE_ACTIONS)
    if pr_actions and not publisher_owners:
        reasons.append("pr_publication_without_publisher_owner")

    if active_actions & TOOL_RECOVERY_ACTIONS and not tooling_owners:
        reasons.append("tool_recovery_without_tooling_owner")

    policy = spec.get("compute_policy")
    compute_actions: set[str] = set()
    compute_authorized = False
    if isinstance(policy, dict):
        compute_authorized = policy.get("compute_authorized") is True or policy.get("slurm_authorized") is True
        compute_actions = {
            action
            for action in _authorized_action_keys(policy.get("authorized_actions"))
            if action not in NOOP_ACTIONS
        }
    if (compute_authorized or compute_actions & COMPUTE_SENSITIVE_ACTIONS) and not compute_owners:
        reasons.append("compute_authorized_without_compute_owner")

    if task_class in OWNER_TOPOLOGY_CROSS_CUTTING_TASKS:
        if (
            len(implementation_owners) == 1
            and len(reviewer_owners) == 1
            and implementation_owners == reviewer_owners
        ):
            reasons.append("sole_implementation_owner_also_sole_reviewer")

    for owner in sorted(implementation_owners):
        if not _topology_owner_has_child_type(spec, owner, "Implementer"):
            reasons.append(f"implementation_owner_without_implementer_child={owner}")

    for owner in sorted(publisher_owners):
        if pr_actions and not _topology_owner_has_child_type(spec, owner, "Publisher"):
            reasons.append(f"publisher_owner_without_publisher_child={owner}")

    shim = topology.get("compatibility_shim")
    if isinstance(shim, dict) and shim.get("authorized") is True:
        if shim.get("decision") != "READY_FOR_USER_DECISION_COMPATIBILITY_SHIM":
            reasons.append("compatibility_shim_authorized_implicitly")
    if topology.get("compatibility_shim_authorized") is True:
        reasons.append("compatibility_shim_authorized_implicitly")

    return reasons


def _string_values(value: object) -> list[str]:
    """递归收集字符串值，用于模型标签漂移检查。"""
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        strings: list[str] = []
        for item in value:
            strings.extend(_string_values(item))
        return strings
    if isinstance(value, dict):
        strings = []
        for item in value.values():
            strings.extend(_string_values(item))
        return strings
    return []


def model_label_reasons(spec: dict[str, object]) -> list[str]:
    """校验 prompt-loop 激活面没有漂移到未授权模型标签。"""
    reasons: list[str] = []
    if spec.get("model_label") != "gpt-5.5":
        reasons.append(f"model_label_drift={spec.get('model_label')}")
    if any(FORBIDDEN_MODEL_LABEL in value for value in _string_values(spec)):
        reasons.append("active_gpt_5_6_label_present")
    return reasons


def _contains_numeric_budget(value: object) -> bool:
    """检查预算或超时策略里是否包含数字示例。"""
    if isinstance(value, bool):
        return False
    if isinstance(value, (int, float)):
        return True
    if isinstance(value, list):
        return any(_contains_numeric_budget(item) for item in value)
    if isinstance(value, dict):
        return any(_contains_numeric_budget(item) for item in value.values())
    return False


def budget_timeout_reasons(spec: dict[str, object]) -> list[str]:
    """数字预算或超时值只能作为明示示例出现，不能成为默认值。"""
    reasons: list[str] = []
    for field in ("budget_policy", "timeout_policy"):
        policy = spec.get(field)
        if not isinstance(policy, dict):
            reasons.append(f"{field}_not_object")
            continue
        has_numeric = _contains_numeric_budget(policy)
        marked_example = (
            policy.get("numeric_values_are_example_only_not_defaults") is True
            or policy.get("example_values_are_not_defaults") is True
        )
        if has_numeric and not marked_example:
            reasons.append(f"{field}_numeric_values_not_marked_example_only")
    return reasons


def compute_runner_reasons(spec: dict[str, object]) -> list[str]:
    """校验 Compute/HPC Owner 下存在深度不超过一的 ComputeRunner。"""
    reasons: list[str] = []
    subagent_plan = spec.get("owner_subagent_plan")
    if not isinstance(subagent_plan, dict):
        return ["compute_runner_owner_subagent_plan_missing"]
    compute_plan = _mapping_entry(subagent_plan, "compute_hpc")
    if not isinstance(compute_plan, dict):
        return ["compute_runner_plan_missing"]

    sequence = compute_plan.get("sequence")
    if not isinstance(sequence, list):
        return ["compute_runner_sequence_missing"]

    owner_thread_plan = spec.get("owner_thread_plan")
    owner_report_paths = (
        owner_thread_plan.get("owner_report_paths")
        if isinstance(owner_thread_plan, dict)
        else MISSING
    )
    compute_owner_report = _mapping_entry(owner_report_paths, "compute_hpc")
    found_runner = False

    for index, child in enumerate(sequence):
        if not isinstance(child, dict):
            continue
        child_type = _action_key(child.get("type"))
        if child_type != "computerunner":
            continue
        found_runner = True
        child_path = f"compute_hpc.sequence[{index}]"
        child_depth = _depth_value(child.get("child_agent_depth", 1))
        if child_depth is None:
            reasons.append(f"compute_runner_depth_missing={child_path}")
        elif child_depth > 1:
            reasons.append(f"compute_runner_depth_gt_1={child_path}")
        if child.get("retires_before") != compute_owner_report:
            reasons.append(f"compute_runner_retirement_path_mismatch={child_path}")

    if not found_runner:
        reasons.append("compute_runner_missing")
    return reasons


def excessive_depth_fields(value: object, field_path: str = "") -> list[str]:
    """递归查找所有大于一的子代理深度字段。"""
    if isinstance(value, dict):
        paths: list[str] = []
        for key, item in sorted(value.items()):
            path = _field_path(field_path, str(key))
            if str(key) in {"child_agent_depth", "child_agent_depth_limit"}:
                depth = _depth_value(item)
                if depth is not None and depth > 1:
                    paths.append(path)
            paths.extend(excessive_depth_fields(item, path))
        return paths
    if isinstance(value, list):
        paths = []
        for index, item in enumerate(value):
            paths.extend(excessive_depth_fields(item, f"{field_path}[{index}]"))
        return paths
    return []


def blocked_reasons(spec: dict[str, object]) -> list[str]:
    """返回阻止循环执行的 fail-closed 原因。"""
    reasons: list[str] = []
    missing = missing_required_fields(spec)
    if missing:
        reasons.append("missing=" + ",".join(missing))
    nested_empty = nested_empty_fields(spec)
    if nested_empty:
        reasons.append("nested_empty=" + ",".join(nested_empty))
    if spec.get("example_only") is True:
        reasons.append("example_only=true")
    placeholder_fields = unresolved_placeholder_fields(spec)
    if placeholder_fields:
        reasons.append("placeholders=" + ",".join(placeholder_fields))

    owner_thread = owner_thread_plan_reasons(spec)
    if owner_thread:
        reasons.append("owner_thread_plan=" + ",".join(owner_thread))
    owner_subagents = owner_subagent_plan_reasons(spec)
    if owner_subagents:
        reasons.append("owner_subagent_plan=" + ",".join(owner_subagents))
    gates = gate_reasons(spec)
    if gates:
        reasons.append("gates=" + ",".join(gates))
    activation = activation_gate_reasons(spec)
    if activation:
        reasons.append("activation_gate=" + ",".join(activation))
    pr_policy = pr_policy_reasons(spec)
    if pr_policy:
        reasons.append("pr_policy=" + ",".join(pr_policy))
    topology = owner_topology_reasons(spec)
    if topology:
        reasons.append("owner_topology=" + ",".join(topology))
    model_label = model_label_reasons(spec)
    if model_label:
        reasons.append("model_label=" + ",".join(model_label))
    budget_timeout = budget_timeout_reasons(spec)
    if budget_timeout:
        reasons.append("budget_timeout=" + ",".join(budget_timeout))
    compute = compute_policy_reasons(spec)
    if compute:
        reasons.append("compute_policy=" + ",".join(compute))
    depth = excessive_depth_fields(spec)
    if depth:
        reasons.append("child_agent_depth_gt_1=" + ",".join(depth))
    return reasons


def main(argv: list[str]) -> int:
    """执行本地只读校验。"""
    if len(argv) != 2:
        print("usage: run-loop.py <resolved-loop.json>", file=sys.stderr)
        return 2
    spec = load_spec(Path(argv[1]))
    reasons = blocked_reasons(spec)
    if reasons:
        status = "BLOCKED_LOOP_SPEC"
        if any("LOOP_NOT_ACTIVATED" in reason for reason in reasons):
            status = "LOOP_NOT_ACTIVATED"
        elif any(reason.startswith("owner_topology=") for reason in reasons):
            status = "BLOCKED_OWNER_TOPOLOGY"
        print(status + " " + " ".join(reasons))
        return 1
    print("PASS loop spec required fields present; runtime dispatch not proven")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
