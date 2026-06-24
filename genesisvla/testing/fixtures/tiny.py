"""M2 tiny fixture 生成器。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import DatasetStatistics, FeatureStatistics


@dataclass(frozen=True, slots=True)
class TinyLeRobotFixture:
    """内存 LeRobot-like tiny fixture。"""

    samples: tuple[RawSample, ...]
    statistics: DatasetStatistics
    provenance: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class TinyParquetFixture:
    """内存 Parquet-like tiny fixture。"""

    records: tuple[Mapping[str, Any], ...]
    provenance: Mapping[str, str]


def _sample(index: int) -> RawSample:
    """构造固定数值的小型机器人样本。"""
    base = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    image = base + np.uint8(index)
    action_base = np.asarray([[2.0, 6.0, 99.0], [4.0, 10.0, 99.0]], dtype=np.float32)
    state_base = np.asarray([1.0, 2.0, 99.0], dtype=np.float32)
    return RawSample(
        images={"front": image},
        language=f"tiny pick-place episode {index}",
        actions=action_base + np.asarray([[index, index, 0.0], [index, index, 0.0]]),
        state=state_base + np.asarray([index, index, 0.0], dtype=np.float32),
        robot_tag="tiny-arm",
        metadata={
            "episode_id": index,
            "action_mask": np.asarray([True, True, False]),
        },
    )


def tiny_lerobot_fixture() -> TinyLeRobotFixture:
    """生成不依赖外部下载的 LeRobot-like tiny fixture。"""
    action = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 2.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )
    state = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 2.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 1.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )
    statistics = DatasetStatistics(
        schema_version="2.0",
        dataset_fingerprint="tiny-lerobot-generated-v1",
        transform_fingerprint="raw",
        count=2,
        state=state,
        action=action,
        metadata={"fixture": "tiny_lerobot"},
    )
    return TinyLeRobotFixture(
        samples=(_sample(0), _sample(1)),
        statistics=statistics,
        provenance={
            "source": "generated",
            "format": "lerobot-like-in-memory",
            "real_format": "false",
            "license": "project-generated",
        },
    )


def tiny_parquet_fixture() -> TinyParquetFixture:
    """生成不写磁盘的 Parquet-like 记录 fixture。"""
    records = tuple(
        {
            "robot_tag": sample.robot_tag,
            "language": sample.language,
            "actions": np.asarray(sample.actions),
            "state": np.asarray(sample.state),
            "padding_mask": np.asarray(sample.metadata["action_mask"], dtype=np.bool_),
        }
        for sample in tiny_lerobot_fixture().samples
    )
    return TinyParquetFixture(
        records=records,
        provenance={
            "source": "generated",
            "format": "parquet-like-in-memory",
            "real_format": "false",
            "license": "project-generated",
        },
    )
