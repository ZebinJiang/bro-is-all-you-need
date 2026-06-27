"""治理用循环规范检查器。

该脚本只检查已解析 JSON 规范是否包含必需字段。它不执行训练、
不调用连接器、不修改 PR、不提交 Slurm 作业，也不改变仓库状态。
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path


PLACEHOLDER_PATTERN = re.compile(r"<[^<>\n]+>")

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
    "owner_routes",
    "owner_dispatch_memory_path",
    "tool_memory_policy",
    "budget_policy",
    "timeout_policy",
    "connector_action_policy",
    "compute_policy",
    "validation_evidence_ledger",
    "scan_gate",
    "pr_visibility_gate",
    "draft_state_policy",
    "completion_gate",
    "rollback_policy",
}

REQUIRED_NESTED_FIELDS = (
    ("owner_routes", "primary"),
    ("owner_routes", "reviewers"),
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
    ("pr_visibility_gate", "expected_state"),
    ("completion_gate", "missing_spec_status"),
)

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


def _dedupe_paths(paths: list[str]) -> list[str]:
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
    return _dedupe_paths(
        empty_required_nested_fields(spec) + recursively_empty_fields(spec)
    )


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
    return reasons


def main(argv: list[str]) -> int:
    """执行本地只读校验。"""
    if len(argv) != 2:
        print("usage: run-loop.py <resolved-loop.json>", file=sys.stderr)
        return 2
    spec = load_spec(Path(argv[1]))
    reasons = blocked_reasons(spec)
    if reasons:
        print("BLOCKED_LOOP_SPEC " + " ".join(reasons))
        return 1
    print("PASS loop spec required fields present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
