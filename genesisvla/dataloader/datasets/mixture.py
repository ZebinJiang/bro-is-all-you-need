"""M2 deterministic mixture 数据集。"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass, replace

import numpy as np

from genesisvla.core.types import RawSample


@dataclass(frozen=True, slots=True)
class InMemoryDataset:
    """只持有小型 RawSample 元组的测试数据集。"""

    name: str
    samples: tuple[RawSample, ...]

    def __post_init__(self) -> None:
        """校验数据集非空且名称稳定。"""
        if not self.name.strip():
            raise ValueError("dataset name must not be empty")
        if not self.samples:
            raise ValueError("samples must not be empty")

    def __len__(self) -> int:
        """返回样本数量。"""
        return len(self.samples)

    def __getitem__(self, index: int) -> RawSample:
        """按索引读取样本。"""
        return self.samples[index]


class MixtureDataset:
    """按固定 seed/epoch 从多个内存数据集确定性混采。"""

    def __init__(self, datasets: Sequence[tuple[InMemoryDataset, float]], *, seed: int) -> None:
        if not datasets:
            raise ValueError("datasets must not be empty")
        if isinstance(seed, bool):
            raise TypeError("seed must be an int")
        weights = np.asarray([weight for _dataset, weight in datasets], dtype=np.float64)
        if not bool(np.all(np.isfinite(weights))):
            raise ValueError("mixture weights must be finite")
        if bool(np.any(weights <= 0.0)) or float(weights.sum()) <= 0.0:
            raise ValueError("mixture weights must be positive")
        names = tuple(dataset.name for dataset, _weight in datasets)
        if len(set(names)) != len(names):
            raise ValueError("dataset names must be unique")
        self._datasets = tuple(dataset for dataset, _weight in datasets)
        self._weights = weights / weights.sum()
        self._seed = seed

    def sample(
        self,
        count: int,
        *,
        epoch: int = 0,
        worker_id: int = 0,
        worker_count: int = 1,
        rank: int = 0,
        world_size: int = 1,
    ) -> Iterator[RawSample]:
        """产生确定性样本流, worker 通过全局 position 切分。"""
        if count < 0:
            raise ValueError("count must be non-negative")
        if epoch < 0:
            raise ValueError("epoch must be non-negative")
        if worker_count <= 0:
            raise ValueError("worker_count must be positive")
        if worker_id < 0 or worker_id >= worker_count:
            raise ValueError("worker_id must be in [0, worker_count)")
        if world_size <= 0:
            raise ValueError("world_size must be positive")
        if rank < 0 or rank >= world_size:
            raise ValueError("rank must be in [0, world_size)")

        parallel_index = rank * worker_count + worker_id
        parallel_count = world_size * worker_count
        for offset in range(count):
            position = parallel_index + offset * parallel_count
            rng = np.random.default_rng(np.random.SeedSequence([self._seed, epoch, position]))
            dataset_index = int(rng.choice(len(self._datasets), p=self._weights))
            dataset = self._datasets[dataset_index]
            sample_index = int(rng.integers(0, len(dataset)))
            source = {
                "dataset": dataset.name,
                "dataset_index": dataset_index,
                "index": sample_index,
                "position": position,
                "global_position": position,
                "epoch": epoch,
                "worker_id": worker_id,
                "worker_count": worker_count,
                "rank": rank,
                "world_size": world_size,
                "seed": self._seed,
            }
            metadata = dict(dataset[sample_index].metadata)
            metadata["sample_source"] = source
            yield replace(dataset[sample_index], metadata=metadata)
