"""AutoVLA 数据集读取边界。"""

from __future__ import annotations

from abc import abstractmethod
from typing import Protocol

from autovla.config.schema import DatasetConfig
from autovla.data.types import DataStage, TrainingSample


class DatasetHandle(Protocol):
    """定义已打开本地数据集的有界生命周期。"""

    @property
    @abstractmethod
    def name(self) -> str:
        """返回稳定数据集名称。"""
        raise NotImplementedError

    @abstractmethod
    def __len__(self) -> int:
        """返回可读取样本数量。"""
        raise NotImplementedError

    @abstractmethod
    def read(self, index: int) -> TrainingSample:
        """按局部索引读取一条规范样本。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭持久句柄并释放本地资源。"""
        raise NotImplementedError


class DatasetFactory(Protocol):
    """定义配置到数据集句柄的工厂。"""

    @abstractmethod
    def __call__(self, config: DatasetConfig, stage: DataStage) -> DatasetHandle:
        """打开显式本地数据集。"""
        raise NotImplementedError


__all__ = ["DatasetFactory", "DatasetHandle"]
