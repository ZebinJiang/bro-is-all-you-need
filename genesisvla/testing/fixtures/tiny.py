"""M2 tiny fixture 生成器。"""

from __future__ import annotations

import importlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import DatasetStatistics, FeatureStatistics

LEROBOT_RELEASE_TAG = "v0.5.1"
LEROBOT_UPSTREAM_REVISION = "1396b9fab7aecddd10006c33c47a487ffdcb54b4"
LEROBOT_CODEBASE_VERSION = "v3.0"
_ACTION_DIM = 3
_FRAMES_PER_EPISODE = 2
_EPISODE_COUNT = 2
_PA: Any = importlib.import_module("pyarrow")
_PQ: Any = importlib.import_module("pyarrow.parquet")


@dataclass(frozen=True, slots=True)
class TinyLeRobotFixture:
    """真实文件格式的 tiny LeRobot v3 fixture 描述。"""

    root: Path
    samples: tuple[RawSample, ...]
    statistics: DatasetStatistics
    provenance: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TinyParquetFixture:
    """真实 parquet 文件格式的 tiny fixture 描述。"""

    path: Path
    samples: tuple[RawSample, ...]
    provenance: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TinyParquetSchemaSummary:
    """fixture parquet 文件的轻量 schema 摘要。"""

    row_count: int
    column_types: Mapping[str, str]


def _action_statistics() -> FeatureStatistics:
    """返回 tiny fixture 的动作统计量。"""
    return FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 2.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
        names=("x", "y", "padding"),
    )


def _state_statistics() -> FeatureStatistics:
    """返回 tiny fixture 的状态统计量。"""
    return FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 1.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
        names=("joint_a", "joint_b", "padding"),
    )


def _statistics(*, dataset_fingerprint: str) -> DatasetStatistics:
    """构造绑定真实 fixture 的统计量缓存对象。"""
    return DatasetStatistics(
        schema_version="2.0",
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint="raw",
        count=_EPISODE_COUNT,
        state=_state_statistics(),
        action=_action_statistics(),
        metadata={"fixture": dataset_fingerprint, "source": "generated"},
    )


def _image(index: int) -> NDArray[np.uint8]:
    """构造 RawSample adapter 使用的确定性小图像。"""
    base = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    return base + np.uint8(index)


def _action_rows(episode_index: int) -> NDArray[np.float32]:
    """返回单个 episode 的逐帧动作。"""
    base = np.asarray([[2.0, 6.0, 99.0], [4.0, 10.0, 99.0]], dtype=np.float32)
    delta = np.asarray([[episode_index, episode_index, 0.0]], dtype=np.float32)
    return base + delta


def _state_row(episode_index: int) -> NDArray[np.float32]:
    """返回单个 episode 的状态参考向量。"""
    return np.asarray([1.0 + episode_index, 2.0 + episode_index, 99.0], dtype=np.float32)


def _sample_source(episode_index: int) -> dict[str, object]:
    """返回样本来源 JSON 元数据。"""
    return {
        "dataset": "tiny-generated",
        "episode_index": episode_index,
        "format": "lerobot-v3",
        "sample_key": f"episode-{episode_index}",
    }


def _frame_records() -> list[dict[str, object]]:
    """构造四帧确定性 parquet 记录。"""
    records: list[dict[str, object]] = []
    row_index = 0
    for episode_index in range(_EPISODE_COUNT):
        actions = _action_rows(episode_index)
        state = _state_row(episode_index)
        for frame_index in range(_FRAMES_PER_EPISODE):
            records.append(
                {
                    "episode_index": episode_index,
                    "frame_index": frame_index,
                    "index": row_index,
                    "timestamp": frame_index / 10.0,
                    "task_index": 0,
                    "language": f"tiny pick-place episode {episode_index}",
                    "robot_tag": "tiny-arm",
                    "state": state.tolist(),
                    "action": actions[frame_index].tolist(),
                    "action_mask": [True, True, False],
                    "source_dataset": "tiny-generated",
                    "source_format": "parquet",
                    "sample_source": json.dumps(
                        _sample_source(episode_index),
                        sort_keys=True,
                        separators=(",", ":"),
                    ),
                }
            )
            row_index += 1
    return records


def _lerobot_schema() -> Any:
    """返回 tiny LeRobot data shard schema。"""
    return _PA.schema(
        [
            _PA.field("index", _PA.int64(), nullable=False),
            _PA.field("episode_index", _PA.int64(), nullable=False),
            _PA.field("frame_index", _PA.int64(), nullable=False),
            _PA.field("timestamp", _PA.float64(), nullable=False),
            _PA.field("task_index", _PA.int64(), nullable=False),
            _PA.field("observation.state", _PA.list_(_PA.float32(), _ACTION_DIM), nullable=False),
            _PA.field("action", _PA.list_(_PA.float32(), _ACTION_DIM), nullable=False),
            _PA.field("action_mask", _PA.list_(_PA.bool_(), _ACTION_DIM), nullable=False),
            _PA.field("language", _PA.string(), nullable=False),
            _PA.field("robot_tag", _PA.string(), nullable=False),
            _PA.field("sample_source", _PA.string(), nullable=False),
        ]
    )


def _parquet_schema() -> Any:
    """返回 tiny standalone parquet schema。"""
    return _PA.schema(
        [
            _PA.field("episode_index", _PA.int64(), nullable=False),
            _PA.field("frame_index", _PA.int64(), nullable=False),
            _PA.field("index", _PA.int64(), nullable=False),
            _PA.field("timestamp", _PA.float64(), nullable=False),
            _PA.field("task_index", _PA.int64(), nullable=False),
            _PA.field("language", _PA.string(), nullable=False),
            _PA.field("robot_tag", _PA.string(), nullable=False),
            _PA.field("state", _PA.list_(_PA.float32(), _ACTION_DIM), nullable=False),
            _PA.field("action", _PA.list_(_PA.float32(), _ACTION_DIM), nullable=False),
            _PA.field("action_mask", _PA.list_(_PA.bool_(), _ACTION_DIM), nullable=False),
            _PA.field("source_dataset", _PA.string(), nullable=False),
            _PA.field("source_format", _PA.string(), nullable=False),
        ]
    )


def _episode_schema() -> Any:
    """返回 tiny LeRobot episode metadata schema。"""
    return _PA.schema(
        [
            _PA.field("episode_index", _PA.int64(), nullable=False),
            _PA.field("start_index", _PA.int64(), nullable=False),
            _PA.field("end_index", _PA.int64(), nullable=False),
            _PA.field("length", _PA.int64(), nullable=False),
            _PA.field("task_index", _PA.int64(), nullable=False),
            _PA.field("task", _PA.string(), nullable=False),
        ]
    )


def _table_from_columns(schema: Any, columns: Mapping[str, Sequence[object]]) -> Any:
    """按指定 schema 创建 parquet table, 避免推断出宽松类型。"""
    arrays = [_PA.array(columns[name], type=schema.field(name).type) for name in schema.names]
    return _PA.Table.from_arrays(arrays, schema=schema)


def _write_lerobot_data(root: Path) -> None:
    """写入 LeRobot v3-like metadata 和 data parquet 分片。"""
    records = _frame_records()
    data_dir = root / "data/chunk-000"
    episode_dir = root / "meta/episodes/chunk-000"
    meta_dir = root / "meta"
    data_dir.mkdir(parents=True, exist_ok=True)
    episode_dir.mkdir(parents=True, exist_ok=True)

    data_schema = _lerobot_schema()
    data_columns: dict[str, Sequence[object]] = {
        "index": [record["index"] for record in records],
        "episode_index": [record["episode_index"] for record in records],
        "frame_index": [record["frame_index"] for record in records],
        "timestamp": [record["timestamp"] for record in records],
        "task_index": [record["task_index"] for record in records],
        "observation.state": [record["state"] for record in records],
        "action": [record["action"] for record in records],
        "action_mask": [record["action_mask"] for record in records],
        "language": [record["language"] for record in records],
        "robot_tag": [record["robot_tag"] for record in records],
        "sample_source": [record["sample_source"] for record in records],
    }
    _PQ.write_table(_table_from_columns(data_schema, data_columns), data_dir / "file-000.parquet")

    episode_schema = _episode_schema()
    episode_columns: dict[str, Sequence[object]] = {
        "episode_index": [0, 1],
        "start_index": [0, 2],
        "end_index": [2, 4],
        "length": [2, 2],
        "task_index": [0, 0],
        "task": ["tiny pick-place", "tiny pick-place"],
    }
    _PQ.write_table(
        _table_from_columns(episode_schema, episode_columns),
        episode_dir / "file-000.parquet",
    )

    info = {
        "codebase_version": LEROBOT_CODEBASE_VERSION,
        "release_tag": LEROBOT_RELEASE_TAG,
        "upstream_revision": LEROBOT_UPSTREAM_REVISION,
        "fps": 10,
        "total_episodes": _EPISODE_COUNT,
        "total_frames": len(records),
        "total_tasks": 1,
        "data_path": "data/chunk-{episode_chunk:03d}/file-{file:03d}.parquet",
        "features": {
            "observation.state": {"dtype": "float32", "shape": [_ACTION_DIM]},
            "action": {"dtype": "float32", "shape": [_ACTION_DIM]},
            "action_mask": {"dtype": "bool", "shape": [_ACTION_DIM]},
        },
    }
    (meta_dir / "info.json").write_text(
        json.dumps(info, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "tasks.jsonl").write_text(
        json.dumps({"task_index": 0, "task": "tiny pick-place"}, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (meta_dir / "stats.json").write_text(
        json.dumps(
            _statistics(dataset_fingerprint="tiny-lerobot-v3-generated-v1").to_json_dict(),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_parquet_data(path: Path) -> None:
    """写入 standalone parquet fixture。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    records = _frame_records()
    schema = _parquet_schema()
    columns: dict[str, Sequence[object]] = {
        "episode_index": [record["episode_index"] for record in records],
        "frame_index": [record["frame_index"] for record in records],
        "index": [record["index"] for record in records],
        "timestamp": [record["timestamp"] for record in records],
        "task_index": [record["task_index"] for record in records],
        "language": [record["language"] for record in records],
        "robot_tag": [record["robot_tag"] for record in records],
        "state": [record["state"] for record in records],
        "action": [record["action"] for record in records],
        "action_mask": [record["action_mask"] for record in records],
        "source_dataset": [record["source_dataset"] for record in records],
        "source_format": [record["source_format"] for record in records],
    }
    _PQ.write_table(_table_from_columns(schema, columns), path)


def _read_table(path: Path, *, label: str) -> Any:
    """读取 parquet table 并把底层异常转为 fixture 契约错误。"""
    if not path.is_file():
        raise FileNotFoundError(str(path))
    try:
        return _PQ.read_table(path)
    except Exception as exc:
        raise ValueError(f"{label} parquet file is invalid") from exc


def _require_schema(table: Any, schema: Any, *, label: str) -> None:
    """校验 parquet table 含有必需列、精确类型且无 null。"""
    for field in schema:
        if field.name not in table.column_names:
            raise ValueError(f"{label} missing required column: {field.name}")
        observed = table.schema.field(field.name)
        if observed.type != field.type:
            raise ValueError(f"{label} column {field.name} has wrong type: {observed.type}")
        if table[field.name].null_count:
            raise ValueError(f"{label} column {field.name} must not contain nulls")


def _float_vector(value: object, *, name: str) -> list[float]:
    """校验并返回固定长度 float 向量。"""
    sequence = cast(Sequence[object], value)
    if len(sequence) != _ACTION_DIM:
        raise ValueError(f"{name} must have length {_ACTION_DIM}")
    return [_float_scalar(item, name=name) for item in sequence]


def _float_scalar(value: object, *, name: str) -> float:
    """校验并返回 float 标量。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must contain numeric values")
    return float(value)


def _int_scalar(value: object, *, name: str) -> int:
    """校验并返回 int 标量。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} must be an integer")
    return int(value)


def _bool_vector(value: object, *, name: str) -> list[bool]:
    """校验并返回固定长度 bool 向量。"""
    sequence = cast(Sequence[object], value)
    if len(sequence) != _ACTION_DIM:
        raise ValueError(f"{name} must have length {_ACTION_DIM}")
    if not all(isinstance(item, bool) for item in sequence):
        raise ValueError(f"{name} must contain bool values")
    return [bool(item) for item in sequence]


def _samples_from_rows(
    rows: Sequence[Mapping[str, object]],
    *,
    source_format: str,
) -> tuple[RawSample, ...]:
    """把逐帧记录聚合为 RawSample episode。"""
    grouped: dict[int, list[Mapping[str, object]]] = {}
    for row in rows:
        episode_index = _int_scalar(row["episode_index"], name="episode_index")
        grouped.setdefault(episode_index, []).append(row)

    samples: list[RawSample] = []
    for episode_index in sorted(grouped):
        episode_rows = sorted(
            grouped[episode_index],
            key=lambda item: _int_scalar(item["frame_index"], name="frame_index"),
        )
        actions = np.asarray(
            [_float_vector(row["action"], name="action") for row in episode_rows],
            dtype=np.float32,
        )
        state_key = "observation.state" if "observation.state" in episode_rows[0] else "state"
        state = np.asarray(
            _float_vector(episode_rows[0][state_key], name=state_key),
            dtype=np.float32,
        )
        action_mask = np.asarray(
            [_bool_vector(row["action_mask"], name="action_mask") for row in episode_rows],
            dtype=np.bool_,
        )
        language = str(episode_rows[0]["language"])
        robot_tag = str(episode_rows[0]["robot_tag"])
        sample_source = _sample_source(episode_index)
        if source_format == "lerobot-v3":
            sample_source = cast(
                dict[str, object],
                json.loads(str(episode_rows[0]["sample_source"])),
            )
        else:
            sample_source = {
                "dataset": str(episode_rows[0]["source_dataset"]),
                "episode_index": episode_index,
                "format": str(episode_rows[0]["source_format"]),
                "sample_key": f"episode-{episode_index}",
            }
        samples.append(
            RawSample(
                images={"front": _image(episode_index)},
                language=language,
                actions=actions,
                state=state,
                robot_tag=robot_tag,
                metadata={
                    "episode_id": episode_index,
                    "action_mask": action_mask,
                    "sample_source": sample_source,
                },
            )
        )
    return tuple(samples)


def _rows_from_table(table: Any, *, state_column: str) -> tuple[Mapping[str, object], ...]:
    """把 parquet table 转为普通行映射。"""
    columns = {name: table[name].to_pylist() for name in table.column_names}
    rows: list[dict[str, object]] = []
    for index in range(table.num_rows):
        rows.append({name: values[index] for name, values in columns.items()})
    if state_column not in columns:
        raise ValueError(f"missing state column: {state_column}")
    return tuple(rows)


def _validate_lerobot_relationships(root: Path, data_table: Any) -> None:
    """校验 LeRobot metadata 与 data/episode 分片关系。"""
    info_path = root / "meta/info.json"
    task_path = root / "meta/tasks.jsonl"
    episode_path = root / "meta/episodes/chunk-000/file-000.parquet"
    if not info_path.is_file():
        raise FileNotFoundError(str(info_path))
    if not task_path.is_file():
        raise FileNotFoundError(str(task_path))
    info = json.loads(info_path.read_text(encoding="utf-8"))
    if info.get("codebase_version") != LEROBOT_CODEBASE_VERSION:
        raise ValueError("codebase_version mismatch")
    if int(info.get("total_frames", -1)) != data_table.num_rows:
        raise ValueError("total_frames mismatch")
    if int(info.get("total_episodes", -1)) != _EPISODE_COUNT:
        raise ValueError("total_episodes mismatch")

    episode_table = _read_table(episode_path, label="lerobot episodes")
    _require_schema(episode_table, _episode_schema(), label="lerobot episodes")
    starts = episode_table["start_index"].to_pylist()
    ends = episode_table["end_index"].to_pylist()
    lengths = episode_table["length"].to_pylist()
    for start, end, length in zip(starts, ends, lengths, strict=True):
        if int(start) < 0 or int(end) > data_table.num_rows or int(end) <= int(start):
            raise ValueError("episode bounds must fit total_frames")
        if int(end) - int(start) != int(length):
            raise ValueError("episode length must match start/end bounds")


def _lerobot_provenance() -> dict[str, str]:
    """返回 LeRobot fixture 来源记录。"""
    return {
        "source": "generated",
        "format": "lerobot-v3",
        "real_format": "true",
        "release_tag": LEROBOT_RELEASE_TAG,
        "upstream_revision": LEROBOT_UPSTREAM_REVISION,
        "license": "project-generated",
    }


def _parquet_provenance() -> dict[str, str]:
    """返回 standalone parquet fixture 来源记录。"""
    return {
        "source": "generated",
        "format": "parquet",
        "real_format": "true",
        "license": "project-generated",
    }


def _semantic_type_name(raw_type: object) -> str:
    """把 PyArrow type 字符串归一化为稳定测试摘要。"""
    text = str(raw_type)
    if "fixed_size_list" in text and "float" in text and f"[{_ACTION_DIM}]" in text:
        return "fixed_size_list<float32>[3]"
    if "fixed_size_list" in text and "bool" in text and f"[{_ACTION_DIM}]" in text:
        return "fixed_size_list<bool>[3]"
    return text


def describe_parquet_file(path: Path) -> TinyParquetSchemaSummary:
    """返回 parquet 文件行数和列类型摘要, 供测试避免直接依赖 PyArrow 类型。"""
    table = _read_table(path, label="parquet summary")
    return TinyParquetSchemaSummary(
        row_count=int(table.num_rows),
        column_types={
            str(name): _semantic_type_name(table.schema.field(name).type)
            for name in table.column_names
        },
    )


def rewrite_parquet_without_column(path: Path, column: str) -> None:
    """重写 parquet 文件并删除指定列, 用于损坏格式测试。"""
    table = _read_table(path, label="tiny parquet")
    _PQ.write_table(table.drop_columns([column]), path)


def rewrite_parquet_action_mask_as_int(path: Path) -> None:
    """把 action_mask 列重写为 int8 fixed-size-list, 用于 dtype 损坏测试。"""
    table = _read_table(path, label="tiny parquet")
    bad_mask = _PA.array(
        [[1, 1, 0] for _ in range(int(table.num_rows))],
        type=_PA.list_(_PA.int8(), _ACTION_DIM),
    )
    bad_table = table.set_column(
        table.column_names.index("action_mask"),
        "action_mask",
        bad_mask,
    )
    _PQ.write_table(bad_table, path)


def tiny_lerobot_fixture(root: Path) -> TinyLeRobotFixture:
    """生成并重载一个真实 LeRobot v3-like tiny fixture。"""
    _write_lerobot_data(root)
    return load_tiny_lerobot_fixture(root)


def load_tiny_lerobot_fixture(root: Path) -> TinyLeRobotFixture:
    """从磁盘读取并验证 tiny LeRobot v3-like fixture。"""
    data_path = root / "data/chunk-000/file-000.parquet"
    data_table = _read_table(data_path, label="lerobot data")
    _require_schema(data_table, _lerobot_schema(), label="lerobot data")
    _validate_lerobot_relationships(root, data_table)
    rows = _rows_from_table(data_table, state_column="observation.state")
    return TinyLeRobotFixture(
        root=root,
        samples=_samples_from_rows(rows, source_format="lerobot-v3"),
        statistics=_statistics(dataset_fingerprint="tiny-lerobot-v3-generated-v1"),
        provenance=_lerobot_provenance(),
    )


def tiny_parquet_fixture(path: Path) -> TinyParquetFixture:
    """生成并重载一个真实 standalone parquet tiny fixture。"""
    _write_parquet_data(path)
    return load_tiny_parquet_fixture(path)


def load_tiny_parquet_fixture(path: Path) -> TinyParquetFixture:
    """从磁盘读取并验证 standalone parquet tiny fixture。"""
    table = _read_table(path, label="tiny parquet")
    _require_schema(table, _parquet_schema(), label="tiny parquet")
    rows = _rows_from_table(table, state_column="state")
    return TinyParquetFixture(
        path=path,
        samples=_samples_from_rows(rows, source_format="parquet"),
        provenance=_parquet_provenance(),
    )
