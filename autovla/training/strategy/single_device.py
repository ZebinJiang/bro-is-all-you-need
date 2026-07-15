"""CUDA-only 单 GPU 生产策略与 session。"""

from __future__ import annotations

import warnings
from collections.abc import Mapping

import torch
from torch import nn

from autovla.config.schema.training import TrainingConfig
from autovla.training.precision import PrecisionPolicy
from autovla.training.session import (
    NativePreparedTrainingSession,
    OptimizerFactory,
    SchedulerFactory,
    TrainingTopology,
)


class SingleGpuTrainingSession(NativePreparedTrainingSession):
    """在一个显式 CUDA 设备上执行 native PyTorch 训练。"""

    def __init__(self, precision: PrecisionPolicy, *, config: TrainingConfig) -> None:
        """固定到 ``cuda:0`` 并保存统一 native session 配置。"""

        topology = TrainingTopology(
            rank=0,
            local_rank=0,
            world_size=1,
            backend="none",
            device_index=0,
            node_rank=0,
            local_world_size=1,
            launcher="direct",
            strategy="single_gpu",
        )
        super().__init__(precision, config=config, topology=topology)
        self._device = torch.device("cuda", 0)

    @property
    def rank(self) -> int:
        """单 GPU rank 固定为零。"""

        return 0

    @property
    def local_rank(self) -> int:
        """单 GPU local rank 固定为零。"""

        return 0

    @property
    def world_size(self) -> int:
        """单 GPU world size 固定为一。"""

        return 1

    def setup(self) -> None:
        """验证 CUDA 并初始化精度策略。"""

        if not torch.cuda.is_available():
            raise RuntimeError("single_gpu requires an available CUDA device")
        torch.cuda.set_device(self.device)
        self.precision.setup(self.device)

    def prepare_model(self, model: nn.Module) -> nn.Module:
        """把模型一次移动到本地 CUDA 设备。"""

        return model.to(self.device)

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """裁剪全部可训练参数并返回全局范数。"""

        return float(torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm).item())

    def all_finite(self, finite: bool) -> bool:
        """单 GPU 直接返回有限性判断。"""

        return finite

    def reduce_mean(self, value: float) -> float:
        """单 GPU 直接返回输入标量。"""

        return value

    def broadcast_text(self, value: str) -> str:
        """单 GPU 直接返回控制文本。"""

        return value

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """返回唯一 rank 的 DataModule 与 RNG 状态。"""

        return self._validate_rank_runtime_states((local_state,))

    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """物化普通模型状态。"""

        return model.state_dict()

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """严格恢复普通模型状态。"""

        model.load_state_dict(dict(state), strict=True)

    def barrier(self) -> None:
        """单 GPU 无需 collective。"""

        return None

    def close(self) -> None:
        """释放 session 引用但不重置全局 CUDA runtime。"""

        if self._accumulation_context is not None:
            raise RuntimeError("cannot close session during forward/backward")
        self._model = None
        self._optimizer = None
        self._scheduler = None
        self._device = None


class SingleGpuStrategy:
    """准备唯一 CUDA 单 GPU session。"""

    def __init__(self, precision: PrecisionPolicy) -> None:
        """保存精度策略,构造阶段不初始化 CUDA。"""

        self._precision = precision
        self._topology = TrainingTopology(
            rank=0,
            local_rank=0,
            world_size=1,
            backend="none",
            device_index=0,
            node_rank=0,
            local_world_size=1,
            launcher="direct",
            strategy="single_gpu",
        )

    @property
    def name(self) -> str:
        """返回规范策略键。"""

        return "single_gpu"

    @property
    def topology(self) -> TrainingTopology:
        """返回单 GPU 拓扑。"""

        return self._topology

    def configure_process_environment(self) -> None:
        """在模型构造前验证并绑定 ``cuda:0``。"""

        if not torch.cuda.is_available():
            raise RuntimeError("single_gpu requires an available CUDA device")
        torch.cuda.set_device(0)

    def prepare(
        self,
        *,
        model: nn.Module,
        config: TrainingConfig,
        optimizer_factory: OptimizerFactory,
        scheduler_factory: SchedulerFactory,
        batches_per_epoch: int,
    ) -> SingleGpuTrainingSession:
        """按模型、优化器、调度器顺序构造统一 session。"""

        session = SingleGpuTrainingSession(self._precision, config=config)
        session.setup()
        prepared = session.prepare_model(model)
        optimizer = optimizer_factory(prepared)
        scheduler = scheduler_factory(optimizer, batches_per_epoch)
        session.bind(prepared, optimizer, scheduler)
        return session


class SingleDeviceStrategy(SingleGpuStrategy):
    """保留 ``single_device`` 导入名的显式弃用兼容层。"""

    def __init__(self, precision: PrecisionPolicy, *args: object, **kwargs: object) -> None:
        """告警后强制迁移到 CUDA-only ``single_gpu``。"""

        if args or kwargs:
            raise ValueError("SingleDeviceStrategy no longer accepts a device override")
        warnings.warn(
            "SingleDeviceStrategy is deprecated; use SingleGpuStrategy",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(precision)


__all__ = ["SingleDeviceStrategy", "SingleGpuStrategy", "SingleGpuTrainingSession"]
