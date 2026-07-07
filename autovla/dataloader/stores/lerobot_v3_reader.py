"""本地 LeRobot v3-style 候选 reader。"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from autovla.dataloader.stores.common import require_str


def read_lerobot_v3_local_batches(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """从真实 LeRobot-compatible parquet 布局读取指定 payload。"""
    index_rows = _read_jsonl(root / "sample_index.jsonl")
    selected_rows = [index_rows[index] for index in indices]
    tasks = _read_tasks(root / "meta" / "tasks.jsonl")
    parquet_module = importlib.import_module("pyarrow.parquet")
    parquet = cast(Any, parquet_module)
    payloads: list[dict[str, object]] = []
    table_cache: dict[str, Any] = {}
    for row in selected_rows:
        data_path = require_str(row.get("data_path"), "data_path")
        if data_path not in table_cache:
            table_cache[data_path] = parquet.read_table(root / data_path)
        table = table_cache[data_path]
        row_in_episode = _resolve_row_in_episode(row)
        columns = tuple(str(name) for name in table.column_names)
        raw_row = {column: table[column][row_in_episode].as_py() for column in columns}
        payloads.append(_payload_from_raw_row(raw_row=raw_row, tasks=tasks))
    return payloads


def _payload_from_raw_row(
    *,
    raw_row: Mapping[str, object],
    tasks: Mapping[int, str],
) -> dict[str, object]:
    """从 LeRobot parquet 行重建稳定 payload。"""
    action = _coerce_float_list(raw_row.get("action"), "action")
    state = _coerce_float_list(raw_row.get("observation.state"), "observation.state")
    task_index = _coerce_int(raw_row.get("task_index"), "task_index")
    language_value = raw_row.get("annotation.human.action.task_description") or tasks.get(
        task_index
    )
    language = require_str(language_value, "annotation.human.action.task_description")
    camera_refs = [
        require_str(
            raw_row.get("observation.images.left_wrist_rgb"),
            "observation.images.left_wrist_rgb",
        ),
        require_str(raw_row.get("observation.images.head_rgb"), "observation.images.head_rgb"),
        require_str(
            raw_row.get("observation.images.right_wrist_rgb"),
            "observation.images.right_wrist_rgb",
        ),
    ]
    sample_index = _coerce_int(raw_row.get("index"), "index")
    episode_index = _coerce_int(raw_row.get("episode_index"), "episode_index")
    frame_index = _coerce_int(raw_row.get("frame_index"), "frame_index")
    payload: dict[str, object] = {
        "action": action,
        "action_mask": [True for _ in action],
        "camera_refs": camera_refs,
        "episode_id": f"episode-{episode_index:06d}",
        "frame_index": frame_index,
        "language": language,
        "sample_id": f"sample-{sample_index:09d}",
        "source_mode": "lerobot_v3_local_artifact",
        "state": state,
        "task_index": task_index,
        "timestamp": _coerce_float(raw_row.get("timestamp"), "timestamp"),
        "window_id": f"episode-{episode_index:06d}:sample-{sample_index:09d}:{frame_index}",
    }
    payload["payload_hash"] = _stable_checksum(payload)
    return payload


def _read_jsonl(path: Path) -> list[Mapping[str, object]]:
    """读取 JSONL 索引。"""
    rows: list[Mapping[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(cast(Mapping[str, object], json.loads(line)))
    return rows


def _read_tasks(path: Path) -> dict[int, str]:
    """读取任务文本映射。"""
    tasks: dict[int, str] = {}
    for row in _read_jsonl(path):
        task_index = _coerce_int(row.get("task_index"), "task_index")
        tasks[task_index] = require_str(row.get("task"), "task")
    return tasks


def _resolve_row_in_episode(row: Mapping[str, object]) -> int:
    """解析 sample_index 中记录的 parquet 行号。"""
    return _coerce_int(row.get("row_in_episode"), "row_in_episode")


def _coerce_float_list(value: object, field_name: str) -> list[float]:
    """把 parquet 数值列收窄为 float list。"""
    items = value
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be numeric sequence")
    raw_items = list(cast(Sequence[object], items))
    values: list[float] = []
    for item in raw_items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} must be numeric sequence")
        values.append(float(item))
    return values


def _coerce_int(value: object, field_name: str) -> int:
    """把 parquet 标量收窄为整数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _coerce_float(value: object, field_name: str) -> float:
    """把 parquet 标量收窄为 float。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _stable_checksum(payload: Mapping[str, object]) -> str:
    """复用稳定 JSON 编码计算 payload 哈希。"""
    import hashlib

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()
