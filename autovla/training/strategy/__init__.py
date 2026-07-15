"""AutoVLA CUDA-only 生产训练策略的轻量懒导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.training.session import PreparedTrainingSession as PreparedTrainingSession
    from autovla.training.session import TrainingStrategy as TrainingStrategy
    from autovla.training.strategy.deepspeed import DeepSpeedStrategy as DeepSpeedStrategy
    from autovla.training.strategy.deepspeed import (
        DeepSpeedTrainingSession as DeepSpeedTrainingSession,
    )
    from autovla.training.strategy.distributed_data_parallel import (
        DistributedDataParallelStrategy as DistributedDataParallelStrategy,
    )
    from autovla.training.strategy.distributed_data_parallel import (
        DistributedDataParallelTrainingSession as DistributedDataParallelTrainingSession,
    )
    from autovla.training.strategy.single_device import SingleDeviceStrategy as SingleDeviceStrategy
    from autovla.training.strategy.single_device import SingleGpuStrategy as SingleGpuStrategy
    from autovla.training.strategy.single_device import (
        SingleGpuTrainingSession as SingleGpuTrainingSession,
    )

_EXPORTS = {
    "DeepSpeedStrategy": "autovla.training.strategy.deepspeed",
    "DeepSpeedTrainingSession": "autovla.training.strategy.deepspeed",
    "DistributedDataParallelStrategy": "autovla.training.strategy.distributed_data_parallel",
    "DistributedDataParallelTrainingSession": "autovla.training.strategy.distributed_data_parallel",
    "PreparedTrainingSession": "autovla.training.session",
    "SingleDeviceStrategy": "autovla.training.strategy.single_device",
    "SingleGpuStrategy": "autovla.training.strategy.single_device",
    "SingleGpuTrainingSession": "autovla.training.strategy.single_device",
    "TrainingStrategy": "autovla.training.session",
}

__all__ = [
    "DeepSpeedStrategy",
    "DeepSpeedTrainingSession",
    "DistributedDataParallelStrategy",
    "DistributedDataParallelTrainingSession",
    "PreparedTrainingSession",
    "SingleDeviceStrategy",
    "SingleGpuStrategy",
    "SingleGpuTrainingSession",
    "TrainingStrategy",
]


def __getattr__(name: str) -> object:
    """仅在访问具体导出时加载其 canonical 模块。"""

    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共名称,不触发具体策略导入。"""

    return sorted(set(globals()) | set(__all__))
