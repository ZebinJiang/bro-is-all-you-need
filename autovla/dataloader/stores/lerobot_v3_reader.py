"""本地 LeRobot v3 row-group 和媒体分组 reader。"""

from __future__ import annotations

import importlib
import json
from collections import OrderedDict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, cast

import numpy as np

from autovla.data.datasets.base import contained_path
from autovla.data.datasets.local_lerobot import LocalLeRobotMetadata
from autovla.dataloader.stores.common import require_str

_VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".webm"}
_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}


class LeRobotGroupedReader:
    """缓存 ParquetFile/footer/row-group、图片和可选视频容器。"""

    def __init__(
        self,
        metadata: LocalLeRobotMetadata,
        *,
        max_row_groups: int = 2,
        max_images: int = 32,
        max_videos: int = 2,
    ) -> None:
        if min(max_row_groups, max_images, max_videos) <= 0:
            raise ValueError("LeRobot cache bounds must be positive")
        self._metadata = metadata
        self._root = metadata.root.resolve()
        self._max_row_groups = max_row_groups
        self._max_images = max_images
        self._max_videos = max_videos
        self._parquet_files: dict[str, Any] = {}
        self._row_group_map: dict[int, tuple[str, int, int]] = {}
        self._row_groups: OrderedDict[tuple[str, int], Any] = OrderedDict()
        self._images: OrderedDict[Path, np.ndarray[Any, Any]] = OrderedDict()
        self._videos: OrderedDict[Path, Any] = OrderedDict()
        self._counters = {
            "metadata_loads": 1,
            "parquet_file_opens": 0,
            "parquet_file_closes": 0,
            "footer_loads": 0,
            "row_group_reads": 0,
            "row_group_cache_hits": 0,
            "row_group_evictions": 0,
            "image_decodes": 0,
            "image_cache_hits": 0,
            "image_evictions": 0,
            "video_opens": 0,
            "video_cache_hits": 0,
            "video_evictions": 0,
            "video_closes": 0,
        }
        self._initialize_parquet_maps()

    def __getstate__(self) -> dict[str, object]:
        """pickle 时排除 Arrow/Pillow/PyAV live cache 和 handles。"""
        state = dict(self.__dict__)
        state["_parquet_files"] = {}
        state["_row_groups"] = OrderedDict()
        state["_images"] = OrderedDict()
        state["_videos"] = OrderedDict()
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        """spawn 后恢复纯状态并重建 worker-local parquet footer map。"""
        self.__dict__.update(state)
        self._parquet_files = {}
        self._row_groups = OrderedDict()
        self._images = OrderedDict()
        self._videos = OrderedDict()
        self._initialize_parquet_maps()

    def _initialize_parquet_maps(self) -> None:
        """一次打开每个 ParquetFile 并建立 global index 到 row-group 映射。"""
        parquet = cast(Any, importlib.import_module("pyarrow.parquet"))
        entries_by_path: dict[str, list[object]] = {}
        for entry in self._metadata.index:
            entries_by_path.setdefault(entry.data_path, []).append(entry)
        for relative_path, raw_entries in sorted(entries_by_path.items()):
            path = contained_path(self._root, relative_path)
            parquet_file = parquet.ParquetFile(path)
            schema = getattr(parquet_file, "schema_arrow", None)
            if schema is not None:
                required = {
                    "action",
                    "observation.state",
                    "episode_index",
                    "frame_index",
                    "index",
                    "task_index",
                    "timestamp",
                }
                if not required.issubset(set(schema.names)):
                    raise ValueError("LeRobot parquet schema lacks required columns")
            self._parquet_files[relative_path] = parquet_file
            self._counters["parquet_file_opens"] += 1
            self._counters["footer_loads"] += 1
            spans: list[tuple[int, int, int]] = []
            start = 0
            for row_group in range(parquet_file.metadata.num_row_groups):
                count = int(parquet_file.metadata.row_group(row_group).num_rows)
                spans.append((start, start + count, row_group))
                start += count
            entries = cast(list[Any], raw_entries)
            multi_episode = len({entry.episode_index for entry in entries}) > 1
            for ordinal, entry in enumerate(entries):
                physical_row = ordinal if multi_episode else entry.row_in_episode
                match = next((span for span in spans if span[0] <= physical_row < span[1]), None)
                if match is None:
                    raise ValueError("LeRobot index row is outside parquet footer bounds")
                begin, _, row_group = match
                self._row_group_map[entry.global_index] = (
                    relative_path,
                    row_group,
                    physical_row - begin,
                )

    def _row_group(self, data_path: str, row_group: int) -> Any:
        """读取或复用一个有界 row-group table。"""
        key = (data_path, row_group)
        if key in self._row_groups:
            self._counters["row_group_cache_hits"] += 1
            self._row_groups.move_to_end(key)
            return self._row_groups[key]
        table = self._parquet_files[data_path].read_row_group(row_group)
        self._row_groups[key] = table
        self._counters["row_group_reads"] += 1
        if len(self._row_groups) > self._max_row_groups:
            self._row_groups.popitem(last=False)
            self._counters["row_group_evictions"] += 1
        return table

    @staticmethod
    def _take_rows(table: Any, rows: Sequence[int]) -> list[dict[str, object]]:
        """用 Arrow take 向量化选择 row-group 内行。"""
        arrow = cast(Any, importlib.import_module("pyarrow"))
        selected = table.take(arrow.array(tuple(rows), type=arrow.int64()))
        columns = tuple(str(name) for name in selected.column_names)
        return [
            {column: selected[column][row].as_py() for column in columns}
            for row in range(int(selected.num_rows))
        ]

    def _image(self, reference: str) -> np.ndarray[Any, Any]:
        """按物理图片路径分组并使用有界 decoder cache。"""
        path = contained_path(self._root, reference)
        if path in self._images:
            self._counters["image_cache_hits"] += 1
            self._images.move_to_end(path)
            return self._images[path]
        if path.suffix.lower() == ".npy":
            image = np.load(path, allow_pickle=False)
        elif path.suffix.lower() in _IMAGE_SUFFIXES:
            try:
                image_module = importlib.import_module("PIL.Image")
            except ImportError as exc:
                raise RuntimeError(
                    "LeRobot image materialization requires optional dependency pillow; "
                    "install autovla[data-lerobot]"
                ) from exc
            with image_module.open(path) as opened:
                image = np.asarray(opened.convert("RGB")).copy()
        else:
            raise ValueError(f"unsupported local LeRobot image suffix: {path.suffix}")
        self._images[path] = image
        self._counters["image_decodes"] += 1
        if len(self._images) > self._max_images:
            self._images.popitem(last=False)
            self._counters["image_evictions"] += 1
        return image

    def _video_container(self, path: Path) -> Any:
        """懒加载可选 PyAV 容器,不猜测依赖版本。"""
        if path in self._videos:
            self._counters["video_cache_hits"] += 1
            self._videos.move_to_end(path)
            return self._videos[path]
        try:
            av = importlib.import_module("av")
        except ImportError as exc:
            raise RuntimeError(
                "LeRobot video materialization requires optional dependency 'av' (PyAV); "
                "no project-compatible version is pinned by current local evidence"
            ) from exc
        container = av.open(path.as_posix(), mode="r")
        self._videos[path] = container
        self._counters["video_opens"] += 1
        if len(self._videos) > self._max_videos:
            _, stale = self._videos.popitem(last=False)
            stale.close()
            self._counters["video_evictions"] += 1
            self._counters["video_closes"] += 1
        return container

    def _video_frame(self, reference: str, timestamp: float) -> np.ndarray[Any, Any]:
        """从本地视频选择不早于目标时间的第一帧。"""
        path = contained_path(self._root, reference)
        container = self._video_container(path)
        stream = container.streams.video[0]
        time_base = float(stream.time_base)
        container.seek(max(int(timestamp / time_base), 0), stream=stream)
        for frame in container.decode(stream):
            frame_time = float(frame.pts or 0) * time_base
            if frame_time + 1e-9 >= timestamp:
                return cast(np.ndarray[Any, Any], frame.to_ndarray(format="rgb24"))
        raise ValueError(f"LeRobot video has no frame at timestamp {timestamp}: {path}")

    def _materialize_media(
        self, payloads: Sequence[dict[str, object]]
    ) -> list[dict[str, np.ndarray[Any, Any]]]:
        """按图片/视频物理路径复用 decoder 和容器缓存。"""
        output: list[dict[str, np.ndarray[Any, Any]]] = []
        for payload in payloads:
            refs = payload.get("camera_refs", ())
            if not isinstance(refs, Sequence) or isinstance(refs, (str, bytes)):
                raise ValueError("LeRobot camera_refs must be a sequence")
            images: dict[str, np.ndarray[Any, Any]] = {}
            for index, raw_reference in enumerate(refs):
                reference = require_str(raw_reference, "camera_ref")
                path = contained_path(self._root, reference)
                name = f"camera.rgb_{index}"
                if path.suffix.lower() in _VIDEO_SUFFIXES:
                    images[name] = self._video_frame(
                        reference, float(cast(float, payload["timestamp"]))
                    )
                else:
                    images[name] = self._image(reference)
            output.append(images)
        return output

    def read_records(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按 parquet row group 和媒体文件分组,最终恢复请求顺序。"""
        groups: dict[tuple[str, int], list[tuple[int, int, int]]] = {}
        for position, index in enumerate(indices):
            if index < 0 or index >= len(self._metadata.index):
                raise IndexError(index)
            data_path, row_group, local_row = self._row_group_map[index]
            groups.setdefault((data_path, row_group), []).append((position, local_row, index))
        output: list[dict[str, object] | None] = [None] * len(indices)
        payloads_by_position: dict[int, dict[str, object]] = {}
        for (data_path, row_group), requests in groups.items():
            table = self._row_group(data_path, row_group)
            raw_rows = self._take_rows(table, tuple(item[1] for item in requests))
            for (position, local_row, index), raw_row in zip(requests, raw_rows, strict=True):
                payload = _payload_from_raw_row(raw_row=raw_row, tasks=dict(self._metadata.tasks))
                payloads_by_position[position] = payload
                output[position] = {
                    "payload": payload,
                    "physical_source": {
                        "parquet": data_path,
                        "row_group": row_group,
                        "row_in_group": local_row,
                        "global_index": index,
                    },
                }
        ordered_payloads = [payloads_by_position[position] for position in range(len(indices))]
        media = self._materialize_media(ordered_payloads)
        for position, images in enumerate(media):
            assert output[position] is not None
            output[position]["images"] = images
        return [cast(dict[str, object], item) for item in output]

    def read_index_fields(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按 row group 向量化加载精确 episode/frame/timestamp 索引字段。"""
        groups: dict[tuple[str, int], list[tuple[int, int]]] = {}
        for position, index in enumerate(indices):
            data_path, row_group, local_row = self._row_group_map[index]
            groups.setdefault((data_path, row_group), []).append((position, local_row))
        output: list[dict[str, object] | None] = [None] * len(indices)
        for (data_path, row_group), requests in groups.items():
            table = self._row_group(data_path, row_group)
            rows = self._take_rows(table, tuple(local_row for _, local_row in requests))
            for (position, _), row in zip(requests, rows, strict=True):
                output[position] = {
                    "episode_index": _coerce_int(row.get("episode_index"), "episode_index"),
                    "frame_index": _coerce_int(row.get("frame_index"), "frame_index"),
                    "timestamp": _coerce_float(row.get("timestamp"), "timestamp"),
                }
        return [cast(dict[str, object], item) for item in output]

    def read_payloads(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """兼容入口委托 grouped reader 并只返回 payload。"""
        return [cast(dict[str, object], record["payload"]) for record in self.read_records(indices)]

    @property
    def row_group_map(self) -> Mapping[int, tuple[str, int, int]]:
        """返回 global index 到 parquet row-group 的副本。"""
        return dict(self._row_group_map)

    @property
    def counters(self) -> Mapping[str, int]:
        """返回 footer、row-group 和媒体 cache 计数。"""
        return dict(self._counters)

    def close(self) -> None:
        """幂等释放 Arrow 引用、图片 cache 和 PyAV 容器。"""
        for container in self._videos.values():
            container.close()
            self._counters["video_closes"] += 1
        self._videos.clear()
        self._images.clear()
        self._row_groups.clear()
        for parquet_file in self._parquet_files.values():
            close = getattr(parquet_file, "close", None)
            if callable(close):
                close()
            self._counters["parquet_file_closes"] += 1
        self._parquet_files.clear()


def read_lerobot_v3_local_batches(root: Path, indices: Sequence[int]) -> list[dict[str, object]]:
    """通过规范 metadata-once reader 读取本地 payload。"""
    from autovla.data.datasets.local_lerobot import inspect_local_lerobot

    reader = LeRobotGroupedReader(inspect_local_lerobot(root))
    try:
        return reader.read_payloads(indices)
    finally:
        reader.close()


def _payload_from_raw_row(
    *, raw_row: Mapping[str, object], tasks: Mapping[int, str]
) -> dict[str, object]:
    """从 LeRobot parquet 行重建稳定原始物理 payload。"""
    action = _coerce_float_list(raw_row.get("action"), "action")
    state = _coerce_float_list(raw_row.get("observation.state"), "observation.state")
    task_index = _coerce_int(raw_row.get("task_index"), "task_index")
    language_value = raw_row.get("annotation.human.action.task_description") or tasks.get(
        task_index
    )
    language = require_str(language_value, "annotation.human.action.task_description")
    camera_refs = [
        require_str(raw_row.get(name), name)
        for name in (
            "observation.images.left_wrist_rgb",
            "observation.images.head_rgb",
            "observation.images.right_wrist_rgb",
        )
        if raw_row.get(name) is not None
    ]
    if not camera_refs:
        raise ValueError("LeRobot row must contain at least one local image/video reference")
    sample_index = _coerce_int(raw_row.get("index"), "index")
    episode_index = _coerce_int(raw_row.get("episode_index"), "episode_index")
    frame_index = _coerce_int(raw_row.get("frame_index"), "frame_index")
    raw_mask = raw_row.get("action_mask")
    if raw_mask is None:
        action_mask = [True for _ in action]
    else:
        action_mask = _coerce_bool_list(raw_mask, "action_mask")
    payload: dict[str, object] = {
        "action": action,
        "action_mask": action_mask,
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


def _coerce_float_list(value: object, field_name: str) -> list[float]:
    """把 parquet 数值列收窄为 float list。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be numeric sequence")
    values: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} must be numeric sequence")
        values.append(float(item))
    return values


def _coerce_bool_list(value: object, field_name: str) -> list[bool]:
    """把 parquet 掩码列严格收窄为 bool list。"""
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise ValueError(f"{field_name} must be bool sequence")
    if any(type(item) is not bool for item in value):
        raise TypeError(f"{field_name} must be bool sequence")
    return list(cast(Sequence[bool], value))


def _coerce_int(value: object, field_name: str) -> int:
    """把 parquet 标量严格收窄为整数。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _coerce_float(value: object, field_name: str) -> float:
    """把 parquet 标量收窄为有限 float。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be numeric")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _stable_checksum(payload: Mapping[str, object]) -> str:
    """使用稳定 JSON 编码计算 payload 哈希。"""
    import hashlib

    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return hashlib.sha256(encoded).hexdigest()


__all__ = ["LeRobotGroupedReader", "read_lerobot_v3_local_batches"]
