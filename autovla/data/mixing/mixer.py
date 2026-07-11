"""AutoVLA 确定性数据集混合。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from autovla.data.datasets.base import DatasetHandle
from autovla.data.sampling import PartitionContext
from autovla.data.types import TrainingSample


@dataclass(frozen=True, slots=True)
class WeightedDataset:
    """绑定已打开数据集及其正权重。"""

    dataset: DatasetHandle
    weight: float

    def __post_init__(self) -> None:
        """校验权重和非空数据集。"""
        if self.weight <= 0.0:
            raise ValueError("dataset weight must be positive")
        if len(self.dataset) <= 0:
            raise ValueError("mixed datasets must not be empty")


class DatasetMixer:
    """按 seed/epoch/全局位置确定性选择数据集和样本。"""

    def __init__(self, datasets: Sequence[WeightedDataset], *, seed: int) -> None:
        """拥有数据集序列并初始化独立局部游标。"""
        if not datasets:
            raise ValueError("datasets must not be empty")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        names = tuple(item.dataset.name for item in datasets)
        if len(set(names)) != len(names):
            raise ValueError("dataset names must be unique")
        self._datasets = tuple(datasets)
        self._seed = seed
        self._cursors: dict[str, int] = {name: 0 for name in names}
        total = sum(item.weight for item in datasets)
        cumulative = 0.0
        thresholds: list[float] = []
        for item in datasets:
            cumulative += item.weight / total
            thresholds.append(cumulative)
        thresholds[-1] = 1.0
        self._thresholds = tuple(thresholds)

    @property
    def datasets(self) -> tuple[WeightedDataset, ...]:
        """返回注册顺序稳定的加权数据集。"""
        return self._datasets

    def _choice(self, *, epoch: int, global_position: int) -> int:
        """用稳定摘要生成 ``[0,1)`` 选择值。"""
        payload = f"{self._seed}:{epoch}:{global_position}".encode("ascii")
        integer = int.from_bytes(hashlib.sha256(payload).digest()[:8], "big")
        value = integer / float(1 << 64)
        for index, threshold in enumerate(self._thresholds):
            if value < threshold:
                return index
        return len(self._thresholds) - 1

    def select(self, *, epoch: int, global_position: int) -> WeightedDataset:
        """按稳定位置选择加权数据集,但不推进任何读取游标。"""

        if epoch < 0 or global_position < 0:
            raise ValueError("epoch and global_position must be non-negative")
        return self._datasets[self._choice(epoch=epoch, global_position=global_position)]

    def read(
        self,
        local_position: int,
        *,
        epoch: int,
        partition: PartitionContext,
    ) -> TrainingSample:
        """选择一个数据集并从其循环局部游标读取样本。"""
        if epoch < 0:
            raise ValueError("epoch must be non-negative")
        global_position = partition.global_position(local_position)
        selected = self.select(epoch=epoch, global_position=global_position)
        name = selected.dataset.name
        cursor = self._cursors[name]
        self._cursors[name] = cursor + 1
        dataset_index = partition.global_position(cursor) % len(selected.dataset)
        return selected.dataset.read(dataset_index)

    def cursor_state(self) -> Mapping[str, int]:
        """返回可进入检查点元数据的数据集游标副本。"""
        return dict(self._cursors)

    def restore_cursors(self, state: Mapping[str, int]) -> None:
        """严格恢复所有数据集游标。"""
        if set(state) != set(self._cursors):
            raise ValueError("cursor state dataset names do not match mixer")
        for name, value in state.items():
            if value < 0:
                raise ValueError(f"cursor for {name!r} must be non-negative")
        self._cursors = dict(state)


__all__ = ["DatasetMixer", "WeightedDataset"]
