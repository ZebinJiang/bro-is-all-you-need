"""生产训练策略抽象和公共状态语义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path

import torch
from torch import nn

from autovla.training.precision import PrecisionPolicy


class TrainingStrategy(ABC):
    """封装设备、进程、模型包装、梯度和分布式状态物化。"""

    def __init__(self, precision: PrecisionPolicy) -> None:
        """保存无副作用的精度配置。"""

        self.precision = precision
        self._device: torch.device | None = None

    @property
    def device(self) -> torch.device:
        """返回 setup 后的本地设备。"""

        if self._device is None:
            raise RuntimeError("training strategy is not set up")
        return self._device

    @property
    @abstractmethod
    def rank(self) -> int:
        """返回全局进程编号。"""

        raise NotImplementedError

    @property
    @abstractmethod
    def world_size(self) -> int:
        """返回进程总数。"""

        raise NotImplementedError

    @property
    def is_primary(self) -> bool:
        """返回当前进程是否负责本地可见输出。"""

        return self.rank == 0

    @abstractmethod
    def setup(self) -> None:
        """延迟建立设备和可选进程组。"""

        raise NotImplementedError

    @abstractmethod
    def prepare_model(self, model: nn.Module) -> nn.Module:
        """移动并按策略包装模型。"""

        raise NotImplementedError

    def prepare_optimizer(self, optimizer: torch.optim.Optimizer) -> torch.optim.Optimizer:
        """返回与已包装参数关联的优化器。"""

        return optimizer

    @property
    def requires_post_prepare_optimizer(self) -> bool:
        """声明具体优化器是否必须在模型准备后创建。"""

        return False

    def accumulation_context(
        self, model: nn.Module, *, synchronize: bool
    ) -> AbstractContextManager[None]:
        """返回微批次梯度同步上下文;单设备默认不操作。"""

        del model, synchronize
        return nullcontext()

    def scale_gradients(self, model: nn.Module, factor: float) -> None:
        """按实际累积窗口修正全部已有梯度。"""

        if factor <= 0.0:
            raise ValueError("gradient scale factor must be positive")
        for parameter in model.parameters():
            if parameter.grad is not None:
                parameter.grad.mul_(factor)

    def autocast(self) -> AbstractContextManager[None]:
        """返回精度策略上下文。"""

        return self.precision.autocast()

    def backward(self, loss: torch.Tensor) -> None:
        """执行缩放感知反向传播。"""

        self.precision.backward(loss)

    def unscale(self, optimizer: torch.optim.Optimizer) -> None:
        """在梯度裁剪前解除缩放。"""

        self.precision.unscale(optimizer)

    def optimizer_step(self, optimizer: torch.optim.Optimizer) -> bool:
        """执行优化器更新并报告是否真正更新。"""

        return self.precision.step(optimizer)

    @abstractmethod
    def all_finite(self, finite: bool) -> bool:
        """要求全部 rank 都观测到有限损失。"""

        raise NotImplementedError

    @abstractmethod
    def reduce_mean(self, value: float) -> float:
        """返回跨 rank 平均标量。"""

        raise NotImplementedError

    @abstractmethod
    def broadcast_text(self, value: str) -> str:
        """从主 rank 广播 checkpoint 等控制面文本。"""

        raise NotImplementedError

    @abstractmethod
    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """收集每个 rank 的数据游标和 RNG 状态。"""

        raise NotImplementedError

    def _validate_rank_runtime_states(
        self, states: Sequence[object]
    ) -> Mapping[str, Mapping[str, object]]:
        """验证收集结果数量、rank 覆盖和拓扑身份。"""

        if len(states) != self.world_size:
            raise RuntimeError("rank runtime state count does not match world size")
        collected: dict[str, Mapping[str, object]] = {}
        for expected_rank, value in enumerate(states):
            if not isinstance(value, Mapping):
                raise TypeError("rank runtime state payload must be a mapping")
            payload = dict(value)
            if payload.get("rank") != expected_rank or payload.get("world_size") != self.world_size:
                raise ValueError("rank runtime state topology does not match collective order")
            collected[str(expected_rank)] = payload
        expected = {str(rank) for rank in range(self.world_size)}
        if set(collected) != expected:
            raise RuntimeError("rank runtime state coverage is incomplete")
        return collected

    @abstractmethod
    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """裁剪模型梯度并返回总范数。"""

        raise NotImplementedError

    @abstractmethod
    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """物化可持久化模型状态。"""

        raise NotImplementedError

    @abstractmethod
    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """把已映射模型状态加载到策略包装模型。"""

        raise NotImplementedError

    def optimizer_state_dict(self, optimizer: torch.optim.Optimizer) -> Mapping[str, object]:
        """物化优化器状态。"""

        return optimizer.state_dict()

    def load_optimizer_state_dict(
        self, optimizer: torch.optim.Optimizer, state: Mapping[str, object]
    ) -> None:
        """恢复优化器状态。"""

        optimizer.load_state_dict(dict(state))

    def strategy_state_dict(self) -> Mapping[str, object]:
        """返回精度及策略身份状态。"""

        return {"name": type(self).__name__, "precision": self.precision.state_dict()}

    def load_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """校验策略身份并恢复精度状态。"""

        if state.get("name") != type(self).__name__:
            raise ValueError("checkpoint strategy does not match current strategy")
        precision = state.get("precision")
        if not isinstance(precision, dict):
            raise ValueError("checkpoint strategy lacks precision state")
        self.precision.load_state_dict(precision)

    @abstractmethod
    def barrier(self) -> None:
        """同步全部进程。"""

        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """释放策略拥有的进程资源。"""

        raise NotImplementedError


def require_local_checkpoint_root(path: Path) -> Path:
    """要求 checkpoint 位于本地绝对路径。"""

    if not path.is_absolute():
        raise ValueError("checkpoint path must be absolute")
    return path


__all__ = ["TrainingStrategy", "require_local_checkpoint_root"]
