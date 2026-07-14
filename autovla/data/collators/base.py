"""AutoVLA 通用批整理边界。"""

from abc import abstractmethod
from typing import Protocol, Sequence

from autovla.core.types.training import TrainingBatch, TrainingSample


class BatchCollator(Protocol):
    """定义样本序列到规范训练批的纯数据变换。"""

    @abstractmethod
    def __call__(self, samples: Sequence[TrainingSample]) -> TrainingBatch:
        """整理样本,不执行分词或模型族图像处理。"""
        raise NotImplementedError


__all__ = ["BatchCollator"]
