"""PyTorch DistributedDataParallel 生产策略。"""

from __future__ import annotations

import os
from collections.abc import Mapping
from datetime import timedelta
from typing import Protocol, runtime_checkable

import torch
from torch import distributed as dist
from torch import nn
from torch.nn.parallel import DistributedDataParallel

from autovla.training.precision import PrecisionPolicy
from autovla.training.strategy.base import TrainingStrategy


@runtime_checkable
class _AllReduce(Protocol):
    """约束 Torch 分布式标量 reduction 调用。"""

    def __call__(self, tensor: torch.Tensor, *, op: object) -> object: ...


@runtime_checkable
class _Barrier(Protocol):
    """约束 Torch 分布式 barrier 调用。"""

    def __call__(self) -> object: ...


def _distributed_all_reduce(tensor: torch.Tensor, *, op: object) -> None:
    """通过运行时校验的 Torch 公共属性执行 reduction。"""

    operation: object = getattr(dist, "all_reduce", None)
    if not isinstance(operation, _AllReduce):
        raise RuntimeError("torch.distributed.all_reduce is unavailable")
    operation(tensor, op=op)


def _distributed_barrier() -> None:
    """通过运行时校验的 Torch 公共属性执行 barrier。"""

    operation: object = getattr(dist, "barrier", None)
    if not isinstance(operation, _Barrier):
        raise RuntimeError("torch.distributed.barrier is unavailable")
    operation()


def _require_broadcast_text(value: object) -> str:
    """校验对象广播结果为非空文本。"""

    if not isinstance(value, str) or not value:
        raise RuntimeError("DDP broadcast returned invalid text")
    return value


def _parse_torchrun_topology(environment: Mapping[str, str]) -> tuple[int, int, int]:
    """严格解析 torchrun 的 ASCII 十进制进程拓扑。"""

    required = ("RANK", "WORLD_SIZE", "LOCAL_RANK")
    missing = [name for name in required if name not in environment]
    if missing:
        raise RuntimeError(f"DDP requires torchrun variables: {missing}")
    parsed: dict[str, int] = {}
    for name in required:
        raw = environment[name]
        if not raw or any(character < "0" or character > "9" for character in raw):
            raise ValueError(f"DDP torchrun {name} must be nonempty ASCII decimal digits")
        parsed[name] = int(raw)
    rank = parsed["RANK"]
    world_size = parsed["WORLD_SIZE"]
    local_rank = parsed["LOCAL_RANK"]
    if world_size <= 0:
        raise ValueError("DDP torchrun WORLD_SIZE must be positive")
    if rank < 0 or rank >= world_size:
        raise ValueError("DDP torchrun RANK must be in [0, WORLD_SIZE)")
    if local_rank < 0:
        raise ValueError("DDP torchrun LOCAL_RANK must be non-negative")
    return rank, world_size, local_rank


class DistributedDataParallelStrategy(TrainingStrategy):
    """按 torchrun 环境显式初始化进程组并包装 DDP 模型。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        expected_world_size: int,
        backend: str | None = None,
        timeout_seconds: int = 1800,
        gradient_as_bucket_view: bool = True,
        find_unused_parameters: bool = False,
    ) -> None:
        """保存 DDP 配置和期望拓扑,构造阶段不初始化 distributed。"""

        super().__init__(precision)
        if expected_world_size <= 0:
            raise ValueError("training.distributed.world_size must be positive")
        self._expected_world_size = expected_world_size
        self._backend = backend
        self._timeout_seconds = timeout_seconds
        self._gradient_as_bucket_view = gradient_as_bucket_view
        self._find_unused_parameters = find_unused_parameters
        self._rank = 0
        self._local_rank = 0
        self._world_size = 1
        self._owns_process_group = False

    @property
    def rank(self) -> int:
        """返回 torchrun 全局 rank。"""

        return self._rank

    @property
    def local_rank(self) -> int:
        """返回 torchrun 节点内 rank。"""

        return self._local_rank

    @property
    def world_size(self) -> int:
        """返回 torchrun world size。"""

        return self._world_size

    def setup(self) -> None:
        """从显式环境变量建立设备和进程组。"""

        rank, world_size, local_rank = _parse_torchrun_topology(os.environ)
        if world_size != self._expected_world_size:
            raise ValueError("training.distributed.world_size does not match torchrun WORLD_SIZE")
        self._rank = rank
        self._local_rank = local_rank
        self._world_size = world_size
        use_cuda = torch.cuda.is_available()
        self._device = torch.device("cuda", local_rank) if use_cuda else torch.device("cpu")
        if use_cuda:
            torch.cuda.set_device(self.device)
        if not dist.is_initialized():
            dist.init_process_group(
                backend=self._backend or ("nccl" if use_cuda else "gloo"),
                timeout=timedelta(seconds=self._timeout_seconds),
            )
            self._owns_process_group = True
        if (
            dist.get_world_size() != self._expected_world_size
            or dist.get_world_size() != self._world_size
            or dist.get_rank() != self._rank
        ):
            raise RuntimeError("initialized process group does not match torchrun topology")
        self.precision.setup(self.device)

    def prepare_model(self, model: nn.Module) -> nn.Module:
        """移动模型并构造 DDP 包装器。"""

        model = model.to(self.device)
        device_ids = [self.device.index] if self.device.type == "cuda" else None
        return DistributedDataParallel(
            model,
            device_ids=device_ids,
            gradient_as_bucket_view=self._gradient_as_bucket_view,
            find_unused_parameters=self._find_unused_parameters,
        )

    def accumulation_context(self, model: nn.Module, *, synchronize: bool):
        """在非边界微批次关闭 DDP 梯度 all-reduce。"""

        prepared = model
        if not isinstance(prepared, DistributedDataParallel):
            raise TypeError("DDP accumulation requires a prepared model")
        return (
            prepared.no_sync()
            if not synchronize
            else super().accumulation_context(model, synchronize=True)
        )

    @staticmethod
    def _module(model: nn.Module) -> nn.Module:
        """返回 DDP 内部模型并拒绝错误包装。"""

        if not isinstance(model, DistributedDataParallel):
            raise TypeError("DDP strategy requires a DistributedDataParallel model")
        module: object = getattr(model, "module", None)
        if not isinstance(module, nn.Module):
            raise TypeError("DDP wrapper lacks an nn.Module payload")
        return module

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """裁剪 DDP 内部参数梯度。"""

        return float(
            torch.nn.utils.clip_grad_norm_(self._module(model).parameters(), max_norm).item()
        )

    def all_finite(self, finite: bool) -> bool:
        """用 MIN reduction 要求全部 rank 的损失有限。"""

        flag = torch.tensor(int(finite), device=self.device, dtype=torch.int32)
        _distributed_all_reduce(flag, op=dist.ReduceOp.MIN)
        return bool(flag.item())

    def reduce_mean(self, value: float) -> float:
        """计算跨 rank 平均标量。"""

        tensor = torch.tensor(value, device=self.device, dtype=torch.float64)
        _distributed_all_reduce(tensor, op=dist.ReduceOp.SUM)
        return float((tensor / self.world_size).item())

    def broadcast_text(self, value: str) -> str:
        """从 rank 0 广播 checkpoint 控制面文本。"""

        values = [value if self.is_primary else ""]
        dist.broadcast_object_list(values, src=0, device=self.device)
        return _require_broadcast_text(values[0])

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """用一次对象集合在主 rank 收齐全部运行时状态。"""

        gathered: list[object] | None = (
            [object() for _ in range(self.world_size)] if self.is_primary else None
        )
        dist.gather_object(dict(local_state), gathered, dst=0)
        if gathered is None:
            return None
        return self._validate_rank_runtime_states(gathered)

    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """物化无 ``module.`` 前缀的完整模型状态。"""

        return self._module(model).state_dict()

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """严格加载无包装器前缀的模型状态。"""

        self._module(model).load_state_dict(dict(state), strict=True)

    def barrier(self) -> None:
        """同步当前进程组。"""

        if dist.is_initialized():
            _distributed_barrier()

    def close(self) -> None:
        """仅销毁本策略创建的进程组。"""

        if self._owns_process_group and dist.is_initialized():
            dist.destroy_process_group()
        self._owns_process_group = False
        self._device = None


__all__ = ["DistributedDataParallelStrategy"]
