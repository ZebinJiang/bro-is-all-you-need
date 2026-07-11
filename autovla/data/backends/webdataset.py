"""AutoVLA 本地 WebDataset 适配器。"""

from pathlib import Path

from autovla.config.schema import DatasetConfig
from autovla.data.backends.base import local_sample_count, record_to_training_sample
from autovla.data.types import DataStage, TrainingSample


class WebDatasetHandle:
    """通过现有顺序 reader 读取本地 TAR shards。"""

    def __init__(self, config: DatasetConfig) -> None:
        """记录配置并懒建现有 WebDataset reader。"""
        from autovla.dataloader.stores.webdataset_reader import WebDatasetSequentialReader

        self._config = config
        self._count = local_sample_count(Path(config.root), config.sample_count)
        self._reader = WebDatasetSequentialReader(Path(config.root))
        self._next_index = 0

    @property
    def name(self) -> str:
        """返回数据集名称。"""
        return self._config.name

    def __len__(self) -> int:
        """返回索引样本数。"""
        return self._count

    def read(self, index: int) -> TrainingSample:
        """向前扫描到分区索引并转换为规范样本。"""
        if index < 0 or index >= self._count:
            raise IndexError(index)
        if index < self._next_index:
            from autovla.dataloader.stores.webdataset_reader import WebDatasetSequentialReader

            self._reader.close()
            self._reader = WebDatasetSequentialReader(Path(self._config.root))
            self._next_index = 0
        read_count = index - self._next_index + 1
        record = self._reader.read_next(read_count)[-1]
        self._next_index = index + 1
        return record_to_training_sample(record, config=self._config)

    def close(self) -> None:
        """关闭顺序 reader。"""
        self._reader.close()


class WebDatasetBackend:
    """打开显式本地 WebDataset artifact。"""

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> WebDatasetHandle:
        """验证阶段后返回本地数据集句柄。"""
        del stage
        return WebDatasetHandle(config)


def create_backend() -> WebDatasetBackend:
    """构造 WebDataset 后端实例。"""
    return WebDatasetBackend()


__all__ = ["WebDatasetBackend", "WebDatasetHandle", "create_backend"]
