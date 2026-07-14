"""AC4 生产数据后端的本地确定性行为测试。"""

from __future__ import annotations

import importlib.util
import io
import json
import pickle
import tarfile
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, TypeGuard, runtime_checkable

import numpy as np
import pytest
from numpy.typing import NDArray

import autovla.data.backends.lerobot as lerobot_backend_module
import autovla.data.backends.webdataset as webdataset_backend_module
import autovla.dataloader.stores.lerobot_v3_reader as lerobot_reader_module
from autovla.config.schema import (
    DataConfig,
    DataLoaderConfig,
    DatasetConfig,
    TemporalQueryConfig,
)
from autovla.core.types.training import TrainingBatch
from autovla.data.backends.lerobot import LeRobotLocalBackend
from autovla.data.backends.robodm import RoboDMContainerBackend
from autovla.data.backends.webdataset import WebDatasetBackend, WebDatasetStreamingSource
from autovla.data.contracts import (
    DataSchemaMismatchError,
    PartitionPlan,
    StreamPartitionState,
    TemporalQuery,
    WorkerContext,
    derive_worker_seed,
    stable_fingerprint,
)
from autovla.data.datasets.local_lerobot import inspect_local_lerobot
from autovla.data.module import DataModule
from autovla.data.types import DataStage, TrainingSample
from autovla.dataloader.stores.robodm_reader import RoboDMGroupedReader


@runtime_checkable
class _VideoFrameReader(Protocol):
    """描述 LeRobot 私有视频解码入口的测试形状。"""

    def __call__(self, media_path: str, timestamp: float) -> NDArray[np.uint8]:
        """读取一个 owned RGB 帧。"""
        ...


@runtime_checkable
class _SampleReader(Protocol):
    """描述 map 数据源读取入口。"""

    def __call__(self, index: int) -> TrainingSample:
        """读取一个训练样本。"""
        ...


@runtime_checkable
class _Closable(Protocol):
    """描述迭代器和 reader 的关闭入口。"""

    def close(self) -> None:
        """关闭动态资源。"""
        ...


@runtime_checkable
class _EpochPlanner(Protocol):
    """描述 loader 的 epoch 规划入口。"""

    def __call__(self, epoch: int) -> PartitionPlan:
        """返回确定性采样计划。"""
        ...


@runtime_checkable
class _BatchObserver(Protocol):
    """描述 loader 的批次提交入口。"""

    def __call__(self, batch: TrainingBatch) -> None:
        """提交一个训练批次的恢复状态。"""
        ...


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    """写入仅位于 pytest tmp_path 的 tiny JSONL。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def _tar_member(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    """向 tiny fixture tar 写入确定性成员。"""
    info = tarfile.TarInfo(name)
    info.size = len(payload)
    archive.addfile(info, io.BytesIO(payload))


def _npy_bytes(value: object) -> bytes:
    """把 tiny 数组编码为无 pickle NPY bytes。"""
    buffer = io.BytesIO()
    np.save(buffer, np.asarray(value), allow_pickle=False)
    return buffer.getvalue()


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """收窄动态 fixture 映射。"""
    return isinstance(value, Mapping)


def _is_string_dict(value: object) -> TypeGuard[dict[str, object]]:
    """收窄需要原位修改的字符串键 fixture 字典。"""
    return _is_object_dict(value) and all(isinstance(key, str) for key in value)


def _is_object_dict(value: object) -> TypeGuard[dict[object, object]]:
    """收窄动态 fixture 字典。"""
    return isinstance(value, dict)


def _is_object_sequence(value: object) -> TypeGuard[list[object] | tuple[object, ...]]:
    """收窄动态 fixture 列表或元组。"""
    return isinstance(value, (list, tuple))


def _string_mapping(value: object) -> Mapping[str, object]:
    """校验并复制字符串键映射。"""
    if not _is_object_mapping(value):
        raise TypeError("expected fixture mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise TypeError("fixture mapping keys must be strings")
        result[key] = item
    return result


def _string_dict(value: object) -> dict[str, object]:
    """校验并原位返回字符串键字典。"""
    if not _is_string_dict(value):
        raise TypeError("expected mutable fixture dictionary")
    return value


def _object_sequence(value: object) -> list[object] | tuple[object, ...]:
    """校验动态 fixture 列表或元组。"""
    if not _is_object_sequence(value):
        raise TypeError("expected fixture sequence")
    return value


def _strict_int(value: object, name: str) -> int:
    """读取排除 bool 的 fixture 整数。"""
    if not isinstance(value, int) or isinstance(value, bool):
        raise TypeError(f"{name} must be an integer")
    return value


def _optional_string(value: object, name: str) -> str | None:
    """读取可空 fixture 文本。"""
    if value is not None and not isinstance(value, str):
        raise TypeError(f"{name} must be text or null")
    return value


def _string_int_mapping(value: object, name: str) -> Mapping[str, int]:
    """读取字符串到整数的计数映射。"""
    mapping = _string_mapping(value)
    return {key: _strict_int(item, f"{name}.{key}") for key, item in mapping.items()}


def _read_sample(source: object, index: int) -> TrainingSample:
    """通过运行时校验的 map 数据源读取样本。"""
    reader: object = getattr(source, "read", None)
    if not isinstance(reader, _SampleReader):
        raise TypeError("map source read must be callable")
    return reader(index)


def _video_frame(
    reader: lerobot_reader_module.LeRobotGroupedReader,
    media_path: str,
    timestamp: float,
) -> NDArray[np.uint8]:
    """通过运行时校验的视频入口读取 RGB 帧。"""
    operation: object = getattr(reader, "_video_frame", None)
    if not isinstance(operation, _VideoFrameReader):
        raise TypeError("LeRobot video frame reader must be callable")
    return operation(media_path, timestamp)


def _close_dynamic(value: object) -> None:
    """关闭实现了显式 close 的动态迭代器。"""
    if not isinstance(value, _Closable):
        raise TypeError("iterator must expose close")
    value.close()


def _private_mapping(owner: object, name: str) -> Mapping[str, object]:
    """读取白盒测试所需的私有映射状态。"""
    return _string_mapping(getattr(owner, name, None))


def _is_object_pair(value: object) -> TypeGuard[tuple[object, object]]:
    """收窄 loader 分配二元组。"""
    return _is_object_tuple(value) and len(value) == 2


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """收窄 loader 动态元组。"""
    return isinstance(value, tuple)


def _stream_units_for_source(values: Sequence[object], *, source_id: int) -> tuple[str, ...]:
    """从混合分配项中提取指定来源的流式单元。"""
    result: list[str] = []
    for value in values:
        if not _is_object_pair(value):
            raise TypeError("stream assignment must be a pair")
        assigned_source, unit = value
        if not isinstance(assigned_source, int) or isinstance(assigned_source, bool):
            raise TypeError("stream source ID must be an integer")
        if not isinstance(unit, str):
            raise TypeError("stream assignment unit must be text")
        if assigned_source == source_id:
            result.append(unit)
    return tuple(result)


def _write_tiny_video(path: Path, values: tuple[int, ...] = (0, 64, 128, 255)) -> None:
    """用 live PyAV 在 pytest tmp_path 写入确定性 rawvideo AVI。"""
    av = pytest.importorskip("av")
    path.parent.mkdir(parents=True, exist_ok=True)
    container = av.open(path.as_posix(), mode="w", format="avi")
    try:
        stream = container.add_stream("rawvideo", rate=10)
        stream.width = 4
        stream.height = 4
        stream.pix_fmt = "rgb24"
        stream.time_base = Fraction(1, 10)
        for index, value in enumerate(values):
            frame = av.VideoFrame.from_ndarray(
                np.full((4, 4, 3), value, dtype=np.uint8), format="rgb24"
            )
            frame.pts = index
            frame.time_base = Fraction(1, 10)
            for packet in stream.encode(frame):
                container.mux(packet)
        for packet in stream.encode():
            container.mux(packet)
    finally:
        container.close()


def _payload(sample_id: str, *, frame: int = 0) -> dict[str, object]:
    """构造规范转换所需的最小真实样本 payload。"""
    return {
        "action": [[float(frame), float(frame + 1)]],
        "action_mask": [[True, True]],
        "episode_id": "episode-0",
        "frame_index": frame,
        "language": "move",
        "sample_id": sample_id,
        "state": [float(frame), 1.0],
        "timestamp": frame / 10.0,
    }


class _FakeScalar:
    def __init__(self, value: object) -> None:
        self._value = value

    def as_py(self) -> object:
        """模拟 Arrow scalar 转 Python。"""
        return self._value


class _FakeColumn:
    def __init__(self, values: list[object]) -> None:
        self._values = values

    def __getitem__(self, index: int) -> _FakeScalar:
        return _FakeScalar(self._values[index])


class _FakeTable:
    def __init__(self, rows: list[dict[str, object]], owner: "_FakeArrowRuntime") -> None:
        self._rows = rows
        self._owner = owner
        self.column_names = list(rows[0]) if rows else []
        self.num_rows = len(rows)

    def take(self, indices: tuple[int, ...]) -> "_FakeTable":
        """记录一次向量化 take 并返回所选行。"""
        self._owner.take_batches.append(indices)
        return _FakeTable([self._rows[index] for index in indices], self._owner)

    def __getitem__(self, name: str) -> _FakeColumn:
        return _FakeColumn([row[name] for row in self._rows])


class _FakeRowGroupMeta:
    def __init__(self, count: int) -> None:
        self.num_rows = count


class _FakeFileMeta:
    def __init__(self, counts: tuple[int, ...]) -> None:
        self._counts = counts
        self.num_row_groups = len(counts)

    def row_group(self, index: int) -> _FakeRowGroupMeta:
        return _FakeRowGroupMeta(self._counts[index])


class _FakeParquetFile:
    def __init__(
        self,
        rows: list[dict[str, object]],
        owner: "_FakeArrowRuntime",
        *,
        schema_names: tuple[str, ...] | None = None,
    ) -> None:
        self._groups = [rows[index : index + 2] for index in range(0, len(rows), 2)]
        self._owner = owner
        self.schema_arrow = None if schema_names is None else SimpleNamespace(names=schema_names)
        self.metadata = _FakeFileMeta(tuple(len(group) for group in self._groups))
        self.close_count = 0

    def read_row_group(self, index: int) -> _FakeTable:
        return _FakeTable(self._groups[index], self._owner)

    def close(self) -> None:
        """记录 handle 的精确关闭次数。"""
        self.close_count += 1


class _FakeArrowRuntime:
    def __init__(
        self,
        rows_by_path: dict[str, list[dict[str, object]]],
        *,
        schema_names: tuple[str, ...] | None = None,
    ) -> None:
        self.rows_by_path = rows_by_path
        self.schema_names = schema_names
        self.take_batches: list[tuple[int, ...]] = []
        self.opened_files: list[_FakeParquetFile] = []

    def parquet_file(self, path: Path) -> _FakeParquetFile:
        opened = _FakeParquetFile(
            self.rows_by_path[path.resolve().as_posix()],
            self,
            schema_names=self.schema_names,
        )
        self.opened_files.append(opened)
        return opened

    @staticmethod
    def array(values: tuple[int, ...], **kwargs: object) -> tuple[int, ...]:
        del kwargs
        return values

    @staticmethod
    def int64() -> str:
        return "int64"


def _install_fake_arrow(monkeypatch: pytest.MonkeyPatch, runtime: _FakeArrowRuntime) -> None:
    """为 package-independent 语义测试安装最小 Arrow 公共边界。"""
    original = lerobot_reader_module.importlib.import_module

    def fake_import(name: str) -> object:
        if name == "pyarrow.parquet":
            return SimpleNamespace(ParquetFile=runtime.parquet_file)
        if name == "pyarrow":
            return SimpleNamespace(array=runtime.array, int64=runtime.int64)
        return original(name)

    monkeypatch.setattr(lerobot_reader_module.importlib, "import_module", fake_import)


def _lerobot_fixture(
    root: Path,
    *,
    media_reference: str = "media/frame.npy",
    unique_anchor_content: bool = False,
) -> tuple[DatasetConfig, dict[str, list[dict[str, object]]]]:
    """构造两 episode、六 frame 的本地 v3 subset 和 fake parquet 行。"""
    data_path = root / "data/data.parquet"
    data_path.parent.mkdir(parents=True)
    data_path.write_bytes(b"PAR1-tiny-footer-identity")
    image_path = root / "media/frame.npy"
    image_path.parent.mkdir(parents=True)
    np.save(image_path, np.arange(12, dtype=np.uint8).reshape(2, 2, 3), allow_pickle=False)
    info = {
        "codebase_version": "v3.0",
        "fps": 10,
        "total_episodes": 2,
        "total_frames": 6,
        "features": {
            "observation.state": {"dtype": "float32", "shape": [2]},
            "action": {"dtype": "float32", "shape": [2]},
            "observation.images.head_rgb": {"dtype": "image", "shape": [2, 2, 3]},
        },
    }
    (root / "meta").mkdir(parents=True)
    (root / "meta/info.json").write_text(json.dumps(info), encoding="utf-8")
    (root / "meta/stats.json").write_text(
        json.dumps(
            {
                "action": {"mean": [0.0, 0.0]},
                "observation.state": {"mean": [0.0, 0.0]},
            }
        ),
        encoding="utf-8",
    )
    _write_jsonl(root / "meta/tasks.jsonl", [{"task_index": 0, "task": "move"}])
    _write_jsonl(
        root / "meta/episodes.jsonl",
        [
            {"episode_index": 0, "length": 3, "tasks": ["move"]},
            {"episode_index": 1, "length": 3, "tasks": ["move"]},
        ],
    )
    index_rows: list[dict[str, object]] = []
    parquet_rows: list[dict[str, object]] = []
    for global_index in range(6):
        episode = global_index // 3
        frame = global_index % 3
        row_media_reference = media_reference
        if unique_anchor_content:
            row_media_reference = f"media/frame-{global_index}.npy"
            np.save(
                root / row_media_reference,
                np.full((2, 2, 3), global_index, dtype=np.uint8),
                allow_pickle=False,
            )
        index_rows.append(
            {
                "episode_index": episode,
                "frame_index": frame,
                "row_in_episode": frame,
                "sample_id": f"sample-{global_index:09d}",
                "timestamp": frame / 10.0,
                "data_path": "data/data.parquet",
            }
        )
        parquet_rows.append(
            {
                "observation.images.head_rgb": row_media_reference,
                "observation.state": [float(global_index), 1.0],
                "action": [float(global_index), float(global_index + 1)],
                "action_mask": [True, global_index % 2 == 0],
                "timestamp": frame / 10.0,
                "frame_index": frame,
                "episode_index": episode,
                "index": global_index,
                "task_index": 0,
                "annotation.human.action.task_description": (
                    f"move-{global_index}" if unique_anchor_content else "move"
                ),
            }
        )
    _write_jsonl(root / "sample_index.jsonl", index_rows)
    config = DatasetConfig(
        name="tiny-lerobot",
        backend="lerobot_local",
        root=str(root),
        image_keys=("camera.rgb_0",),
    )
    return config, {data_path.resolve().as_posix(): parquet_rows}


def test_lerobot_loads_metadata_once_groups_rows_and_is_pickle_safe(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 metadata-once、row-group take、顺序恢复、图片 cache 和 spawn pickle。"""
    config, rows = _lerobot_fixture(tmp_path / "lerobot")
    runtime = _FakeArrowRuntime(rows)
    _install_fake_arrow(monkeypatch, runtime)
    calls = 0
    original = lerobot_backend_module.inspect_local_lerobot

    def counted(root: str | Path) -> object:
        nonlocal calls
        calls += 1
        return original(root)

    monkeypatch.setattr(lerobot_backend_module, "inspect_local_lerobot", counted)
    backend = LeRobotLocalBackend()
    first_spec = backend.describe_source(config, DataStage.TRAIN)
    source = backend.open_source(config, DataStage.TRAIN, WorkerContext())
    samples = source.read_many((4, 1, 5))

    assert calls == 1
    assert [sample.sample_source["anchor_index"] for sample in samples] == [4, 1, 5]
    assert any(len(batch) == 2 for batch in runtime.take_batches)
    counters = _string_mapping(source.state_dict()["cache_counters"])
    assert counters["row_group_reads"] == 2
    assert counters["image_decodes"] == 1
    assert counters["image_cache_hits"] == 2
    reader: object = getattr(source, "_reader", None)
    if not isinstance(reader, lerobot_reader_module.LeRobotGroupedReader):
        raise TypeError("LeRobot source must own a grouped reader")
    restored_reader: object = pickle.loads(pickle.dumps(reader))
    if not isinstance(restored_reader, lerobot_reader_module.LeRobotGroupedReader):
        raise TypeError("pickled LeRobot reader changed type")
    assert not _private_mapping(restored_reader, "_row_groups")
    assert not _private_mapping(restored_reader, "_images")
    assert not _private_mapping(restored_reader, "_videos")
    restored_reader.close()
    restored: object = pickle.loads(pickle.dumps(source))
    assert getattr(restored, "spec", None) == first_spec
    assert getattr(restored, "_reader", None) is None
    source.close()


def test_lerobot_schema_failure_closes_new_parquet_handle_and_clears_state(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 schema 校验失败会精确关闭新 handle 并清空部分构造状态。"""
    root = tmp_path / "lerobot"
    _, rows = _lerobot_fixture(root)
    runtime = _FakeArrowRuntime(rows, schema_names=("action",))
    _install_fake_arrow(monkeypatch, runtime)
    rolled_back: dict[str, object] = {}
    original_close = lerobot_reader_module.LeRobotGroupedReader.close

    def observed_close(reader: lerobot_reader_module.LeRobotGroupedReader) -> None:
        original_close(reader)
        rolled_back["parquet_files"] = dict(_private_mapping(reader, "_parquet_files"))
        rolled_back["row_group_map"] = dict(_private_mapping(reader, "_row_group_map"))

    monkeypatch.setattr(lerobot_reader_module.LeRobotGroupedReader, "close", observed_close)
    with pytest.raises(ValueError, match="schema lacks required columns"):
        lerobot_reader_module.LeRobotGroupedReader(inspect_local_lerobot(root))

    assert len(runtime.opened_files) == 1
    assert runtime.opened_files[0].close_count == 1
    assert rolled_back == {"parquet_files": {}, "row_group_map": {}}


def test_lerobot_video_has_precise_optional_pyav_boundary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证本地视频仅在实际请求时要求有界 PyAV optional extra。"""
    root = tmp_path / "lerobot"
    config, rows = _lerobot_fixture(root, media_reference="media/video.mp4")
    (root / "media/video.mp4").write_bytes(b"local-video-placeholder")
    runtime = _FakeArrowRuntime(rows)
    _install_fake_arrow(monkeypatch, runtime)
    delegated = lerobot_reader_module.importlib.import_module

    def missing_av(name: str) -> object:
        if name == "av":
            raise ImportError("PyAV intentionally absent in semantic test")
        return delegated(name)

    monkeypatch.setattr(lerobot_reader_module.importlib, "import_module", missing_av)
    source = LeRobotLocalBackend().open_source(config, DataStage.TRAIN, WorkerContext())
    with pytest.raises(RuntimeError, match=r"av>=16,<17"):
        source.read(0)
    source.close()


def test_lerobot_live_pyav_selects_exact_owned_rgb_frames_and_reuses_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证真实 PyAV seek、精确帧选择、owned RGB 和容器复用。"""
    root = tmp_path / "lerobot"
    _, rows = _lerobot_fixture(root, media_reference="media/video.avi")
    _write_tiny_video(root / "media/video.avi")
    runtime = _FakeArrowRuntime(rows)
    _install_fake_arrow(monkeypatch, runtime)
    reader = lerobot_reader_module.LeRobotGroupedReader(inspect_local_lerobot(root))
    arrays = [_video_frame(reader, "media/video.avi", index / 10.0) for index in range(4)]

    assert [int(array[0, 0, 0]) for array in arrays] == [0, 64, 128, 255]
    assert all(array.dtype == np.uint8 and array.flags.c_contiguous for array in arrays)
    assert all(array.flags.owndata for array in arrays)
    assert reader.counters["video_opens"] == 1
    assert reader.counters["video_cache_hits"] == 3
    reader.close()
    reader.close()
    assert reader.counters["video_closes"] == 1


def test_lerobot_live_pyav_lru_eof_corruption_and_process_ownership(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证视频 LRU close、typed EOF/损坏和跨进程 fail-closed。"""
    root = tmp_path / "lerobot"
    _, rows = _lerobot_fixture(root, media_reference="media/first.avi")
    _write_tiny_video(root / "media/first.avi")
    _write_tiny_video(root / "media/second.avi", (1, 2, 3, 4))
    (root / "media/corrupt.avi").write_bytes(b"not-a-video")
    runtime = _FakeArrowRuntime(rows)
    _install_fake_arrow(monkeypatch, runtime)
    reader = lerobot_reader_module.LeRobotGroupedReader(inspect_local_lerobot(root), max_videos=1)

    _video_frame(reader, "media/first.avi", 0.0)
    _video_frame(reader, "media/second.avi", 0.0)
    assert reader.counters["video_evictions"] == 1
    assert reader.counters["video_closes"] == 1
    with pytest.raises(lerobot_reader_module.LeRobotVideoDecodeError, match="EOF"):
        _video_frame(reader, "media/second.avi", 1.0)
    with pytest.raises(lerobot_reader_module.LeRobotVideoDecodeError, match="cannot open"):
        _video_frame(reader, "media/corrupt.avi", 0.0)
    monkeypatch.setattr(lerobot_reader_module.os, "getpid", lambda: reader.owner_pid + 1)
    with pytest.raises(RuntimeError, match="across processes"):
        reader.read_records((0,))
    monkeypatch.undo()
    reader.close()
    assert reader.counters["video_opens"] == reader.counters["video_closes"]


def test_lerobot_temporal_query_enforces_episode_boundary_and_separate_mask(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 pad 时间窗口不跨 episode 且 temporal mask 不改写 action mask。"""
    config, rows = _lerobot_fixture(tmp_path / "lerobot")
    _install_fake_arrow(monkeypatch, _FakeArrowRuntime(rows))
    query = TemporalQuery(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        boundary_policy="pad",
        action_horizon=3,
    )
    source = LeRobotLocalBackend(temporal_query=query).open_source(
        config, DataStage.TRAIN, WorkerContext()
    )
    sample = source.read(0)

    np.testing.assert_array_equal(
        sample.metadata["temporal_query_mask"], np.asarray([False, True, True])
    )
    assert sample.metadata["temporal_global_indices"] == (0, 0, 1)
    assert sample.actions.shape == (3, 2)
    assert sample.action_mask.shape == (3, 2)
    assert bool(sample.action_mask[0, 1]) is True
    assert sample.sample_source["anchor_episode_index"] == 0
    assert sample.sample_source["anchor_frame_index"] == 0
    assert sample.sample_source["anchor_timestamp"] == 0.0
    temporal_physical = _object_sequence(sample.sample_source["temporal_physical"])
    assert all(
        _string_mapping(item)["parquet"] == "data/data.parquet" for item in temporal_physical
    )
    source.close()


def test_lerobot_middle_anchor_is_independent_from_negative_window_element(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 requested anchor 不会被第一个负 offset 的物理记录替换。"""
    config, rows = _lerobot_fixture(
        tmp_path / "lerobot",
        unique_anchor_content=True,
    )
    _install_fake_arrow(monkeypatch, _FakeArrowRuntime(rows))
    query = TemporalQuery(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        anchor_semantics="frame",
        boundary_policy="error",
        action_horizon=3,
    )
    source = LeRobotLocalBackend(temporal_query=query).open_source(
        config, DataStage.TRAIN, WorkerContext()
    )
    sample = source.read(1)

    assert sample.sample_source["sample_id"] == "sample-000000001"
    assert sample.sample_source["anchor_index"] == 1
    assert sample.sample_source["anchor_semantics"] == "frame"
    assert sample.sample_source["anchor_frame_index"] == 1
    assert _string_mapping(sample.sample_source["physical"])["global_index"] == 1
    temporal_physical = _object_sequence(sample.sample_source["temporal_physical"])
    assert _string_mapping(temporal_physical[0])["global_index"] == 0
    assert sample.language == "move-1"
    np.testing.assert_array_equal(sample.state, [1.0, 1.0])
    np.testing.assert_array_equal(sample.timestamps, [0.1])
    np.testing.assert_array_equal(
        sample.images["camera.rgb_0"],
        np.full((2, 2, 3), 1, dtype=np.uint8),
    )
    np.testing.assert_array_equal(sample.actions[0], [0.0, 1.0])
    assert sample.metadata["temporal_global_indices"] == (0, 1, 2)
    source.close()


def test_registry_data_module_source_factory_transports_lerobot_query(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证完整规范链把配置查询送入 LeRobot materialization 和状态身份。"""
    config, rows = _lerobot_fixture(tmp_path / "lerobot", unique_anchor_content=True)
    _install_fake_arrow(monkeypatch, _FakeArrowRuntime(rows))
    query_config = TemporalQueryConfig(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        anchor_semantics="frame",
        boundary_policy="error",
        action_horizon=3,
    )
    configured = replace(config, temporal_query=query_config)
    module = DataModule(DataConfig(datasets=(configured,)))
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    factory = loader.source_factories[0]
    source = factory.initialize(WorkerContext())
    sample = _read_sample(source, 1)
    state = loader.state_dict()
    canonical_query = TemporalQuery(
        feature_key="action",
        feature_family="action",
        frame_offsets=(-1, 0, 1),
        anchor_semantics="frame",
        boundary_policy="error",
        action_horizon=3,
    )

    assert getattr(source, "_temporal_query", None) == canonical_query
    query_fingerprint = source.spec.compatibility_metadata["temporal_query_fingerprint"]
    assert query_fingerprint == query_config.fingerprint
    assert query_fingerprint == canonical_query.fingerprint
    assert sample.sample_source["sample_id"] == "sample-000000001"
    assert sample.metadata["temporal_query_fingerprint"] == query_config.fingerprint
    assert state["temporal_query_state"] == {
        "sources": [
            {
                "dataset_key": "tiny-lerobot",
                "query_fingerprint": query_config.fingerprint,
                "query": query_config.to_dict(),
            }
        ]
    }
    assert (
        loader.validate_state(state).temporal_query_fingerprint
        == state["temporal_query_fingerprint"]
    )
    loader.load_state_dict(state)
    factory.close()
    module.close()


def test_lerobot_temporal_error_clip_and_timestamp_delta(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 error/clip 和 timestamp delta 使用同 episode 映射。"""
    config, rows = _lerobot_fixture(tmp_path / "lerobot")
    _install_fake_arrow(monkeypatch, _FakeArrowRuntime(rows))
    error_source = LeRobotLocalBackend(
        temporal_query=TemporalQuery(
            feature_key="action",
            feature_family="action",
            frame_offsets=(-1,),
            boundary_policy="error",
        )
    ).open_source(config, DataStage.TRAIN, WorkerContext())
    with pytest.raises(IndexError, match="episode boundary"):
        error_source.read(0)
    error_source.close()

    clip_source = LeRobotLocalBackend(
        temporal_query=TemporalQuery(
            feature_key="action",
            feature_family="action",
            frame_offsets=(-1,),
            timestamp_deltas=(0.1,),
            boundary_policy="clip",
            tolerance=1e-6,
            action_horizon=2,
        )
    ).open_source(config, DataStage.TRAIN, WorkerContext())
    sample = clip_source.read(0)
    assert sample.metadata["temporal_global_indices"] == (0, 1)
    np.testing.assert_array_equal(sample.metadata["temporal_query_mask"], [True, True])
    clip_source.close()


def test_lerobot_root_contains_parquet_and_media_paths(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 data 和媒体引用都不能逃逸本地数据根。"""
    config, rows = _lerobot_fixture(tmp_path / "lerobot")
    index_path = Path(config.root) / "sample_index.jsonl"
    index_rows = [_string_dict(json.loads(line)) for line in index_path.read_text().splitlines()]
    index_rows[0]["data_path"] = "../escape.parquet"
    (tmp_path / "escape.parquet").write_bytes(b"escape")
    _write_jsonl(index_path, index_rows)
    with pytest.raises(ValueError, match="escapes dataset root"):
        inspect_local_lerobot(config.root)

    config, rows = _lerobot_fixture(tmp_path / "media-lerobot", media_reference="../outside.npy")
    np.save(tmp_path / "outside.npy", np.zeros((1, 1, 3), dtype=np.uint8))
    _install_fake_arrow(monkeypatch, _FakeArrowRuntime(rows))
    source = LeRobotLocalBackend().open_source(config, DataStage.TRAIN, WorkerContext())
    with pytest.raises(ValueError, match="escapes dataset root"):
        source.read(0)
    source.close()


def test_lerobot_fingerprint_changes_with_metadata_or_parquet_identity(tmp_path: Path) -> None:
    """验证同路径同计数内容漂移会改变 source fingerprint。"""
    config, _ = _lerobot_fixture(tmp_path / "lerobot")
    first = LeRobotLocalBackend().describe_source(config, DataStage.TRAIN).source_fingerprint
    data_path = Path(config.root) / "data/data.parquet"
    data_path.write_bytes(b"PAR1-mutated-same-path")
    second = LeRobotLocalBackend().describe_source(config, DataStage.TRAIN).source_fingerprint
    assert first != second


class _FakePipeline:
    def __init__(self, samples: list[object], owner: "_FakeWebDataset") -> None:
        self._samples = samples
        self._owner = owner
        self.closed = False

    def __iter__(self) -> Iterator[object]:
        for sample in self._samples:
            if isinstance(sample, BaseException):
                raise sample
            yield sample

    def close(self) -> None:
        """记录 pipeline 显式关闭。"""
        if not self.closed:
            self.closed = True
            self._owner.close_count += 1


class _FakeWebDataset:
    __version__ = "1.0.2"

    def __init__(self, samples_by_shard: dict[str, list[object]]) -> None:
        self.samples_by_shard = samples_by_shard
        self.close_count = 0
        self.opens: dict[str, int] = {}

    def WebDataset(self, shards: list[str], **kwargs: object) -> _FakePipeline:
        """模拟 WebDataset 公共构造器并保留 splitter/handler 参数。"""
        assert kwargs["shardshuffle"] is False
        assert callable(kwargs["nodesplitter"])
        assert callable(kwargs["workersplitter"])
        assert callable(kwargs["handler"])
        shard = shards[0]
        self.opens[shard] = self.opens.get(shard, 0) + 1
        samples = list(self.samples_by_shard[shard])
        if samples and isinstance(samples[0], OSError) and self.opens[shard] > 1:
            samples = samples[1:]
        return _FakePipeline(samples, self)


def _webdataset_fixture(
    root: Path,
    samples_by_name: dict[str, list[dict[str, object]]],
    *,
    mode: str = "finite_epoch",
    nominal: int | None = None,
) -> tuple[DatasetConfig, dict[str, list[object]]]:
    """构造本地 shard/index 身份和 fake pipeline payload。"""
    (root / "shards").mkdir(parents=True)
    index_rows: list[dict[str, object]] = []
    samples_by_path: dict[str, list[object]] = {}
    for shard_name, payloads in sorted(samples_by_name.items()):
        path = root / "shards" / shard_name
        path.write_bytes(f"tar-identity-{shard_name}".encode())
        samples_by_path[path.resolve().as_posix()] = []
        for payload in payloads:
            key = str(payload.get("sample_id", "malformed"))
            index_rows.append({"shard": f"shards/{shard_name}", "key": key})
            samples_by_path[path.resolve().as_posix()].append(
                {
                    "__key__": key,
                    "payload.json": json.dumps(payload).encode(),
                    "camera_0.npy": _npy_bytes(np.zeros((2, 2, 3), dtype=np.uint8)),
                }
            )
    _write_jsonl(root / "sample_index.jsonl", index_rows)
    total = sum(len(values) for values in samples_by_name.values())
    config = DatasetConfig(
        name="tiny-wds",
        backend="webdataset",
        root=str(root),
        image_keys=("camera.rgb_0",),
        access_mode="streaming",
        stream_mode=mode,
        nominal_epoch_size=nominal or total,
    )
    return config, samples_by_path


def _stream_state(
    units: tuple[str, ...],
    *,
    source_state: dict[str, object] | None = None,
    observed: dict[str, object] | None = None,
    seed: int = 17,
) -> StreamPartitionState:
    """构造或从后端 observed state 恢复 canonical stream state。"""
    observed = observed or {}
    current_shard = _optional_string(observed.get("current_shard"), "current_shard")
    shard_index = _strict_int(observed.get("shard_index", 0), "shard_index")
    consumed_offset = _strict_int(
        observed.get("consumed_sample_offset", 0),
        "consumed_sample_offset",
    )
    handler_counts = _string_int_mapping(observed.get("handler_counts", {}), "handler_counts")
    return StreamPartitionState(
        worker_id=0,
        epoch=0,
        assignment_owner="autovla_loader",
        assigned_units=units,
        upstream_partitioning_disabled=True,
        assignment_digest="assignment",
        shard_order_digest="order",
        current_shard=current_shard,
        shard_index=shard_index,
        consumed_sample_offset=consumed_offset,
        shard_rng_state={"seed": 11, "shuffle": False},
        sample_rng_state={"seed": seed},
        handler_counts=handler_counts,
        source_state=source_state or observed,
    )


def _install_fake_webdataset(monkeypatch: pytest.MonkeyPatch, fake: _FakeWebDataset) -> None:
    """替换延迟依赖边界,不伪造已安装包证据。"""
    monkeypatch.setattr(webdataset_backend_module, "_webdataset_module", lambda: fake)


def test_webdataset_finite_resume_state_identity_close_and_fingerprint(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证有限流无重复、下一 cursor、断点重放、显式关闭和内容指纹。"""
    root = tmp_path / "webdataset"
    config, samples = _webdataset_fixture(
        root,
        {
            "a.tar": [_payload("a0"), _payload("a1", frame=1)],
            "b.tar": [_payload("b0")],
        },
    )
    fake = _FakeWebDataset(samples)
    _install_fake_webdataset(monkeypatch, fake)
    backend = WebDatasetBackend()
    spec = backend.describe_source(config, DataStage.TRAIN)
    context = WorkerContext()
    source = WebDatasetStreamingSource(config, spec)
    source.initialize_worker(context)
    iterator = source.iter_samples(context, _stream_state(spec.partition_units))
    first = next(iterator)
    observed = dict(source.state_dict())

    assert first.sample_source["sample_id"] == "a0"
    assert observed["delivered_sample_identity"] == "a0"
    assert observed["next_unread_identity"] == "a1"
    assert observed["next_cursor"] == {"shard_index": 0, "sample_offset": 1}
    assert _string_mapping(first.sample_source["physical"])["key"] == "a0"
    _close_dynamic(iterator)
    source.close()
    resumed = WebDatasetStreamingSource(config, spec)
    resumed.initialize_worker(context)
    remaining = list(
        resumed.iter_samples(
            context,
            StreamPartitionState.from_dict(
                _stream_state(spec.partition_units, observed=observed).to_dict()
            ),
        )
    )
    assert [sample.sample_source["sample_id"] for sample in remaining] == ["a1", "b0"]
    resumed.close()
    assert fake.close_count >= 3

    first_fingerprint = spec.source_fingerprint
    (root / "shards/a.tar").write_bytes(b"changed-same-path-and-count")
    second_fingerprint = backend.describe_source(config, DataStage.TRAIN).source_fingerprint
    assert first_fingerprint != second_fingerprint


def test_webdataset_resampled_is_deterministic_resumable_and_train_only(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证显式有放回 RNG、nominal 长度、精确恢复和验证阶段拒绝。"""
    config, samples = _webdataset_fixture(
        tmp_path / "webdataset",
        {"a.tar": [_payload("a0")], "b.tar": [_payload("b0")]},
        mode="resampled",
        nominal=5,
    )
    fake = _FakeWebDataset(samples)
    _install_fake_webdataset(monkeypatch, fake)
    backend = WebDatasetBackend()
    spec = backend.describe_source(config, DataStage.TRAIN)
    context = WorkerContext()

    def full_run() -> list[str]:
        source = WebDatasetStreamingSource(config, spec)
        source.initialize_worker(context)
        result = [
            str(sample.sample_source["sample_id"])
            for sample in source.iter_samples(context, _stream_state(spec.partition_units))
        ]
        source.close()
        return result

    expected = full_run()
    assert len(expected) == 5
    assert full_run() == expected
    source = WebDatasetStreamingSource(config, spec)
    source.initialize_worker(context)
    iterator = source.iter_samples(context, _stream_state(spec.partition_units))
    prefix = [str(next(iterator).sample_source["sample_id"]) for _ in range(2)]
    observed = dict(source.state_dict())
    _close_dynamic(iterator)
    source.close()
    resumed = WebDatasetStreamingSource(config, spec)
    resumed.initialize_worker(context)
    suffix = [
        str(sample.sample_source["sample_id"])
        for sample in resumed.iter_samples(
            context,
            StreamPartitionState.from_dict(
                _stream_state(spec.partition_units, observed=observed).to_dict()
            ),
        )
    ]
    resumed.close()
    assert prefix + suffix == expected
    assert observed["replacement"] is True
    assert observed["nominal_epoch_size"] == 5
    with pytest.raises(ValueError, match="forbidden"):
        backend.describe_source(config, DataStage.VALIDATE)


def test_resampled_state_loads_through_training_loader_after_many_selections(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 replacement 计数超 shard 数后 canonical loader 仍可验证并恢复。"""
    config, samples = _webdataset_fixture(
        tmp_path / "webdataset",
        {"a.tar": [_payload("a0")], "b.tar": [_payload("b0")]},
        mode="resampled",
        nominal=9,
    )
    fake = _FakeWebDataset(samples)
    _install_fake_webdataset(monkeypatch, fake)
    module = DataModule(
        DataConfig(
            datasets=(config,),
            loader=DataLoaderConfig(batch_size=1),
        )
    )
    module.setup(DataStage.TRAIN)
    loader = module.train_dataloader()
    spec = loader.source_specs[0]
    planner: object = getattr(loader, "_plan_for_epoch", None)
    if not isinstance(planner, _EpochPlanner):
        raise TypeError("training loader epoch planner must be callable")
    plan = planner(0)
    assigned_units = _stream_units_for_source(plan.worker_assignments[0], source_id=0)
    initial_state = StreamPartitionState(
        worker_id=0,
        epoch=0,
        assignment_owner="autovla_loader",
        assigned_units=assigned_units,
        upstream_partitioning_disabled=True,
        assignment_digest=stable_fingerprint({"epoch": 0, "assigned_units": assigned_units}),
        shard_order_digest=plan.sequence_digest,
        shard_rng_state={"seed": plan.permutation_seed, "shuffle": False},
        sample_rng_state={
            "seed": derive_worker_seed(
                base_seed=0,
                epoch=0,
                global_rank=0,
                split="train",
                worker_id=0,
            )
        },
    )
    source = WebDatasetStreamingSource(config, spec)
    source.initialize_worker(WorkerContext())
    iterator = source.iter_samples(WorkerContext(), initial_state)
    for _ in range(5):
        next(iterator)
    observed = dict(source.state_dict())
    _close_dynamic(iterator)
    source.close()

    assert observed["resampled_selection_count"] == 5
    selection_count = _strict_int(observed["resampled_selection_count"], "selection count")
    shard_index = _strict_int(observed["shard_index"], "shard index")
    assert selection_count > len(assigned_units)
    assert 0 <= shard_index < len(assigned_units)
    assert observed["resampled_current_unit_index"] == observed["shard_index"]
    assert _string_mapping(observed["next_cursor"])["shard_index"] == shard_index
    worker_state = replace(
        initial_state,
        current_shard=_optional_string(observed["current_shard"], "current_shard"),
        shard_index=shard_index,
        consumed_sample_offset=_strict_int(
            observed["consumed_sample_offset"],
            "consumed sample offset",
        ),
        sample_rng_state=_string_mapping(observed["sample_rng_state"]),
        handler_counts=_string_int_mapping(observed["handler_counts"], "handler counts"),
        source_state=observed,
    )
    batch = TrainingBatch(
        images={"camera.rgb_0": np.zeros((1, 1, 1, 1), dtype=np.float32)},
        language=("resume",),
        actions=np.zeros((1, 1, 1), dtype=np.float32),
        action_mask=np.ones((1, 1, 1), dtype=np.bool_),
        sample_source=(
            {
                "autovla_worker": {
                    "worker_id": 0,
                    "pid": 1,
                    "actual_worker_process_count": 0,
                },
                "autovla_source_key": config.name,
                "autovla_stream_state": worker_state.to_dict(),
            },
        ),
        dataset_fingerprint="test-manifest",
        transform_fingerprint="identity",
        statistics_fingerprint="identity",
    )
    observer: object = getattr(loader, "_observe_and_commit", None)
    if not isinstance(observer, _BatchObserver):
        raise TypeError("training loader batch observer must be callable")
    observer(batch)
    checkpoint = loader.state_dict()
    partition_states = _string_mapping(checkpoint["stream_partition_states"])
    checkpoint_worker_state = _string_mapping(partition_states[f"{config.name}:0"])
    assert "resampled_selection_count" not in checkpoint_worker_state
    checkpoint_source_state = _string_mapping(checkpoint_worker_state["source_state"])
    assert checkpoint_source_state["resampled_selection_count"] == 5
    assert checkpoint_source_state["resampled_current_unit_index"] == (
        checkpoint_worker_state["shard_index"]
    )

    restored_module = DataModule(
        DataConfig(
            datasets=(config,),
            loader=DataLoaderConfig(batch_size=1),
        )
    )
    restored_module.setup(DataStage.TRAIN)
    restored_loader = restored_module.train_dataloader()
    validated = restored_loader.validate_state(checkpoint)
    validated_state = _string_mapping(validated.stream_partition_states[f"{config.name}:0"])
    assert _strict_int(validated_state["shard_index"], "validated shard index") < len(
        assigned_units
    )
    restored_loader.load_state_dict(checkpoint)
    assert restored_loader.state_dict() == checkpoint
    restored_module.close()
    module.close()


def test_webdataset_schema_failfast_decode_skip_and_transient_retry(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """验证 schema fail-fast、显式 decode skip 和仅本地 I/O 有界 retry。"""
    config, samples = _webdataset_fixture(
        tmp_path / "webdataset",
        {"a.tar": [_payload("bad"), _payload("good")]},
    )
    shard = next(iter(samples))
    spec = WebDatasetBackend().describe_source(config, DataStage.TRAIN)
    context = WorkerContext()

    schema_fake = _FakeWebDataset({shard: [{"__key__": "bad", "camera_0.npy": b"bad"}]})
    _install_fake_webdataset(monkeypatch, schema_fake)
    schema_source = WebDatasetStreamingSource(config, spec, handler_policy="warn_and_skip")
    schema_source.initialize_worker(context)
    with pytest.raises(DataSchemaMismatchError, match=r"payload\.json"):
        list(schema_source.iter_samples(context, _stream_state(spec.partition_units)))
    schema_source.close()

    corrupt = dict(_string_mapping(samples[shard][0]))
    corrupt["camera_0.npy"] = b"not-npy"
    decode_fake = _FakeWebDataset({shard: [corrupt, samples[shard][1]]})
    _install_fake_webdataset(monkeypatch, decode_fake)
    decode_source = WebDatasetStreamingSource(config, spec, handler_policy="warn_and_skip")
    decode_source.initialize_worker(context)
    decoded = list(decode_source.iter_samples(context, _stream_state(spec.partition_units)))
    assert [sample.sample_source["sample_id"] for sample in decoded] == ["good"]
    decode_counts = _string_mapping(decode_source.state_dict()["handler_counts"])
    assert decode_counts["warn_and_skip"] == 1
    decode_source.close()

    retry_fake = _FakeWebDataset({shard: [OSError("transient"), samples[shard][0]]})
    _install_fake_webdataset(monkeypatch, retry_fake)
    retry_source = WebDatasetStreamingSource(config, spec, transient_retries=1)
    retry_source.initialize_worker(context)
    retried = list(retry_source.iter_samples(context, _stream_state(spec.partition_units)))
    assert [sample.sample_source["sample_id"] for sample in retried] == ["bad"]
    retry_counts = _string_mapping(retry_source.state_dict()["handler_counts"])
    assert retry_counts["transient_retries"] == 1
    retry_source.close()


@pytest.mark.skipif(
    importlib.util.find_spec("webdataset") is None,
    reason="webdataset==1.0.2 is not installed; package execution remains deferred",
)
def test_webdataset_real_public_pipeline_when_represented_package_is_available(
    tmp_path: Path,
) -> None:
    """有真实 1.0.2 包时验证 lazy 公共 pipeline,否则精确跳过。"""
    root = tmp_path / "webdataset"
    shard = root / "shards/a.tar"
    shard.parent.mkdir(parents=True)
    payload = _payload("real-0")
    with tarfile.open(shard, "w") as archive:
        _tar_member(archive, "real-0.payload.json", json.dumps(payload).encode())
        _tar_member(
            archive,
            "real-0.camera_0.npy",
            _npy_bytes(np.zeros((2, 2, 3), dtype=np.uint8)),
        )
    _write_jsonl(root / "sample_index.jsonl", [{"shard": "shards/a.tar", "key": "real-0"}])
    config = DatasetConfig(
        name="real-wds",
        backend="webdataset",
        root=str(root),
        image_keys=("camera.rgb_0",),
        access_mode="streaming",
        stream_mode="finite_epoch",
        nominal_epoch_size=1,
    )
    backend = WebDatasetBackend()
    spec = backend.describe_source(config, DataStage.TRAIN)
    source = WebDatasetStreamingSource(config, spec)
    source.initialize_worker(WorkerContext())
    samples = list(source.iter_samples(WorkerContext(), _stream_state(spec.partition_units)))
    source.close()
    assert [sample.sample_source["sample_id"] for sample in samples] == ["real-0"]


def test_webdataset_rejects_network_url() -> None:
    """验证网络 shard 在迭代前失败关闭。"""
    config = DatasetConfig(
        name="remote",
        backend="webdataset",
        root="https://example.invalid/data",
        access_mode="streaming",
        stream_mode="finite_epoch",
        nominal_epoch_size=1,
    )
    with pytest.raises(ValueError, match="local shards"):
        WebDatasetBackend().describe_stream_partition_units(config, DataStage.TRAIN)


def test_robodm_grouped_reader_counts_literal_members_and_pickles(tmp_path: Path) -> None:
    """验证容器 LRU 和 member_reads 按真实 tar 成员提取计数。"""
    root = tmp_path / "robodm"
    rows: list[dict[str, object]] = []
    for index in range(2):
        relative = f"containers/c{index}.tar"
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        prefix = f"sample-{index}"
        with tarfile.open(path, "w") as archive:
            _tar_member(
                archive,
                f"{prefix}/payload.json",
                json.dumps(_payload(prefix)).encode("utf-8"),
            )
            _tar_member(
                archive,
                f"{prefix}/camera_0.npy",
                _npy_bytes(np.zeros((2, 2, 3), dtype=np.uint8)),
            )
        rows.append({"container": relative, "member_prefix": prefix})
    _write_jsonl(root / "sample_index.jsonl", rows)

    reader = RoboDMGroupedReader(root, max_handles=1)
    reader.read_records((0, 0))
    assert reader.counters["member_reads"] == 4
    reader.read_records((0,))
    reader.read_records((1,))
    assert reader.counters["member_reads"] == 8
    assert reader.counters["cache_hits"] >= 1
    assert reader.counters["evictions"] == 1
    restored = pickle.loads(pickle.dumps(reader))
    assert restored.counters == reader.counters
    reader.close()
    assert reader.counters["closes"] == 2


def test_robodm_source_order_provenance_and_content_fingerprint(tmp_path: Path) -> None:
    """验证 grouped 顺序、物理 provenance、NO_BACKEND_WINNER 和内容身份。"""
    root = tmp_path / "robodm"
    path = root / "containers/c0.tar"
    path.parent.mkdir(parents=True)
    rows: list[dict[str, object]] = []
    with tarfile.open(path, "w") as archive:
        for index in range(2):
            prefix = f"sample-{index}"
            _tar_member(
                archive,
                f"{prefix}/payload.json",
                json.dumps(_payload(prefix)).encode("utf-8"),
            )
            _tar_member(
                archive,
                f"{prefix}/camera_0.npy",
                _npy_bytes(np.zeros((2, 2, 3), dtype=np.uint8)),
            )
            rows.append({"container": "containers/c0.tar", "member_prefix": prefix})
    _write_jsonl(root / "sample_index.jsonl", rows)
    config = DatasetConfig(name="tiny-rdm", backend="robodm_container", root=str(root))
    backend = RoboDMContainerBackend()
    first_spec = backend.describe_source(config, DataStage.TRAIN)
    source = backend.open_source(config, DataStage.TRAIN, WorkerContext())
    samples = source.read_many((1, 0))
    assert [sample.sample_source["sample_id"] for sample in samples] == ["sample-1", "sample-0"]
    assert samples[0].sample_source["container"] == "containers/c0.tar"
    assert samples[0].sample_source["member_prefix"] == "sample-1"
    assert first_spec.compatibility_metadata["decision"] == "NO_BACKEND_WINNER"
    source.close()
    with path.open("ab") as stream:
        stream.write(b"bounded-identity-change")
    second_spec = backend.describe_source(config, DataStage.TRAIN)
    assert first_spec.source_fingerprint != second_spec.source_fingerprint
