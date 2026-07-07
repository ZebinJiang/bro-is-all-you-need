"""LeRobot / Isaac 兼容 surface 生成 helper。"""

from __future__ import annotations

import importlib
import json
import os
import shutil
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

from autovla.dataloader.stores.common import (
    CAMERA_VIEWS,
    SourceSample,
    require_int,
    write_json,
    write_jsonl,
)

BLACK_RUBBER_MODALITY_LAYOUT: dict[str, object] = {
    "state": {
        "left_arm_joint_position": {"original_key": "observation.state", "start": 0, "end": 8},
        "right_arm_joint_position": {"original_key": "observation.state", "start": 8, "end": 16},
        "left_effector_position": {"original_key": "observation.state", "start": 22, "end": 25},
        "left_effector_orientation": {
            "original_key": "observation.state",
            "start": 25,
            "end": 29,
        },
        "right_effector_position": {"original_key": "observation.state", "start": 29, "end": 32},
        "right_effector_orientation": {
            "original_key": "observation.state",
            "start": 32,
            "end": 36,
        },
        "left_hand_joint_position": {"original_key": "observation.state", "start": 36, "end": 42},
        "right_hand_joint_position": {
            "original_key": "observation.state",
            "start": 42,
            "end": 48,
        },
        "waist_joint_position": {"original_key": "observation.state", "start": 18, "end": 22},
    },
    "action": {
        "right_arm_joint_position": {"original_key": "action", "start": 8, "end": 16},
        "right_hand_joint_position": {"original_key": "action", "start": 92, "end": 98},
        "waist_joint_position": {"original_key": "action", "start": 18, "end": 22},
    },
    "video": {
        "head_rgb": {"original_key": "observation.images.head_rgb"},
        "left_wrist_rgb": {"original_key": "observation.images.left_wrist_rgb"},
        "right_wrist_rgb": {"original_key": "observation.images.right_wrist_rgb"},
    },
    "annotation": {
        "human.action.task_description": {"original_key": "task_index"},
    },
}


def build_raw_isaac_candidate_root(
    *,
    root: Path,
    source_dataset: Path,
    samples: Sequence[SourceSample],
) -> Path:
    """构造 task-owned raw compatibility root, 仅补兼容 surface。"""
    root.mkdir(parents=True, exist_ok=True)
    _write_common_meta(root=root, source_dataset=source_dataset, samples=samples)
    _ensure_directory_reference(source_dataset / "data", root / "data")
    _ensure_directory_reference(source_dataset / "videos", root / "videos")
    return root


def prepare_lerobot_v3_local_root(
    *,
    root: Path,
    source_dataset: Path,
    samples: Sequence[SourceSample],
) -> Path:
    """构造真正可被 Isaac 消费的本地 v3 candidate root。"""
    root.mkdir(parents=True, exist_ok=True)
    _write_common_meta(root=root, source_dataset=source_dataset, samples=samples)
    _ensure_directory_reference(source_dataset / "videos", root / "videos")
    return root


def write_episode_parquet_rows(
    *,
    root: Path,
    rows_by_episode: Mapping[int, Sequence[Mapping[str, object]]],
) -> dict[int, str]:
    """按 episode 写出真实 parquet 布局并返回相对路径映射。"""
    parquet = cast(Any, importlib.import_module("pyarrow.parquet"))
    pa = cast(Any, importlib.import_module("pyarrow"))
    data_root = root / "data"
    _reset_path(data_root)
    relative_paths: dict[int, str] = {}
    for episode_index, rows in sorted(rows_by_episode.items()):
        chunk_index = episode_index // 1000
        episode_dir = data_root / f"chunk-{chunk_index:03d}"
        episode_dir.mkdir(parents=True, exist_ok=True)
        episode_path = episode_dir / f"episode_{episode_index:06d}.parquet"
        table = pa.Table.from_pylist(list(rows))
        parquet.write_table(table, episode_path)
        relative_paths[episode_index] = episode_path.relative_to(root).as_posix()
    return relative_paths


def build_episode_metadata(samples: Sequence[SourceSample]) -> list[dict[str, object]]:
    """从 bounded samples 生成 Isaac 需要的 episodes.jsonl。"""
    tasks_by_episode: dict[int, set[str]] = defaultdict(set)
    count_by_episode: dict[int, int] = defaultdict(int)
    for sample in samples:
        episode_index = _parse_episode_index(sample)
        tasks_by_episode[episode_index].add(sample.language)
        count_by_episode[episode_index] += 1
    rows: list[dict[str, object]] = []
    for episode_index in sorted(count_by_episode):
        rows.append(
            {
                "episode_index": episode_index,
                "length": count_by_episode[episode_index],
                "tasks": sorted(tasks_by_episode[episode_index]),
            }
        )
    return rows


def build_candidate_info(
    *,
    source_dataset: Path,
    samples: Sequence[SourceSample],
) -> dict[str, object]:
    """以 source info.json 为基础生成 bounded candidate info.json。"""
    source_info = cast(
        Mapping[str, object],
        json.loads((source_dataset / "meta" / "info.json").read_text(encoding="utf-8")),
    )
    episode_indices = sorted({_parse_episode_index(sample) for sample in samples})
    chunks_size = require_int(source_info.get("chunks_size", 1000), "chunks_size")
    total_tasks = len({sample.task_index for sample in samples})
    payload = dict(source_info)
    payload["total_episodes"] = len(episode_indices)
    payload["total_frames"] = len(samples)
    payload["total_tasks"] = total_tasks
    payload["total_videos"] = len(episode_indices) * len(CAMERA_VIEWS)
    payload["total_chunks"] = len(
        {episode_index // chunks_size for episode_index in episode_indices}
    )
    payload["splits"] = {"train": f"0:{len(episode_indices)}"}
    return payload


def build_v3_candidate_rows(samples: Sequence[SourceSample]) -> tuple[
    list[dict[str, object]],
    list[dict[str, object]],
    dict[int, list[dict[str, object]]],
]:
    """把 bounded samples 转成真实 LeRobot parquet 行和两个 JSONL 索引。"""
    sample_index: list[dict[str, object]] = []
    episode_index_rows: dict[str, dict[str, object]] = {}
    rows_by_episode: dict[int, list[dict[str, object]]] = defaultdict(list)
    episode_lengths: dict[int, int] = defaultdict(int)
    for row_index, sample in enumerate(samples):
        episode_index = _parse_episode_index(sample)
        sample_index_value = _parse_sample_index(sample)
        row_in_episode = episode_lengths[episode_index]
        episode_lengths[episode_index] += 1
        rows_by_episode[episode_index].append(
            {
                "observation.images.left_wrist_rgb": sample.camera_refs[0],
                "observation.images.head_rgb": sample.camera_refs[1],
                "observation.images.right_wrist_rgb": sample.camera_refs[2],
                "observation.state": list(sample.state),
                "action": list(sample.action),
                "is_first": row_in_episode == 0,
                "is_last": False,
                "is_terminal": False,
                "timestamp": sample.timestamp,
                "frame_index": sample.frame_index,
                "episode_index": episode_index,
                "index": sample_index_value,
                "task_index": sample.task_index,
                "annotation.human.action.task_description": sample.language,
            }
        )
        sample_index.append(
            {
                "episode_id": sample.episode_id,
                "episode_index": episode_index,
                "row_index": row_index,
                "sample_id": sample.sample_id,
                "sample_index": sample_index_value,
                "window_id": sample.window_id,
                "row_in_episode": row_in_episode,
            }
        )
        episode_entry = episode_index_rows.setdefault(
            sample.episode_id,
            {
                "episode_id": sample.episode_id,
                "episode_index": episode_index,
                "sample_count": 0,
                "sample_ids": [],
                "window_ids": [],
            },
        )
        episode_entry["sample_count"] = cast(int, episode_entry["sample_count"]) + 1
        cast(list[str], episode_entry["sample_ids"]).append(sample.sample_id)
        cast(list[str], episode_entry["window_ids"]).append(sample.window_id)
    for episode_rows in rows_by_episode.values():
        if episode_rows:
            episode_rows[-1]["is_last"] = True
            episode_rows[-1]["is_terminal"] = True
    return sample_index, list(episode_index_rows.values()), rows_by_episode


def write_lerobot_meta_and_indices(
    *,
    root: Path,
    source_dataset: Path,
    samples: Sequence[SourceSample],
    sample_index: Sequence[Mapping[str, object]] | None = None,
    episode_index: Sequence[Mapping[str, object]] | None = None,
) -> None:
    """写出 Isaac 兼容 meta surface 与 AutoVLA JSONL 索引。"""
    _write_common_meta(root=root, source_dataset=source_dataset, samples=samples)
    if sample_index is not None:
        write_jsonl(root / "sample_index.jsonl", sample_index)
    if episode_index is not None:
        write_jsonl(root / "episode_index.jsonl", episode_index)


def _write_common_meta(
    *,
    root: Path,
    source_dataset: Path,
    samples: Sequence[SourceSample],
) -> None:
    """写出共享的 meta/info/tasks/modality/stats/episodes surface。"""
    meta_root = root / "meta"
    _reset_path(meta_root)
    meta_root.mkdir(parents=True, exist_ok=True)
    info_payload = build_candidate_info(source_dataset=source_dataset, samples=samples)
    write_json(meta_root / "info.json", info_payload)
    write_json(meta_root / "modality.json", BLACK_RUBBER_MODALITY_LAYOUT)
    write_jsonl(meta_root / "episodes.jsonl", build_episode_metadata(samples))
    shutil.copy2(source_dataset / "meta" / "tasks.jsonl", meta_root / "tasks.jsonl")
    source_stats = source_dataset / "meta" / "stats.json"
    if source_stats.is_file():
        shutil.copy2(source_stats, meta_root / "stats.json")
    else:
        write_json(meta_root / "stats.json", _build_fallback_stats(samples))


def _ensure_directory_reference(source: Path, destination: Path) -> None:
    """创建安全目录引用, 优先使用相对符号链接。"""
    _reset_path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    relative_target = os.path.relpath(source, destination.parent)
    destination.symlink_to(relative_target, target_is_directory=True)


def _reset_path(path: Path) -> None:
    """重建前清理旧路径。"""
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _parse_episode_index(sample: SourceSample) -> int:
    """从稳定 episode_id 解析数值 episode_index。"""
    return int(sample.episode_id.removeprefix("episode-"))


def _parse_sample_index(sample: SourceSample) -> int:
    """从稳定 sample_id 解析数值 sample_index。"""
    return int(sample.sample_id.removeprefix("sample-"))


def _build_fallback_stats(samples: Sequence[SourceSample]) -> dict[str, object]:
    """为 tiny fixture 生成最小可用 stats.json。"""
    action_values = [list(sample.action) for sample in samples]
    state_values = [list(sample.state) for sample in samples]
    return {
        "action": _summarize_numeric_matrix(action_values),
        "observation.state": _summarize_numeric_matrix(state_values),
    }


def _summarize_numeric_matrix(values: Sequence[Sequence[float]]) -> dict[str, object]:
    """对二维数值矩阵生成基础统计。"""
    if not values:
        return {"mean": [], "std": [], "min": [], "max": [], "q01": [], "q99": []}
    width = len(values[0])
    columns = [[float(row[index]) for row in values] for index in range(width)]
    summary: dict[str, object] = {
        "mean": [sum(column) / len(column) for column in columns],
        "min": [min(column) for column in columns],
        "max": [max(column) for column in columns],
    }
    summary["std"] = [_population_std(column) for column in columns]
    summary["q01"] = [float(min(column)) for column in columns]
    summary["q99"] = [float(max(column)) for column in columns]
    return summary


def _population_std(values: Sequence[float]) -> float:
    """计算总体标准差。"""
    if not values:
        return 0.0
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return variance**0.5
