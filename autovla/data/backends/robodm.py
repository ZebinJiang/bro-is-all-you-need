"""AutoVLA RoboDM-container 适配器。"""

from pathlib import Path

from autovla.config.schema import DatasetConfig
from autovla.data.backends.base import local_sample_count, record_to_training_sample
from autovla.data.types import DataStage, TrainingSample


class RoboDMContainerHandle:
    """通过现有持久索引和有界句柄池读取容器。"""

    def __init__(self, config: DatasetConfig) -> None:
        """打开 AutoVLA-owned 容器索引。"""
        from autovla.dataloader.stores.robodm_reader import RoboDMGroupedReader

        self._config = config
        self._count = local_sample_count(Path(config.root), config.sample_count)
        self._reader = RoboDMGroupedReader(Path(config.root))

    @property
    def name(self) -> str:
        """返回数据集名称。"""
        return self._config.name

    def __len__(self) -> int:
        """返回索引样本数。"""
        return self._count

    def read(self, index: int) -> TrainingSample:
        """分组 reader 读取一条记录并转换为规范样本。"""
        if index < 0 or index >= self._count:
            raise IndexError(index)
        record = self._reader.read_records((index,))[0]
        return record_to_training_sample(record, config=self._config)

    def close(self) -> None:
        """关闭全部持久容器句柄。"""
        self._reader.close()


class RoboDMContainerBackend:
    """打开 prototype-only、非原生兼容的本地容器。"""

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> RoboDMContainerHandle:
        """返回本地容器句柄,不声明后端胜者。"""
        del stage
        return RoboDMContainerHandle(config)


def create_backend() -> RoboDMContainerBackend:
    """构造 RoboDM-container 后端实例。"""
    return RoboDMContainerBackend()


__all__ = ["RoboDMContainerBackend", "RoboDMContainerHandle", "create_backend"]
