"""AutoVLA 本地 LeRobot 元数据和样本 reader。"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast

from autovla.config.schema import DatasetConfig
from autovla.data.backends.base import local_sample_count, record_to_training_sample
from autovla.data.types import TrainingSample


@dataclass(frozen=True, slots=True)
class LeRobotFeature:
    """描述本地 LeRobot feature 的 dtype、shape 和视频属性。"""

    name: str
    dtype: str
    shape: tuple[int, ...]
    is_video: bool = False

    def __post_init__(self) -> None:
        """校验 feature 名称、类型和维度。"""
        if not self.name.strip() or not self.dtype.strip():
            raise ValueError("LeRobot feature name and dtype must not be empty")
        if any(dimension <= 0 for dimension in self.shape):
            raise ValueError("LeRobot feature shape dimensions must be positive")


@dataclass(frozen=True, slots=True)
class LocalLeRobotMetadata:
    """保存完整本地 LeRobot 数据集的关键元数据。"""

    root: Path
    features: Mapping[str, LeRobotFeature]
    fps: float
    total_episodes: int
    total_frames: int
    statistics: Mapping[str, object]

    def __post_init__(self) -> None:
        """冻结 feature 和统计量映射。"""
        if self.fps <= 0.0 or self.total_episodes <= 0 or self.total_frames <= 0:
            raise ValueError("LeRobot fps, episodes, and frames must be positive")
        object.__setattr__(self, "features", MappingProxyType(dict(self.features)))
        object.__setattr__(self, "statistics", MappingProxyType(dict(self.statistics)))


def _json(path: Path) -> Mapping[str, object]:
    """读取本地 JSON 映射并拒绝缺失或非映射值。"""
    if not path.is_file():
        raise ValueError(f"required local LeRobot metadata is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"LeRobot metadata must be a mapping: {path}")
    return cast(Mapping[str, object], value)


def inspect_local_lerobot(root: str | Path) -> LocalLeRobotMetadata:
    """在不调用 Hub 的前提下校验并读取完整本地 metadata surface。"""
    dataset_root = Path(root).resolve()
    info = _json(dataset_root / "meta" / "info.json")
    statistics = _json(dataset_root / "meta" / "stats.json")
    for required in (
        dataset_root / "meta" / "tasks.jsonl",
        dataset_root / "meta" / "episodes.jsonl",
        dataset_root / "sample_index.jsonl",
    ):
        if not required.is_file():
            raise ValueError(f"required local LeRobot file is missing: {required}")
    raw_features_value = info.get("features")
    if not isinstance(raw_features_value, Mapping):
        raise ValueError("LeRobot info.features must be a mapping")
    raw_features = cast(Mapping[object, object], raw_features_value)
    features: dict[str, LeRobotFeature] = {}
    for name, raw in raw_features.items():
        if not isinstance(raw, Mapping):
            raise ValueError(f"LeRobot feature {name!r} must be a mapping")
        raw_mapping = cast(Mapping[str, object], raw)
        dtype = raw_mapping.get("dtype")
        shape = raw_mapping.get("shape", ())
        if not isinstance(dtype, str) or not isinstance(shape, (list, tuple)):
            raise ValueError(f"LeRobot feature {name!r} lacks dtype/shape")
        shape_values = cast(list[object] | tuple[object, ...], shape)
        dimensions: list[int] = []
        for value in shape_values:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"LeRobot feature {name!r} shape must contain integers")
            dimensions.append(value)
        features[str(name)] = LeRobotFeature(
            name=str(name),
            dtype=dtype,
            shape=tuple(dimensions),
            is_video=bool(raw_mapping.get("video_info")) or dtype in {"video", "image"},
        )
    fps = info.get("fps")
    episodes = info.get("total_episodes")
    frames = info.get("total_frames")
    if isinstance(fps, bool) or not isinstance(fps, (int, float)):
        raise ValueError("LeRobot info.fps must be numeric")
    if isinstance(episodes, bool) or not isinstance(episodes, int):
        raise ValueError("LeRobot info.total_episodes must be an integer")
    if isinstance(frames, bool) or not isinstance(frames, int):
        raise ValueError("LeRobot info.total_frames must be an integer")
    return LocalLeRobotMetadata(
        root=dataset_root,
        features=features,
        fps=float(fps),
        total_episodes=episodes,
        total_frames=frames,
        statistics=statistics,
    )


class LocalLeRobotDataset:
    """通过现有本地 LeRobot v3 reader 提供规范样本。"""

    def __init__(self, config: DatasetConfig) -> None:
        """校验完整本地 metadata 后保存配置。"""
        self._config = config
        self._metadata = inspect_local_lerobot(config.root)
        self._count = local_sample_count(self._metadata.root, config.sample_count)

    @property
    def metadata(self) -> LocalLeRobotMetadata:
        """返回只读本地 metadata。"""
        return self._metadata

    @property
    def name(self) -> str:
        """返回数据集名称。"""
        return self._config.name

    def __len__(self) -> int:
        """返回本地索引样本数。"""
        return self._count

    def read(self, index: int) -> TrainingSample:
        """读取本地 parquet 行并转换为规范样本。"""
        if index < 0 or index >= self._count:
            raise IndexError(index)
        from autovla.dataloader.stores.lerobot_v3_reader import (
            read_lerobot_v3_local_batches,
        )

        payload = read_lerobot_v3_local_batches(self._metadata.root, (index,))[0]
        return record_to_training_sample(payload, config=self._config)

    def close(self) -> None:
        """本地 reader 按调用关闭文件,无持久资源需要释放。"""
        return None


__all__ = [
    "LeRobotFeature",
    "LocalLeRobotDataset",
    "LocalLeRobotMetadata",
    "inspect_local_lerobot",
]
