"""AutoVLA 本地 LeRobot 后端。"""

from autovla.config.schema import DatasetConfig
from autovla.data.datasets.local_lerobot import LocalLeRobotDataset
from autovla.data.types import DataStage


class LeRobotLocalBackend:
    """只打开完整本地 LeRobot 数据集,不提供网络回退。"""

    def open_dataset(self, config: DatasetConfig, stage: DataStage) -> LocalLeRobotDataset:
        """验证阶段后构造本地数据集句柄。"""
        del stage
        return LocalLeRobotDataset(config)


def create_backend() -> LeRobotLocalBackend:
    """构造本地 LeRobot 后端。"""
    return LeRobotLocalBackend()


__all__ = ["LeRobotLocalBackend", "create_backend"]
