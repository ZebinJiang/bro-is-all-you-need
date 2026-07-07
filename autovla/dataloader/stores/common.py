"""多格式 datastore bakeoff 共享合同与工具。"""

from __future__ import annotations

import csv
import hashlib
import importlib
import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

CAMERA_VIEWS: tuple[str, str, str] = (
    "observation.images.left_wrist_rgb",
    "observation.images.head_rgb",
    "observation.images.right_wrist_rgb",
)
CANDIDATE_IDS: tuple[str, str, str, str] = (
    "zjh_lerobot_v21_raw",
    "zjh_lerobot_v3_local",
    "zjh_webdataset_tar",
    "zjh_robodm_container_v1",
)
DEFAULT_MANIFEST_VERSION = "autovla.multiformat_sample_window_manifest.v1"
DEFAULT_LEDGER_VERSION = "autovla.multiformat_artifact_ledger.v1"
DEFAULT_TABLE_VERSION = "autovla.multiformat_load_benchmark.v1"
PayloadRow = dict[str, object]
ReaderFn = Callable[[Sequence[int]], list[PayloadRow]]


@dataclass(frozen=True, slots=True)
class MultiformatDatastoreConfig:
    """保存多格式 datastore bakeoff 的有界配置。"""

    source_dataset: Path
    working_root: Path
    output_dir: Path
    readonly_root: Path | None = None
    max_episodes: int = 4
    max_samples: int = 512
    seed: int = 11
    window_size: int = 1
    action_horizon: int = 1
    batch_size: int = 1
    measured_batches: int = 4
    samples_per_shard: int = 128

    def __post_init__(self) -> None:
        """校验路径、只读边界与 bounded 参数。"""
        for field_name in (
            "max_episodes",
            "max_samples",
            "window_size",
            "action_horizon",
            "batch_size",
            "measured_batches",
            "samples_per_shard",
        ):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise ValueError(f"{field_name} must be a positive integer")
        if isinstance(self.seed, bool) or self.seed < 0:
            raise ValueError("seed must be a non-negative integer")

        source = self.source_dataset.resolve()
        working = self.working_root.resolve()
        output = self.output_dir.resolve()
        readonly_root = (
            self.readonly_root.resolve()
            if self.readonly_root is not None
            else (Path(__file__).resolve().parents[3] / "datasets" / "readonly").resolve()
        )
        if source != readonly_root and readonly_root not in source.parents:
            raise ValueError("source_dataset must stay under readonly_root")
        if working == source or source in working.parents:
            raise ValueError("working_root must not be inside source_dataset")
        if output == source or source in output.parents:
            raise ValueError("output_dir must not be inside source_dataset")


@dataclass(frozen=True, slots=True)
class SourceSample:
    """保存共享 sample/window manifest 选出的单条样本。"""

    sample_id: str
    window_id: str
    episode_id: str
    frame_index: int
    task_index: int
    timestamp: float
    action: tuple[float, ...]
    action_mask: tuple[bool, ...]
    state: tuple[float, ...]
    language: str
    camera_refs: tuple[str, str, str]

    def payload(self, source_mode: str) -> dict[str, object]:
        """返回稳定 JSON-safe payload。"""
        payload: dict[str, object] = {
            "action": list(self.action),
            "action_mask": list(self.action_mask),
            "camera_refs": list(self.camera_refs),
            "episode_id": self.episode_id,
            "frame_index": self.frame_index,
            "language": self.language,
            "sample_id": self.sample_id,
            "source_mode": source_mode,
            "state": list(self.state),
            "task_index": self.task_index,
            "timestamp": round(self.timestamp, 6),
            "window_id": self.window_id,
        }
        payload["payload_hash"] = stable_checksum(payload)
        return payload


@dataclass(frozen=True, slots=True)
class BenchmarkStats:
    """保存单个候选的 load benchmark 统计。"""

    sample_count: int
    batch_size: int
    build_time_ms: float
    p50_ms: float
    p95_ms: float
    samples_per_second: float

    def to_json_dict(self) -> dict[str, object]:
        """返回 JSON-safe benchmark 字段。"""
        return {
            "batch_size": self.batch_size,
            "build_time_ms": round(self.build_time_ms, 6),
            "p50_ms": round(self.p50_ms, 6),
            "p95_ms": round(self.p95_ms, 6),
            "sample_count": self.sample_count,
            "samples_per_second": round(self.samples_per_second, 6),
        }


def stable_json_bytes(payload: object) -> bytes:
    """返回稳定 JSON 编码。"""
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def stable_checksum(payload: object) -> str:
    """返回稳定 SHA256 校验和。"""
    return hashlib.sha256(stable_json_bytes(payload)).hexdigest()


def write_json(path: Path, payload: Mapping[str, object]) -> None:
    """写出稳定 JSON。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: Sequence[Mapping[str, object]]) -> None:
    """写出稳定 JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(row, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: Sequence[Mapping[str, object]], fieldnames: Sequence[str]) -> None:
    """写出稳定 CSV 表。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def require_mapping(value: object, field_name: str) -> Mapping[str, object]:
    """把对象校验为 mapping。"""
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a mapping")
    return cast(Mapping[str, object], value)


def require_str(value: object, field_name: str) -> str:
    """读取非空字符串。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def require_int(value: object, field_name: str) -> int:
    """读取整数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def require_float(value: object, field_name: str) -> float:
    """读取数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    return float(value)


def _coerce_camera_ref(value: object, field_name: str) -> str:
    """把相机列收窄为稳定的视频路径字符串。"""
    if isinstance(value, str) and value:
        return value
    if isinstance(value, Mapping):
        mapping_value = cast(Mapping[str, object], value)
        path_value = mapping_value.get("path")
        if not isinstance(path_value, str) or not path_value:
            raise ValueError(f"{field_name}.path must be a non-empty string")
        return path_value
    raise ValueError(f"{field_name} must be a non-empty string or mapping with path")


def read_metadata(source_dataset: Path) -> Mapping[str, object]:
    """读取 ZJH/LeRobot v2.1 元数据。"""
    return cast(
        Mapping[str, object],
        json.loads((source_dataset / "meta" / "info.json").read_text(encoding="utf-8")),
    )


def read_tasks(source_dataset: Path) -> dict[int, str]:
    """读取 task_index 到任务文本的映射。"""
    path = source_dataset / "meta" / "tasks.jsonl"
    if not path.is_file():
        return {}
    tasks: dict[int, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = cast(Mapping[str, object], json.loads(line))
        task_index = require_int(payload.get("task_index"), "task_index")
        task_value = payload.get("task", payload.get("task_text"))
        tasks[task_index] = require_str(task_value, "task")
    return tasks


def load_source_samples(config: MultiformatDatastoreConfig) -> list[SourceSample]:
    """从 source parquet 读取有界样本, 不写入任何源路径。"""
    metadata = read_metadata(config.source_dataset)
    tasks = read_tasks(config.source_dataset)
    pq_module = importlib.import_module("pyarrow.parquet")
    parquet = cast(Any, pq_module)
    rows: list[SourceSample] = []
    seen_episodes: set[int] = set()
    for parquet_path in sorted((config.source_dataset / "data").glob("chunk-*/*.parquet")):
        table = parquet.read_table(parquet_path)
        columns = tuple(str(name) for name in table.column_names)
        required = set(CAMERA_VIEWS) | {"observation.state", "action", "timestamp", "frame_index"}
        if not required.issubset(columns):
            raise ValueError("source parquet columns do not match expected ZJH schema")
        for row_index in range(table.num_rows):
            row = {column: table[column][row_index].as_py() for column in columns}
            episode_index = require_int(row.get("episode_index"), "episode_index")
            if episode_index not in seen_episodes and len(seen_episodes) >= config.max_episodes:
                continue
            seen_episodes.add(episode_index)
            rows.append(_build_source_sample(metadata=metadata, raw=row, tasks=tasks))
            if len(rows) >= config.max_samples:
                return rows
    if not rows:
        raise ValueError("source dataset did not yield any bounded samples")
    return rows


def _build_source_sample(
    *,
    metadata: Mapping[str, object],
    raw: Mapping[str, object],
    tasks: Mapping[int, str],
) -> SourceSample:
    """把 parquet row 规范化为 SourceSample。"""
    action_values = _coerce_float_tuple(raw.get("action"), "action")
    state_values = _coerce_float_tuple(raw.get("observation.state"), "observation.state")
    task_index = require_int(raw.get("task_index", 0), "task_index")
    language = raw.get("annotation.human.action.task_description") or tasks.get(task_index)
    if not isinstance(language, str) or not language:
        raise ValueError("language text is required")
    sample_index = require_int(raw.get("index"), "index")
    episode_index = require_int(raw.get("episode_index"), "episode_index")
    frame_index = require_int(raw.get("frame_index"), "frame_index")
    camera_refs = tuple(_coerce_camera_ref(raw.get(camera), camera) for camera in CAMERA_VIEWS)
    sample_id = f"sample-{sample_index:09d}"
    episode_id = f"episode-{episode_index:06d}"
    timestamp = require_float(raw.get("timestamp"), "timestamp")
    window_id = f"{episode_id}:{sample_id}:{frame_index}"
    return SourceSample(
        sample_id=sample_id,
        window_id=window_id,
        episode_id=episode_id,
        frame_index=frame_index,
        task_index=task_index,
        timestamp=timestamp,
        action=action_values,
        action_mask=tuple(True for _ in action_values),
        state=state_values,
        language=language,
        camera_refs=cast(tuple[str, str, str], camera_refs),
    )


def measure_reader(
    *,
    sample_count: int,
    batch_size: int,
    measured_batches: int,
    reader: ReaderFn,
) -> BenchmarkStats:
    """对单个 reader 路径做轻量 load benchmark。"""
    latencies_ms: list[float] = []
    total_batches = max(1, (sample_count + batch_size - 1) // batch_size)
    effective_batches = max(1, min(measured_batches, total_batches))
    started = time.perf_counter()
    for batch_index in range(effective_batches):
        start = batch_index * batch_size
        indices = tuple(index for index in range(start, min(start + batch_size, sample_count)))
        tick = time.perf_counter()
        payloads: list[PayloadRow] = reader(indices)
        latency_ms = (time.perf_counter() - tick) * 1000.0
        if len(payloads) != len(indices):
            raise ValueError("reader returned unexpected payload count")
        latencies_ms.append(latency_ms)
    total_time_s = max(time.perf_counter() - started, 1e-9)
    sorted_latencies = sorted(latencies_ms)
    p50 = sorted_latencies[len(sorted_latencies) // 2]
    p95_index = min(len(sorted_latencies) - 1, math_ceil(0.95 * len(sorted_latencies)) - 1)
    p95 = sorted_latencies[p95_index]
    return BenchmarkStats(
        sample_count=sample_count,
        batch_size=batch_size,
        build_time_ms=0.0,
        p50_ms=p50,
        p95_ms=p95,
        samples_per_second=sample_count / total_time_s,
    )


def math_ceil(value: float) -> int:
    """提供最小依赖的 ceil。"""
    integer = int(value)
    return integer if float(integer) == value else integer + 1


def _coerce_float_tuple(value: object, field_name: str) -> tuple[float, ...]:
    """把数值序列收窄为 float tuple。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be a numeric sequence")
    raw_items = list(cast(Sequence[object], value))
    numeric_values: list[float] = []
    for item in raw_items:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} must be a numeric sequence")
        numeric_values.append(float(item))
    return tuple(numeric_values)
