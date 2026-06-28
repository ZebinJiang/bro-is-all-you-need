"""M2 MixtureDataset 确定性采样契约测试。"""

from __future__ import annotations

from collections import Counter
from typing import Any

import numpy as np
import pytest

from autovla.core.types import RawSample
from autovla.dataloader.datasets import InMemoryDataset, MixtureDataset


def _sample(name: str, index: int) -> RawSample:
    """构造带来源信息的小样本。"""
    return RawSample(
        images={"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        language=f"{name}-{index}",
        actions=np.asarray([[float(index), 0.0]], dtype=np.float32),
        state=np.asarray([float(index), 0.0], dtype=np.float32),
        robot_tag="tiny-arm",
        metadata={"dataset": name, "index": index},
    )


def _dataset(name: str, count: int) -> InMemoryDataset:
    """构造内存数据集。"""
    return InMemoryDataset(name=name, samples=tuple(_sample(name, i) for i in range(count)))


def _sequence(dataset: MixtureDataset, count: int, **kwargs: Any) -> list[str]:
    """返回采样来源序列。"""
    return [
        sample.metadata["sample_source"]["dataset"] for sample in dataset.sample(count, **kwargs)
    ]


def test_should_sample_same_sequence_for_same_seed_and_epoch() -> None:
    """验证相同 seed/epoch 产生相同序列。"""
    mixture = MixtureDataset(((_dataset("a", 3), 0.7), (_dataset("b", 3), 0.3)), seed=11)

    assert _sequence(mixture, 20, epoch=2) == _sequence(mixture, 20, epoch=2)


def test_should_change_sequence_for_different_epoch() -> None:
    """验证 epoch 参与采样随机性。"""
    mixture = MixtureDataset(((_dataset("a", 3), 0.7), (_dataset("b", 3), 0.3)), seed=11)

    assert _sequence(mixture, 20, epoch=1) != _sequence(mixture, 20, epoch=2)


def test_should_respect_weights_within_tolerance() -> None:
    """验证加权采样比例在小型统计容差内。"""
    mixture = MixtureDataset(((_dataset("a", 5), 0.8), (_dataset("b", 5), 0.2)), seed=3)

    counts = Counter(_sequence(mixture, 1000, epoch=0))

    assert 720 <= counts["a"] <= 880
    assert 120 <= counts["b"] <= 280


def test_should_reject_invalid_weights() -> None:
    """验证负权重和零总权重会失败。"""
    with pytest.raises(ValueError, match="weight"):
        MixtureDataset(((_dataset("a", 1), -1.0),), seed=0)
    with pytest.raises(ValueError, match="weight"):
        MixtureDataset(((_dataset("a", 1), 0.0),), seed=0)
    with pytest.raises(ValueError, match="finite"):
        MixtureDataset(((_dataset("a", 1), float("nan")),), seed=0)
    with pytest.raises(ValueError, match="dataset name"):
        MixtureDataset(((_dataset("a", 1), 1.0), (_dataset("a", 1), 1.0)), seed=0)


def test_should_split_worker_sequences_without_duplicate_positions() -> None:
    """验证 worker 切分同一全局序列时不重复采样位置。"""
    mixture = MixtureDataset(((_dataset("a", 10), 1.0),), seed=5)

    left = list(mixture.sample(5, epoch=0, worker_id=0, worker_count=2))
    right = list(mixture.sample(5, epoch=0, worker_id=1, worker_count=2))

    left_positions = {sample.metadata["sample_source"]["position"] for sample in left}
    right_positions = {sample.metadata["sample_source"]["position"] for sample in right}
    assert left_positions.isdisjoint(right_positions)


def test_should_split_rank_sequences_and_record_source_metadata() -> None:
    """验证 rank/world_size 参与采样切分并写入来源元数据。"""
    mixture = MixtureDataset(((_dataset("a", 10), 1.0),), seed=5)

    rank0 = list(mixture.sample(4, epoch=1, worker_id=0, worker_count=2, rank=0, world_size=2))
    rank1 = list(mixture.sample(4, epoch=1, worker_id=0, worker_count=2, rank=1, world_size=2))

    rank0_positions = {sample.metadata["sample_source"]["position"] for sample in rank0}
    rank1_positions = {sample.metadata["sample_source"]["position"] for sample in rank1}
    assert rank0_positions.isdisjoint(rank1_positions)
    source = rank0[0].metadata["sample_source"]
    assert source["worker_id"] == 0
    assert source["worker_count"] == 2
    assert source["rank"] == 0
    assert source["world_size"] == 2
    assert source["dataset_index"] == 0
