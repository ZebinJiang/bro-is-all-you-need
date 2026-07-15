"""AutoVLA 本地 LeRobot v3 元数据和时间查询 MAP 源。"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Protocol, TypeGuard

import numpy as np

from autovla.config.schema import DatasetConfig
from autovla.core.semantics import TensorLayout
from autovla.core.types.training import TrainingSample
from autovla.data.backends.base import record_to_training_sample
from autovla.data.contracts import DataSourceSpec, TemporalQuery, WorkerContext, stable_fingerprint
from autovla.data.datasets.base import contained_path
from autovla.data.normalization import FeatureStatistics, NormalizationStatistics


class _LeRobotReader(Protocol):
    """约束数据集使用的 worker-local reader 最小接口。"""

    @property
    def owner_pid(self) -> int:
        """返回 live handle 的进程所有者。"""

        ...

    @property
    def counters(self) -> Mapping[str, int]:
        """返回有界缓存计数。"""

        ...

    def read_records(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """按请求顺序返回物理记录。"""

        ...

    def read_index_fields(self, indices: Sequence[int]) -> list[dict[str, object]]:
        """返回时间索引字段。"""

        ...

    def close(self) -> None:
        """释放 reader 拥有的资源。"""

        ...


@dataclass(frozen=True, slots=True)
class LeRobotFeature:
    """描述本地 LeRobot feature 的 dtype、shape 和媒体类型。"""

    name: str
    dtype: str
    shape: tuple[int, ...]
    media_kind: str = "none"


@dataclass(frozen=True, slots=True)
class LeRobotEpisode:
    """保存 episode 边界和任务身份。"""

    episode_index: int
    length: int
    tasks: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class LeRobotIndexEntry:
    """保存全局 anchor 到 episode/frame/物理 parquet 的映射。"""

    global_index: int
    episode_index: int
    frame_index: int
    data_path: str
    row_in_episode: int
    sample_id: str
    timestamp: float


@dataclass(frozen=True, slots=True)
class LocalLeRobotMetadata:
    """保存一次解析完成且可 spawn-pickle 的本地元数据。"""

    root: Path
    info: dict[str, object]
    features: tuple[LeRobotFeature, ...]
    fps: float
    total_episodes: int
    total_frames: int
    statistics: dict[str, object]
    tasks: tuple[tuple[int, str], ...]
    episodes: tuple[LeRobotEpisode, ...]
    index: tuple[LeRobotIndexEntry, ...]
    data_paths: tuple[str, ...]
    media_path_templates: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        """校验计数、索引和 episode 边界。"""
        if self.fps <= 0.0 or self.total_episodes <= 0 or self.total_frames <= 0:
            raise ValueError("LeRobot fps, episodes, and frames must be positive")
        if len(self.episodes) != self.total_episodes:
            raise ValueError("episodes.jsonl count differs from info.total_episodes")
        if len(self.index) != self.total_frames:
            raise ValueError("global index count differs from info.total_frames")
        if sum(episode.length for episode in self.episodes) != self.total_frames:
            raise ValueError("episode lengths differ from info.total_frames")
        episode_lengths = {episode.episode_index: episode.length for episode in self.episodes}
        if len(episode_lengths) != len(self.episodes) or any(
            length <= 0 for length in episode_lengths.values()
        ):
            raise ValueError("LeRobot episodes must be unique and non-empty")
        if not self.index:
            raise ValueError("LeRobot global sample index must not be empty")
        for expected, entry in enumerate(self.index):
            if entry.global_index != expected:
                raise ValueError("LeRobot global index must be dense and ordered")
            length = episode_lengths.get(entry.episode_index)
            if length is None or entry.frame_index < 0 or entry.frame_index >= length:
                raise ValueError("LeRobot index crosses declared episode boundary")
        if len({entry.sample_id for entry in self.index}) != len(self.index):
            raise ValueError("LeRobot sample identities must be unique")
        if len({(entry.episode_index, entry.frame_index) for entry in self.index}) != len(
            self.index
        ):
            raise ValueError("LeRobot episode/frame identities must be unique")

    @property
    def feature_map(self) -> dict[str, LeRobotFeature]:
        """返回按名称索引的 feature 副本。"""
        return {feature.name: feature for feature in self.features}

    @property
    def episode_map(self) -> dict[int, LeRobotEpisode]:
        """返回按数值 episode 索引的边界副本。"""
        return {episode.episode_index: episode for episode in self.episodes}

    @property
    def schema_identity(self) -> dict[str, object]:
        """返回解析后 feature/schema 身份。"""
        return {
            "codebase_version": self.info.get("codebase_version"),
            "features": [
                {
                    "name": feature.name,
                    "dtype": feature.dtype,
                    "shape": feature.shape,
                    "media_kind": feature.media_kind,
                }
                for feature in self.features
            ],
        }


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态值是否可作为对象映射读取。"""

    return isinstance(value, Mapping)


def _is_object_sequence(value: object) -> TypeGuard[Sequence[object]]:
    """判断动态值是否为非文本序列。"""

    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _require_string_mapping(value: object, name: str) -> dict[str, object]:
    """把运行时映射逐键收窄为字符串键对象映射。"""

    if not _is_object_mapping(value):
        raise ValueError(f"{name} must be a mapping")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str):
            raise ValueError(f"{name} keys must be strings")
        result[key] = item
    return result


def _record_payload(record: Mapping[str, object]) -> dict[str, object]:
    """校验并返回 reader 记录中的 payload 映射。"""

    return _require_string_mapping(record.get("payload"), "LeRobot record payload")


def _json(path: Path) -> dict[str, object]:
    """读取本地 JSON 映射并拒绝缺失或非映射值。"""
    if not path.is_file():
        raise ValueError(f"required local LeRobot metadata is missing: {path}")
    value: object = json.loads(path.read_text(encoding="utf-8"))
    return _require_string_mapping(value, f"LeRobot metadata {path}")


def _jsonl(path: Path) -> tuple[dict[str, object], ...]:
    """一次读取并校验 JSONL 映射。"""
    if not path.is_file():
        raise ValueError(f"required local LeRobot metadata is missing: {path}")
    rows: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        value: object = json.loads(line)
        rows.append(_require_string_mapping(value, f"LeRobot JSONL row {path}"))
    if not rows:
        raise ValueError(f"LeRobot JSONL must not be empty: {path}")
    return tuple(rows)


def _integer(value: object, name: str) -> int:
    """严格解析非负整数。"""
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a non-negative integer")
    return value


def _number(value: object, name: str) -> float:
    """严格解析有限数值。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be numeric")
    result = float(value)
    if not np.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


def inspect_local_lerobot(root: str | Path) -> LocalLeRobotMetadata:
    """一次加载 info/schema/stats/tasks/episodes/global index 和路径映射。"""
    dataset_root = Path(root).resolve()
    info = _json(dataset_root / "meta" / "info.json")
    statistics = _json(dataset_root / "meta" / "stats.json")
    task_rows = _jsonl(dataset_root / "meta" / "tasks.jsonl")
    episode_rows = _jsonl(dataset_root / "meta" / "episodes.jsonl")
    index_rows = _jsonl(dataset_root / "sample_index.jsonl")

    raw_features = _require_string_mapping(info.get("features"), "LeRobot info.features")
    features: list[LeRobotFeature] = []
    media_templates: list[tuple[str, str]] = []
    for raw_name, raw_value in sorted(raw_features.items()):
        value = _require_string_mapping(raw_value, f"LeRobot feature {raw_name!r}")
        dtype = value.get("dtype")
        shape = value.get("shape", ())
        if not isinstance(dtype, str) or not _is_object_sequence(shape):
            raise ValueError(f"LeRobot feature {raw_name!r} lacks dtype/shape")
        dimensions = tuple(_integer(item, f"feature {raw_name!r} shape") for item in shape)
        media_kind = (
            "video"
            if value.get("video_info") or dtype == "video"
            else "image" if dtype == "image" else "none"
        )
        features.append(LeRobotFeature(str(raw_name), dtype, dimensions, media_kind))
        template = value.get("path") or value.get("video_path")
        if media_kind != "none" and isinstance(template, str):
            media_templates.append((str(raw_name), template))

    task_values: list[tuple[int, str]] = []
    for row in task_rows:
        text = row.get("task")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("LeRobot task text must be non-empty")
        task_values.append((_integer(row.get("task_index"), "task_index"), text))
    tasks = tuple(task_values)
    if len({task_index for task_index, _ in tasks}) != len(tasks):
        raise ValueError("LeRobot task indices must be unique")
    episodes: list[LeRobotEpisode] = []
    for row in episode_rows:
        raw_tasks = row.get("tasks", ())
        if not _is_object_sequence(raw_tasks):
            raise ValueError("LeRobot episode tasks must be a sequence")
        episodes.append(
            LeRobotEpisode(
                episode_index=_integer(row.get("episode_index"), "episode_index"),
                length=_integer(row.get("length"), "episode length"),
                tasks=tuple(str(item) for item in raw_tasks),
            )
        )
    episode_map = {episode.episode_index: episode for episode in episodes}
    index: list[LeRobotIndexEntry] = []
    data_paths: set[str] = set()
    fps = _number(info.get("fps"), "LeRobot info.fps")
    required_features = {"action", "observation.state"}
    if not required_features.issubset(feature.name for feature in features):
        raise ValueError("LeRobot schema lacks action or observation.state")
    if not statistics:
        raise ValueError("LeRobot stats.json must not be empty")
    for global_index, row in enumerate(index_rows):
        episode_index = _integer(row.get("episode_index"), "episode_index")
        frame_index = _integer(row.get("frame_index", row.get("row_in_episode")), "frame_index")
        data_path = row.get("data_path")
        if not isinstance(data_path, str) or not data_path.strip():
            raise ValueError("LeRobot index data_path must be non-empty text")
        contained_path(dataset_root, data_path)
        data_paths.add(data_path)
        sample_id = row.get("sample_id", f"sample-{global_index:09d}")
        if not isinstance(sample_id, str) or not sample_id.strip():
            raise ValueError("LeRobot sample_id must be non-empty text")
        if episode_index not in episode_map:
            raise ValueError("LeRobot index references unknown episode")
        index.append(
            LeRobotIndexEntry(
                global_index=global_index,
                episode_index=episode_index,
                frame_index=frame_index,
                data_path=data_path,
                row_in_episode=_integer(row.get("row_in_episode"), "row_in_episode"),
                sample_id=sample_id,
                timestamp=_number(row.get("timestamp", frame_index / fps), "timestamp"),
            )
        )
    return LocalLeRobotMetadata(
        root=dataset_root,
        info=dict(info),
        features=tuple(features),
        fps=fps,
        total_episodes=_integer(info.get("total_episodes"), "total_episodes"),
        total_frames=_integer(info.get("total_frames"), "total_frames"),
        statistics=dict(statistics),
        tasks=tasks,
        episodes=tuple(sorted(episodes, key=lambda item: item.episode_index)),
        index=tuple(index),
        data_paths=tuple(sorted(data_paths)),
        media_path_templates=tuple(sorted(media_templates)),
    )


def convert_lerobot_statistics(
    metadata: LocalLeRobotMetadata,
    *,
    feature_names: Sequence[str] = ("observation.state", "action"),
) -> NormalizationStatistics:
    """把本地 LeRobot 统计量严格映射到 R3 rank-aware 统计契约。

    一维数组映射为 ``[D]``, 二维数组映射为 ``[T,D]``; 函数不会展平、
    取首步或联网补全缺失字段。
    """

    converted: dict[str, FeatureStatistics] = {}
    for name in feature_names:
        raw = metadata.statistics.get(name)
        values = _require_string_mapping(raw, f"LeRobot statistics {name!r}")
        method: str
        kwargs: dict[str, object]
        if "mean" in values and "std" in values:
            method = "mean_std"
            kwargs = {"mean": values["mean"], "std": values["std"]}
        elif "min" in values and "max" in values:
            method = "min_max"
            kwargs = {"minimum": values["min"], "maximum": values["max"]}
        else:
            raise ValueError(f"LeRobot statistics {name!r} require mean/std or min/max")
        first = np.asarray(next(iter(kwargs.values())))
        if first.ndim == 0:
            layout = TensorLayout.scalar()
        elif first.ndim == 1:
            layout = TensorLayout.feature()
        elif first.ndim == 2:
            layout = TensorLayout.time_feature()
        else:
            raise ValueError(f"LeRobot statistics {name!r} must be scalar, [D], or [T,D]")
        converted[name] = FeatureStatistics(
            method=method,
            layout=layout,
            constant_feature_policy="identity",
            **kwargs,
        )
    return NormalizationStatistics(features=converted)


class LocalLeRobotDataset:
    """提供 grouped MAP 读取、episode-safe TemporalQuery 和 worker-local 媒体缓存。"""

    def __init__(
        self,
        config: DatasetConfig,
        spec: DataSourceSpec,
        metadata: LocalLeRobotMetadata,
        *,
        temporal_query: TemporalQuery | None = None,
    ) -> None:
        self._config = config
        self.spec = spec
        self._metadata = metadata
        self._temporal_query = temporal_query
        if temporal_query is not None and temporal_query.feature_family == "action":
            query_size = len(temporal_query.frame_offsets) + len(temporal_query.timestamp_deltas)
            if query_size != temporal_query.action_horizon:
                raise ValueError("action TemporalQuery size must match action_horizon")
        self._reader: _LeRobotReader | None = None
        self._by_episode_frame = {
            (entry.episode_index, entry.frame_index): entry for entry in metadata.index
        }
        self._episode_entries: dict[int, tuple[LeRobotIndexEntry, ...]] = {}
        for episode in metadata.episodes:
            self._episode_entries[episode.episode_index] = tuple(
                entry for entry in metadata.index if entry.episode_index == episode.episode_index
            )

    @property
    def metadata(self) -> LocalLeRobotMetadata:
        """返回 spawn-safe 本地 metadata。"""
        return self._metadata

    @property
    def name(self) -> str:
        """返回数据集名称。"""
        return self._config.name

    def __len__(self) -> int:
        """返回全局 anchor 索引长度。"""
        return len(self._metadata.index)

    def __getstate__(self) -> dict[str, object]:
        """pickle 时排除 ParquetFile、媒体 decoder 和 live handle。"""
        state = dict(self.__dict__)
        state["_reader"] = None
        return state

    def initialize_worker(self, context: WorkerContext) -> None:
        """在消费 worker 中一次建立 parquet footer/row-group/media 映射。"""
        del context
        if self._reader is not None and self._reader.owner_pid != os.getpid():
            self._reader.close()
            self._reader = None
        if self._reader is None:
            from autovla.dataloader.stores.lerobot_v3_reader import LeRobotGroupedReader

            reader = LeRobotGroupedReader(self._metadata)
            try:
                if self._temporal_query is not None and self._temporal_query.timestamp_deltas:
                    facts = reader.read_index_fields(range(len(self._metadata.index)))
                    updated: list[LeRobotIndexEntry] = []
                    for entry, fact in zip(self._metadata.index, facts, strict=True):
                        if (
                            fact["episode_index"] != entry.episode_index
                            or fact["frame_index"] != entry.frame_index
                        ):
                            raise ValueError("parquet temporal index differs from global index")
                        updated.append(
                            replace(
                                entry,
                                timestamp=_number(fact.get("timestamp"), "parquet timestamp"),
                            )
                        )
                    self._by_episode_frame = {
                        (entry.episode_index, entry.frame_index): entry for entry in updated
                    }
                    self._episode_entries = {
                        episode.episode_index: tuple(
                            entry
                            for entry in updated
                            if entry.episode_index == episode.episode_index
                        )
                        for episode in self._metadata.episodes
                    }
                self._reader = reader
            except Exception:
                reader.close()
                raise

    def _boundary_entry(
        self, anchor: LeRobotIndexEntry, target_frame: int, policy: str
    ) -> tuple[LeRobotIndexEntry, bool]:
        """解析一个 frame offset 并应用 pad/clip/error 边界策略。"""
        exact = self._by_episode_frame.get((anchor.episode_index, target_frame))
        if exact is not None:
            return exact, True
        entries = self._episode_entries[anchor.episode_index]
        if policy == "error":
            raise IndexError("TemporalQuery crosses an episode boundary")
        boundary = min(
            entries, key=lambda item: (abs(item.frame_index - target_frame), item.frame_index)
        )
        return boundary, policy == "clip"

    def _temporal_window(
        self, anchor: LeRobotIndexEntry
    ) -> tuple[tuple[LeRobotIndexEntry, ...], tuple[bool, ...]]:
        """把 canonical TemporalQuery 展开成同 episode 物理索引和真实 mask。"""
        query = self._temporal_query
        if query is None:
            return (anchor,), (True,)
        if query.frame_offsets and query.anchor_semantics not in {"sample", "frame"}:
            raise ValueError("frame offsets require sample or frame anchor semantics")
        if query.timestamp_deltas and query.anchor_semantics not in {"sample", "timestamp"}:
            raise ValueError("timestamp deltas require sample or timestamp anchor semantics")
        entries: list[LeRobotIndexEntry] = []
        observed: list[bool] = []
        frame_anchor = anchor.frame_index
        for offset in query.frame_offsets:
            entry, valid = self._boundary_entry(
                anchor, frame_anchor + offset, query.boundary_policy
            )
            entries.append(entry)
            observed.append(valid)
        episode_entries = self._episode_entries[anchor.episode_index]
        tolerance = query.tolerance
        if tolerance is None:
            tolerance = 0.5 / (query.fps or self._metadata.fps)
        timestamp_anchor = anchor.timestamp
        for delta in query.timestamp_deltas:
            target = timestamp_anchor + delta
            nearest = min(episode_entries, key=lambda item: abs(item.timestamp - target))
            distance = abs(nearest.timestamp - target)
            if distance <= tolerance:
                entries.append(nearest)
                observed.append(True)
            else:
                entry, valid = self._boundary_entry(
                    anchor,
                    round(target * (query.fps or self._metadata.fps)),
                    query.boundary_policy,
                )
                entries.append(entry)
                observed.append(valid)
        mask = tuple(observed)
        if query.output_mask_semantics == "true_is_padding":
            mask = tuple(not value for value in mask)
        return tuple(entries), mask

    def read(self, index: int) -> TrainingSample:
        """读取一个 anchor 及其可选 temporal window。"""
        return self.read_many((index,))[0]

    def read_many(self, indices: Sequence[int]) -> Sequence[TrainingSample]:
        """批量展开时间窗口,按物理位置分组读取并恢复 anchor 顺序。"""
        if any(index < 0 or index >= len(self) for index in indices):
            raise IndexError("LeRobot index out of range")
        if self._reader is None:
            raise RuntimeError("LeRobot source must be initialized in its worker")
        anchors = [
            self._by_episode_frame[
                (
                    self._metadata.index[index].episode_index,
                    self._metadata.index[index].frame_index,
                )
            ]
            for index in indices
        ]
        windows = [self._temporal_window(anchor) for anchor in anchors]
        flattened_list: list[int] = []
        for anchor, (entries, _) in zip(anchors, windows, strict=True):
            flattened_list.append(anchor.global_index)
            if self._temporal_query is not None:
                flattened_list.extend(entry.global_index for entry in entries)
        flattened = tuple(flattened_list)
        records = self._reader.read_records(flattened)
        output: list[TrainingSample] = []
        cursor = 0
        for anchor_index, anchor, (entries, temporal_mask) in zip(
            indices, anchors, windows, strict=True
        ):
            anchor_record = records[cursor]
            cursor += 1
            if self._temporal_query is None:
                window_records = [anchor_record]
            else:
                window_records = records[cursor : cursor + len(entries)]
                cursor += len(entries)
            sample = record_to_training_sample(anchor_record, config=self._config)
            query = self._temporal_query
            if query is not None and query.feature_family == "action":
                actions = np.concatenate(
                    [
                        np.asarray(_record_payload(record)["action"])
                        .reshape(1, -1)
                        .astype(np.float32)
                        for record in window_records
                    ],
                    axis=0,
                )
                masks = np.concatenate(
                    [
                        np.asarray(
                            _record_payload(record)["action_mask"],
                            dtype=np.bool_,
                        ).reshape(1, -1)
                        for record in window_records
                    ],
                    axis=0,
                )
                sample = replace(sample, actions=actions, action_mask=masks)
            source = dict(sample.sample_source)
            source.update(
                {
                    "anchor_index": anchor_index,
                    "anchor_semantics": "sample" if query is None else query.anchor_semantics,
                    "anchor_episode_index": anchor.episode_index,
                    "anchor_frame_index": anchor.frame_index,
                    "anchor_timestamp": _number(
                        _record_payload(anchor_record).get("timestamp"),
                        "anchor timestamp",
                    ),
                    "physical_format": "lerobot_v3_local",
                    "physical": anchor_record.get("physical_source", {}),
                    "temporal_physical": tuple(
                        record.get("physical_source", {}) for record in window_records
                    ),
                }
            )
            metadata = dict(sample.metadata)
            metadata.update(
                {
                    "temporal_query_fingerprint": "none" if query is None else query.fingerprint,
                    "temporal_query_mask": np.asarray(temporal_mask, dtype=np.bool_),
                    "temporal_mask_semantics": (
                        "true_is_observed" if query is None else query.output_mask_semantics
                    ),
                    "temporal_global_indices": tuple(entry.global_index for entry in entries),
                }
            )
            output.append(replace(sample, sample_source=source, metadata=metadata))
        return tuple(output)

    def state_dict(self) -> Mapping[str, object]:
        """返回 metadata/load/cache 状态和精确下一 anchor 身份语义。"""
        counters: Mapping[str, int] = (
            dict[str, int]() if self._reader is None else self._reader.counters
        )
        return {
            "cache_counters": counters,
            "resume_identity": "next_anchor_global_index",
            "temporal_query_fingerprint": (
                "none" if self._temporal_query is None else self._temporal_query.fingerprint
            ),
            "metadata_fingerprint": stable_fingerprint(self._metadata.schema_identity),
        }

    def close(self) -> None:
        """幂等关闭 worker-local parquet 与媒体缓存。"""
        reader, self._reader = self._reader, None
        if reader is not None:
            reader.close()


__all__ = [
    "LeRobotEpisode",
    "LeRobotFeature",
    "LeRobotIndexEntry",
    "LocalLeRobotDataset",
    "LocalLeRobotMetadata",
    "convert_lerobot_statistics",
    "inspect_local_lerobot",
]
