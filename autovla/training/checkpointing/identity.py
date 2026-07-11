"""生产 checkpoint 的版本、Git 和稳定指纹身份。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import fields, is_dataclass
from enum import Enum
from pathlib import Path
from typing import cast

_OPERATIONAL_LOCATION_PATHS = (
    ("training", "checkpoint", "directory"),
    ("training", "checkpoint", "resume_from"),
    ("training", "logging", "jsonl_path"),
)


def _json_value(value: object) -> object:
    """把受控配置值递归转换为稳定 JSON 值。"""
    if is_dataclass(value) and not isinstance(value, type):
        return {
            field.name: _json_value(getattr(value, field.name))
            for field in fields(value)
            if not field.name.startswith("_")
        }
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        return {
            str(key): _json_value(item)
            for key, item in sorted(mapping.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, Enum):
        return _json_value(value.value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        sequence = cast(Sequence[object], value)
        return [_json_value(item) for item in sequence]
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"unsupported fingerprint value: {type(value).__name__}")


def stable_fingerprint(value: object) -> str:
    """返回环境无关、字段排序稳定的 SHA256。"""
    encoded = json.dumps(
        _json_value(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def checkpoint_compatibility_projection(config: Mapping[str, object]) -> dict[str, object]:
    """投影严格训练语义,仅排除 checkpoint、resume 和日志输出位置。"""
    normalized = _json_value(config)
    if not isinstance(normalized, dict):
        raise TypeError("checkpoint config must normalize to a mapping")
    projection = cast(dict[str, object], normalized)
    for path in _OPERATIONAL_LOCATION_PATHS:
        _remove_location(projection, path)
    return projection


def _remove_location(config: dict[str, object], path: tuple[str, ...]) -> None:
    """从已规范化配置中移除一个精确嵌套位置。"""
    parent = config
    for key in path[:-1]:
        child = parent.get(key)
        if not isinstance(child, dict):
            return
        parent = cast(dict[str, object], child)
    parent.pop(path[-1], None)


def checkpoint_compatibility_fingerprint(config: Mapping[str, object]) -> str:
    """返回规范语义投影的唯一恢复兼容指纹。"""
    return stable_fingerprint(checkpoint_compatibility_projection(config))


def resolve_git_commit(project_root: Path) -> str:
    """从显式环境或本地 Git checkout 解析精确提交,禁止模糊身份。"""
    configured = os.environ.get("AUTOVLA_GIT_COMMIT")
    if configured is not None:
        candidate = configured.strip().lower()
    else:
        result = subprocess.run(
            ("git", "-C", str(project_root), "rev-parse", "HEAD"),
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            raise RuntimeError(
                "checkpoint identity requires AUTOVLA_GIT_COMMIT or a readable local Git checkout"
            )
        candidate = result.stdout.strip().lower()
    if len(candidate) != 40 or any(character not in "0123456789abcdef" for character in candidate):
        raise ValueError("checkpoint Git identity must be a full 40-character hexadecimal commit")
    return candidate


__all__ = [
    "checkpoint_compatibility_fingerprint",
    "checkpoint_compatibility_projection",
    "resolve_git_commit",
    "stable_fingerprint",
]
