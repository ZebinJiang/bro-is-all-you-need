"""本地 LeRobot v3 row-group 和媒体分组 reader。"""

from __future__ import annotations

import importlib
import json
import os
from collections import OrderedDict
from collections.abc import Iterable, Mapping, Sequence
from pathlib import Path
from typing import Protocol, SupportsFloat, TypeAlias, TypeGuard, runtime_checkable

import numpy as np
from numpy.typing import NDArray

from autovla.data.datasets.base import contained_path
from autovla.data.datasets.local_lerobot import LeRobotIndexEntry, LocalLeRobotMetadata
from autovla.dataloader.stores.common import require_str

_VIDEO_SUFFIXES = {".avi", ".mkv", ".mov", ".mp4", ".webm"}
_IMAGE_SUFFIXES = {".bmp", ".jpeg", ".jpg", ".png", ".tif", ".tiff", ".webp"}
_VIDEO_TIMESTAMP_TOLERANCE_SECONDS = 1e-6
_ImageArray: TypeAlias = NDArray[np.generic]


class _ArrowScalar(Protocol):
    """约束 Arrow scalar 的 Python 值转换。"""

    def as_py(self) -> object:
        """返回 Python 标量或容器。"""

        ...


class _ArrowColumn(Protocol):
    """约束按行索引 Arrow 列。"""

    def __getitem__(self, index: int) -> _ArrowScalar: ...


class _ArrowTable(Protocol):
    """约束 grouped reader 使用的 Arrow table 表面。"""

    @property
    def column_names(self) -> Sequence[str]: ...

    @property
    def num_rows(self) -> int: ...

    def take(self, indices: object) -> _ArrowTable: ...

    def __getitem__(self, name: str) -> _ArrowColumn: ...


class _ParquetSchema(Protocol):
    """约束 Arrow schema 的列名表面。"""

    @property
    def names(self) -> Sequence[str]: ...


class _ParquetRowGroupMetadata(Protocol):
    """约束 row-group 行数元数据。"""

    @property
    def num_rows(self) -> int: ...


class _ParquetFileMetadata(Protocol):
    """约束 parquet footer 的 row-group 表面。"""

    @property
    def num_row_groups(self) -> int: ...

    def row_group(self, index: int) -> _ParquetRowGroupMetadata: ...


class _ParquetFile(Protocol):
    """约束 reader 持有的 ParquetFile handle。"""

    @property
    def schema_arrow(self) -> _ParquetSchema | None: ...

    @property
    def metadata(self) -> _ParquetFileMetadata: ...

    def read_row_group(self, index: int) -> _ArrowTable: ...

    def close(self) -> None: ...


@runtime_checkable
class _ParquetModule(Protocol):
    """约束延迟导入的 parquet 模块。"""

    def ParquetFile(self, path: Path) -> _ParquetFile: ...


@runtime_checkable
class _RuntimeArrowModule(Protocol):
    """约束延迟导入的 Arrow 模块。"""

    def array(self, values: Sequence[int], **options: object) -> object: ...

    def int64(self) -> object: ...


class _OpenedImage(Protocol):
    """约束 Pillow image context 和颜色转换。"""

    def __enter__(self) -> _OpenedImage: ...

    def __exit__(
        self,
        exception_type: object,
        exception: object,
        traceback: object,
    ) -> bool | None: ...

    def convert(self, mode: str) -> object: ...


@runtime_checkable
class _ImageModule(Protocol):
    """约束延迟导入的 Pillow 模块。"""

    def open(self, path: Path) -> _OpenedImage: ...


class _VideoStream(Protocol):
    """约束 PyAV 视频流时间基。"""

    @property
    def time_base(self) -> SupportsFloat | None: ...


class _VideoStreams(Protocol):
    """约束 PyAV 容器的视频流集合。"""

    @property
    def video(self) -> Sequence[_VideoStream]: ...


class _VideoFrame(Protocol):
    """约束 PyAV 解码帧的时间戳和 RGB 转换。"""

    @property
    def pts(self) -> int | None: ...

    def to_ndarray(self, **options: object) -> object: ...


@runtime_checkable
class _VideoContainer(Protocol):
    """约束 worker-local PyAV 容器。"""

    @property
    def streams(self) -> _VideoStreams: ...

    def seek(
        self,
        offset: int,
        *,
        stream: _VideoStream,
        backward: bool,
        any_frame: bool,
    ) -> None: ...

    def decode(self, stream: _VideoStream) -> Iterable[_VideoFrame]: ...

    def close(self) -> None: ...


@runtime_checkable
class _VideoModule(Protocol):
    """约束延迟导入的 PyAV 模块。"""

    def open(self, path: str, *, mode: str) -> _VideoContainer: ...


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态值是否可作为对象映射读取。"""

    return isinstance(value, Mapping)


def _is_object_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """判断动态值是否为非文本序列。"""

    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _require_string_mapping(value: object, name: str) -> dict[str, object]:
    """把动态映射逐键收窄为字符串键对象映射。"""

    if not _is_object_mapping(value):
        raise TypeError(f"{name} must be a mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings")
        result[key] = item
    return result


def _complete_records(records: Sequence[dict[str, object] | None]) -> list[dict[str, object]]:
    """拒绝 reader 内部留下未填充的请求位置。"""

    complete: list[dict[str, object]] = []
    for record in records:
        if record is None:
            raise RuntimeError("LeRobot grouped reader left an unfilled request")
        complete.append(record)
    return complete


class LeRobotVideoDecodeError(ValueError):
    """表示本地 LeRobot 视频流、时间戳或解码内容不满足契约。"""


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
        self._owner_pid = os.getpid()
        self._closed = False
        self._max_row_groups = max_row_groups
        self._max_images = max_images
        self._max_videos = max_videos
        self._parquet_files: dict[str, _ParquetFile] = {}
        self._row_group_map: dict[int, tuple[str, int, int]] = {}
        self._row_groups: OrderedDict[tuple[str, int], _ArrowTable] = OrderedDict()
        self._images: OrderedDict[Path, _ImageArray] = OrderedDict()
        self._videos: OrderedDict[Path, _VideoContainer] = OrderedDict()
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
        try:
            self._initialize_parquet_maps()
        except Exception:
            self.close()
            raise

    def __getstate__(self) -> dict[str, object]:
        """pickle 时排除 Arrow/Pillow/PyAV live cache 和 handles。"""
        state = dict(self.__dict__)
        state["_parquet_files"] = {}
        state["_row_groups"] = OrderedDict()
        state["_images"] = OrderedDict()
        state["_videos"] = OrderedDict()
        state["_owner_pid"] = None
        state["_closed"] = False
        return state

    def __setstate__(self, state: dict[str, object]) -> None:
        """spawn 后恢复纯状态并重建 worker-local parquet footer map。"""
        self.__dict__.update(state)
        self._parquet_files = {}
        self._row_groups = OrderedDict()
        self._images = OrderedDict()
        self._videos = OrderedDict()
        self._owner_pid = os.getpid()
        self._closed = False
        try:
            self._initialize_parquet_maps()
        except Exception:
            self.close()
            raise

    @property
    def owner_pid(self) -> int:
        """返回创建当前 live handle 集合的进程。"""
        return self._owner_pid

    def _require_owner(self) -> None:
        """拒绝从非创建进程使用继承的 Parquet 或 PyAV handle。"""
        if self._owner_pid != os.getpid():
            raise RuntimeError("LeRobot live handles cannot be used across processes")
        if self._closed:
            raise RuntimeError("LeRobot reader is closed")

    def _initialize_parquet_maps(self) -> None:
        """一次打开每个 ParquetFile 并建立 global index 到 row-group 映射。"""
        parquet_module: object = importlib.import_module("pyarrow.parquet")
        if not isinstance(parquet_module, _ParquetModule):
            raise RuntimeError("pyarrow.parquet lacks the required ParquetFile interface")
        entries_by_path: dict[str, list[LeRobotIndexEntry]] = {}
        for entry in self._metadata.index:
            entries_by_path.setdefault(entry.data_path, []).append(entry)
        for relative_path, entries in sorted(entries_by_path.items()):
            path = contained_path(self._root, relative_path)
            parquet_file = parquet_module.ParquetFile(path)
            # 先登记所有权,确保后续 schema/footer/map 失败也由统一回滚释放。
            self._parquet_files[relative_path] = parquet_file
            self._counters["parquet_file_opens"] += 1
            self._counters["footer_loads"] += 1
            schema = parquet_file.schema_arrow
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
            spans: list[tuple[int, int, int]] = []
            start = 0
            for row_group in range(parquet_file.metadata.num_row_groups):
                count = int(parquet_file.metadata.row_group(row_group).num_rows)
                spans.append((start, start + count, row_group))
                start += count
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

    def _row_group(self, data_path: str, row_group: int) -> _ArrowTable:
        """读取或复用一个有界 row-group table。"""
        self._require_owner()
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
    def _take_rows(table: _ArrowTable, rows: Sequence[int]) -> list[dict[str, object]]:
        """用 Arrow take 向量化选择 row-group 内行。"""
        arrow_module: object = importlib.import_module("pyarrow")
        if not isinstance(arrow_module, _RuntimeArrowModule):
            raise RuntimeError("pyarrow lacks the required array construction interface")
        selected = table.take(arrow_module.array(tuple(rows), type=arrow_module.int64()))
        columns = tuple(selected.column_names)
        return [
            {column: selected[column][row].as_py() for column in columns}
            for row in range(int(selected.num_rows))
        ]

    def _image(self, reference: str) -> _ImageArray:
        """按物理图片路径分组并使用有界 decoder cache。"""
        self._require_owner()
        path = contained_path(self._root, reference)
        if path in self._images:
            self._counters["image_cache_hits"] += 1
            self._images.move_to_end(path)
            return self._images[path]
        if path.suffix.lower() == ".npy":
            image: _ImageArray = np.load(path, allow_pickle=False)
        elif path.suffix.lower() in _IMAGE_SUFFIXES:
            try:
                imported_image_module: object = importlib.import_module("PIL.Image")
            except ImportError as exc:
                raise RuntimeError(
                    "LeRobot image materialization requires optional dependency pillow; "
                    "install autovla[data-lerobot]"
                ) from exc
            if not isinstance(imported_image_module, _ImageModule):
                raise RuntimeError("Pillow lacks the required image interface")
            with imported_image_module.open(path) as opened:
                image = np.asarray(opened.convert("RGB")).copy()
        else:
            raise ValueError(f"unsupported local LeRobot image suffix: {path.suffix}")
        self._images[path] = image
        self._counters["image_decodes"] += 1
        if len(self._images) > self._max_images:
            self._images.popitem(last=False)
            self._counters["image_evictions"] += 1
        return image

    def _video_container(self, path: Path) -> _VideoContainer:
        """懒加载 PyAV 容器并按路径维持有界 worker-local LRU。"""
        self._require_owner()
        if path in self._videos:
            self._counters["video_cache_hits"] += 1
            self._videos.move_to_end(path)
            return self._videos[path]
        try:
            imported_video_module: object = importlib.import_module("av")
        except ImportError as exc:
            raise RuntimeError(
                "LeRobot video materialization requires optional dependency 'av' (PyAV); "
                "install autovla[data-lerobot] (av>=16,<17)"
            ) from exc
        try:
            if not isinstance(imported_video_module, _VideoModule):
                raise RuntimeError("PyAV lacks the required container interface")
            container = imported_video_module.open(path.as_posix(), mode="r")
        except Exception as exc:
            raise LeRobotVideoDecodeError(f"cannot open LeRobot video: {path}") from exc
        self._videos[path] = container
        self._counters["video_opens"] += 1
        if len(self._videos) > self._max_videos:
            _, stale = self._videos.popitem(last=False)
            self._close_video(stale)
            self._counters["video_evictions"] += 1
        return container

    def _close_video(self, container: _VideoContainer) -> None:
        """关闭一个已从 cache 移除的容器并只计数一次。"""
        container.close()
        self._counters["video_closes"] += 1

    def _video_frame(self, reference: str, timestamp: float) -> _ImageArray:
        """后向 seek 后选择目标时刻或其后容差内的第一帧。"""
        if not np.isfinite(timestamp) or timestamp < 0.0:
            raise LeRobotVideoDecodeError("LeRobot video timestamp must be finite and non-negative")
        path = contained_path(self._root, reference)
        container = self._video_container(path)
        streams = tuple(container.streams.video)
        if len(streams) != 1:
            raise LeRobotVideoDecodeError("LeRobot video must contain exactly one video stream")
        stream = streams[0]
        if stream.time_base is None:
            raise LeRobotVideoDecodeError("LeRobot video stream has no time base")
        time_base = float(stream.time_base)
        if not np.isfinite(time_base) or time_base <= 0.0:
            raise LeRobotVideoDecodeError(
                "LeRobot video stream time base must be finite and positive"
            )
        target_units = int(timestamp / time_base)
        seek_units = max(target_units - 1, 0)
        try:
            container.seek(seek_units, stream=stream, backward=True, any_frame=False)
            for frame in container.decode(stream):
                if frame.pts is None:
                    raise LeRobotVideoDecodeError("LeRobot decoded frame has no PTS")
                frame_time = float(frame.pts) * time_base
                if not np.isfinite(frame_time):
                    raise LeRobotVideoDecodeError("LeRobot decoded frame PTS is not finite")
                if frame_time + _VIDEO_TIMESTAMP_TOLERANCE_SECONDS >= timestamp:
                    array = np.asarray(frame.to_ndarray(format="rgb24"), dtype=np.uint8)
                    return np.ascontiguousarray(array).copy()
        except LeRobotVideoDecodeError:
            raise
        except Exception as exc:
            raise LeRobotVideoDecodeError(
                f"failed to decode LeRobot video at timestamp {timestamp}: {path}"
            ) from exc
        raise LeRobotVideoDecodeError(
            f"LeRobot video reached EOF before timestamp {timestamp}: {path}"
        )

    def _materialize_media(
        self, payloads: Sequence[dict[str, object]]
    ) -> list[dict[str, _ImageArray]]:
        """按图片/视频物理路径复用 decoder 和容器缓存。"""
        output: list[dict[str, _ImageArray]] = []
        for payload in payloads:
            refs = payload.get("camera_refs", ())
            if not _is_object_sequence(refs):
                raise ValueError("LeRobot camera_refs must be a sequence")
            images: dict[str, _ImageArray] = {}
            for index, raw_reference in enumerate(refs):
                reference = require_str(raw_reference, "camera_ref")
                path = contained_path(self._root, reference)
                name = f"camera.rgb_{index}"
                if path.suffix.lower() in _VIDEO_SUFFIXES:
                    images[name] = self._video_frame(
                        reference, _coerce_float(payload.get("timestamp"), "timestamp")
                    )
                else:
                    images[name] = self._image(reference)
            output.append(images)
        return output

    def _read_records_without_media(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按 parquet row group 读取 payload 和物理来源,不触发媒体解码。"""

        self._require_owner()
        groups: dict[tuple[str, int], list[tuple[int, int, int]]] = {}
        for position, index in enumerate(indices):
            if index < 0 or index >= len(self._metadata.index):
                raise IndexError(index)
            data_path, row_group, local_row = self._row_group_map[index]
            groups.setdefault((data_path, row_group), []).append((position, local_row, index))
        output: list[dict[str, object] | None] = [None] * len(indices)
        for (data_path, row_group), requests in groups.items():
            table = self._row_group(data_path, row_group)
            raw_rows = self._take_rows(table, tuple(item[1] for item in requests))
            for (position, local_row, index), raw_row in zip(requests, raw_rows, strict=True):
                payload = _payload_from_raw_row(raw_row=raw_row, tasks=dict(self._metadata.tasks))
                output[position] = {
                    "payload": payload,
                    "physical_source": {
                        "parquet": data_path,
                        "row_group": row_group,
                        "row_in_group": local_row,
                        "global_index": index,
                    },
                }
        return _complete_records(output)

    def read_records(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按 parquet row group 和媒体文件分组,最终恢复请求顺序。"""

        output = self._read_records_without_media(indices)
        ordered_payloads = [
            _require_string_mapping(record.get("payload"), "LeRobot record payload")
            for record in output
        ]
        media = self._materialize_media(ordered_payloads)
        for position, images in enumerate(media):
            output[position]["images"] = images
        return output

    def read_index_fields(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按 row group 向量化加载精确 episode/frame/timestamp 索引字段。"""
        self._require_owner()
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
        return _complete_records(output)

    def read_payloads(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """兼容入口只读取 payload,避免 benchmark 触发媒体解码副作用。"""

        return [
            _require_string_mapping(record.get("payload"), "LeRobot record payload")
            for record in self._read_records_without_media(indices)
        ]

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
        if self._closed:
            return
        for container in self._videos.values():
            self._close_video(container)
        self._videos.clear()
        self._images.clear()
        self._row_groups.clear()
        self._row_group_map.clear()
        for parquet_file in self._parquet_files.values():
            parquet_file.close()
            self._counters["parquet_file_closes"] += 1
        self._parquet_files.clear()
        self._closed = True


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
    if not _is_object_sequence(value):
        raise ValueError(f"{field_name} must be numeric sequence")
    values: list[float] = []
    for item in value:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            raise ValueError(f"{field_name} must be numeric sequence")
        values.append(float(item))
    return values


def _coerce_bool_list(value: object, field_name: str) -> list[bool]:
    """把 parquet 掩码列严格收窄为 bool list。"""
    if not _is_object_sequence(value):
        raise ValueError(f"{field_name} must be bool sequence")
    values: list[bool] = []
    for item in value:
        if type(item) is not bool:
            raise TypeError(f"{field_name} must be bool sequence")
        values.append(item)
    return values


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


__all__ = [
    "LeRobotGroupedReader",
    "LeRobotVideoDecodeError",
    "read_lerobot_v3_local_batches",
]
