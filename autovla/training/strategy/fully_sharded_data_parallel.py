"""基于 PyTorch composable FSDP2 的生产训练策略。"""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

import torch
from torch import distributed as dist
from torch import nn

from autovla.training.precision import PrecisionPolicy
from autovla.training.strategy.base import CheckpointCollectiveStatus, TrainingStrategy

if TYPE_CHECKING:
    from torch.distributed.checkpoint.state_dict import OptimizerStateType, ValueType


@runtime_checkable
class _FullyShard(Protocol):
    """约束 Torch 2.5/2.6 composable FSDP2 入口。"""

    def __call__(
        self,
        module: nn.Module,
        *,
        reshard_after_forward: bool,
    ) -> object: ...


@runtime_checkable
class _GradientSyncControl(Protocol):
    """约束 FSDP2 注入的梯度同步控制方法。"""

    def set_requires_gradient_sync(self, requires_sync: bool) -> None: ...


@runtime_checkable
class _AllReduce(Protocol):
    """约束 Torch 分布式标量 reduction 调用。"""

    def __call__(self, tensor: torch.Tensor, *, op: object) -> object: ...


@runtime_checkable
class _AllGatherObject(Protocol):
    """约束 Torch 分布式对象收集调用。"""

    def __call__(self, output: list[object], value: object) -> object: ...


@runtime_checkable
class _Barrier(Protocol):
    """约束 Torch 分布式 barrier 调用。"""

    def __call__(self) -> object: ...


@runtime_checkable
class _NamedModuleProvider(Protocol):
    """约束模型模块遍历接口的返回类型。"""

    def named_modules(self) -> Iterator[tuple[str, nn.Module]]: ...


@runtime_checkable
class _DcpOperation(Protocol):
    """约束 DCP 保存和加载函数的共同调用面。"""

    def __call__(
        self,
        state_dict: dict[str, object],
        *,
        checkpoint_id: str,
    ) -> object: ...


@runtime_checkable
class _LoadPlanner(Protocol):
    """约束 DCP 加载计划的公开校验接口。"""

    def set_up_planner(
        self,
        state_dict: dict[str, object],
        *,
        metadata: object,
        is_coordinator: bool,
    ) -> None: ...

    def create_local_plan(self) -> object: ...


def _require_named_module_provider(value: object) -> _NamedModuleProvider:
    """校验并收窄模型模块遍历接口。"""

    if not isinstance(value, _NamedModuleProvider):
        raise TypeError("FSDP2 model does not expose named_modules")
    return value


def _require_load_planner(value: object) -> _LoadPlanner:
    """校验并收窄 DCP 加载计划接口。"""

    if not isinstance(value, _LoadPlanner):
        raise RuntimeError("Torch DCP load planner lacks the required interface")
    return value


def _resolve_fully_shard() -> _FullyShard:
    """从 Torch 2.5/2.6 公共命名空间解析 FSDP2 入口。"""

    module: object = importlib.import_module("torch.distributed._composable.fsdp")
    operation: object = getattr(module, "fully_shard", None)
    if not isinstance(operation, _FullyShard):
        raise RuntimeError("Torch composable FSDP2 fully_shard is unavailable")
    return operation


def _distributed_all_reduce(tensor: torch.Tensor, *, op: object) -> None:
    """通过运行时校验的 Torch 公共属性执行 reduction。"""

    operation: object = getattr(dist, "all_reduce", None)
    if not isinstance(operation, _AllReduce):
        raise RuntimeError("torch.distributed.all_reduce is unavailable")
    operation(tensor, op=op)


def _distributed_all_gather_object(output: list[object], value: object) -> None:
    """通过运行时校验的 Torch 公共属性收集对象。"""

    operation: object = getattr(dist, "all_gather_object", None)
    if not isinstance(operation, _AllGatherObject):
        raise RuntimeError("torch.distributed.all_gather_object is unavailable")
    operation(output, value)


def _distributed_barrier() -> None:
    """通过运行时校验的 Torch 公共属性执行 barrier。"""

    operation: object = getattr(dist, "barrier", None)
    if not isinstance(operation, _Barrier):
        raise RuntimeError("torch.distributed.barrier is unavailable")
    operation()


def _run_dcp_operation(
    module_name: str,
    operation_name: str,
    state: dict[str, object],
    path: Path,
) -> None:
    """通过运行时协议边界调用 Torch DCP 保存或加载函数。"""

    module: object = importlib.import_module(module_name)
    operation: object = getattr(module, operation_name, None)
    if not isinstance(operation, _DcpOperation):
        raise RuntimeError(f"Torch DCP operation is unavailable: {operation_name}")
    operation(state, checkpoint_id=str(path))


def _require_broadcast_text(value: object) -> str:
    """校验对象广播结果为非空文本。"""

    if not isinstance(value, str) or not value:
        raise RuntimeError("FSDP2 broadcast returned invalid text")
    return value


def _parse_torchrun_topology(environment: Mapping[str, str]) -> tuple[int, int, int]:
    """严格解析 torchrun 的 ASCII 十进制进程拓扑。"""

    required = ("RANK", "WORLD_SIZE", "LOCAL_RANK")
    missing = [name for name in required if name not in environment]
    if missing:
        raise RuntimeError(f"FSDP2 requires torchrun variables: {missing}")
    parsed: dict[str, int] = {}
    for name in required:
        raw = environment[name]
        if not raw or any(character < "0" or character > "9" for character in raw):
            raise ValueError(f"FSDP2 torchrun {name} must be nonempty ASCII decimal digits")
        parsed[name] = int(raw)
    rank = parsed["RANK"]
    world_size = parsed["WORLD_SIZE"]
    local_rank = parsed["LOCAL_RANK"]
    if world_size <= 0:
        raise ValueError("FSDP2 torchrun WORLD_SIZE must be positive")
    if rank < 0 or rank >= world_size:
        raise ValueError("FSDP2 torchrun RANK must be in [0, WORLD_SIZE)")
    if local_rank < 0:
        raise ValueError("FSDP2 torchrun LOCAL_RANK must be non-negative")
    return rank, world_size, local_rank


class FullyShardedDataParallelStrategy(TrainingStrategy):
    """按叶到根顺序应用 composable ``fully_shard`` 并管理 DTensor 状态。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        expected_world_size: int,
        module_filter: Callable[[str, nn.Module], bool],
        backend: str | None = None,
        timeout_seconds: int = 1800,
        reshard_after_forward: bool = True,
    ) -> None:
        """保存 FSDP2 分片选择器和期望拓扑,不初始化运行时。"""

        super().__init__(precision)
        if expected_world_size <= 0:
            raise ValueError("training.distributed.world_size must be positive")
        self._expected_world_size = expected_world_size
        self._module_filter = module_filter
        self._backend = backend
        self._timeout_seconds = timeout_seconds
        self._reshard_after_forward = reshard_after_forward
        self._rank = 0
        self._local_rank = 0
        self._world_size = 1
        self._owns_process_group = False
        self._prepared_model: nn.Module | None = None
        self._wrapped_module_names: tuple[str, ...] = ()

    @property
    def rank(self) -> int:
        """返回全局 rank。"""

        return self._rank

    @property
    def local_rank(self) -> int:
        """返回 torchrun 节点内 rank。"""

        return self._local_rank

    @property
    def world_size(self) -> int:
        """返回进程总数。"""

        return self._world_size

    def setup(self) -> None:
        """按 torchrun 环境延迟建立 CUDA 进程组。"""

        rank, world_size, local_rank = _parse_torchrun_topology(os.environ)
        if world_size != self._expected_world_size:
            raise ValueError("training.distributed.world_size does not match torchrun WORLD_SIZE")
        if not torch.cuda.is_available():
            raise RuntimeError("FSDP2 production strategy requires CUDA")
        self._rank = rank
        self._local_rank = local_rank
        self._world_size = world_size
        self._device = torch.device("cuda", local_rank)
        torch.cuda.set_device(self.device)
        if not dist.is_initialized():
            dist.init_process_group(
                backend=self._backend or "nccl",
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
        """将选中子模块按叶到根顺序分片,最终分片根模型。"""

        model.to(self.device)
        fully_shard = _resolve_fully_shard()
        provider = _require_named_module_provider(model)
        selected: list[tuple[str, nn.Module]] = []
        for name, module in provider.named_modules():
            if name and self._module_filter(name, module):
                selected.append((name, module))
        if not selected:
            raise RuntimeError("FSDP2 production module selector matched no modules")
        for _, module in reversed(selected):
            fully_shard(module, reshard_after_forward=self._reshard_after_forward)
        fully_shard(model, reshard_after_forward=self._reshard_after_forward)
        self._wrapped_module_names = (*(name for name, _ in selected), "<root>")
        self._prepared_model = model
        return model

    @property
    def requires_post_prepare_optimizer(self) -> bool:
        """FSDP2 必须针对分片后的参数身份创建优化器。"""

        return True

    @contextmanager
    def accumulation_context(self, model: nn.Module, *, synchronize: bool):
        """在非边界微批次关闭 composable FSDP2 梯度同步。"""

        prepared = self._require_model(model)
        if synchronize:
            yield
            return
        if not isinstance(prepared, _GradientSyncControl):
            raise RuntimeError("prepared FSDP2 model lacks gradient sync control")
        prepared.set_requires_gradient_sync(False)
        try:
            yield
        finally:
            prepared.set_requires_gradient_sync(True)

    def _require_model(self, model: nn.Module) -> nn.Module:
        """确认状态操作针对本策略已分片模型。"""

        if model is not self._prepared_model:
            raise TypeError("FSDP2 strategy received an unprepared model")
        return model

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """使用 composable FSDP2 的分布式梯度范数裁剪。"""

        prepared = self._require_model(model)
        norm = torch.nn.utils.clip_grad_norm_(prepared.parameters(), max_norm)
        return float(norm.item())

    def all_finite(self, finite: bool) -> bool:
        """用 MIN reduction 要求全部 FSDP2 rank 的损失有限。"""

        flag = torch.tensor(int(finite), device=self.device, dtype=torch.int32)
        _distributed_all_reduce(flag, op=dist.ReduceOp.MIN)
        return bool(flag.item())

    def reduce_mean(self, value: float) -> float:
        """计算跨 FSDP2 rank 平均标量。"""

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
        """拒绝把 FSDP2 状态聚合进 rank-zero ``state.pt``。"""

        self._require_model(model)
        raise RuntimeError("FSDP2 model state must use the distributed sharded checkpoint boundary")

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """拒绝从 rank-zero ``state.pt`` 恢复 FSDP2 模型。"""

        del state
        self._require_model(model)
        raise RuntimeError("FSDP2 model state must use the distributed sharded checkpoint boundary")

    def optimizer_state_dict(self, optimizer: torch.optim.Optimizer) -> Mapping[str, object]:
        """拒绝把 FSDP2 优化器聚合进 rank-zero ``state.pt``。"""

        del optimizer
        raise RuntimeError(
            "FSDP2 optimizer state must use the distributed sharded checkpoint boundary"
        )

    def load_optimizer_state_dict(
        self, optimizer: torch.optim.Optimizer, state: Mapping[str, object]
    ) -> None:
        """拒绝从 rank-zero ``state.pt`` 恢复 FSDP2 优化器。"""

        del optimizer, state
        raise RuntimeError(
            "FSDP2 optimizer state must use the distributed sharded checkpoint boundary"
        )

    @property
    def uses_sharded_checkpoint(self) -> bool:
        """声明模型和优化器由公共 DCP 分片目录保存。"""

        return True

    @staticmethod
    def _require_supported_dcp() -> None:
        """将 FSDP2 checkpoint API 限定到已审核的 Torch 2.5/2.6。"""

        version = torch.__version__.split("+", 1)[0].split(".")
        if len(version) < 2 or tuple(map(int, version[:2])) not in {(2, 5), (2, 6)}:
            raise RuntimeError(
                "FSDP2 checkpoint source supports Torch 2.5/2.6 only; "
                "classification=SOURCE_IMPLEMENTED/DISTRIBUTED_RUNTIME_NOT_EXECUTED"
            )

    def _sharded_state(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> tuple[dict[str, ValueType], OptimizerStateType]:
        """通过公开 state-dict API 返回 DTensor 模型和优化器状态。"""

        self._require_supported_dcp()
        from torch.distributed.checkpoint.state_dict import (
            StateDictOptions,
            get_model_state_dict,
            get_optimizer_state_dict,
        )

        prepared = self._require_model(model)
        options = StateDictOptions(full_state_dict=False, cpu_offload=False)
        return (
            get_model_state_dict(prepared, options=options),
            get_optimizer_state_dict(prepared, optimizer, options=options),
        )

    def save_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """由全部 rank 使用公共 DCP API 保存 DTensor 分片。"""

        self._require_supported_dcp()
        model_state, optimizer_state = self._sharded_state(model, optimizer)
        state: dict[str, object] = {"model": model_state, "optimizer": optimizer_state}
        _run_dcp_operation(
            "torch.distributed.checkpoint.state_dict_saver",
            "save",
            state,
            path,
        )
        return {
            "storage": "distributed_sharded",
            "torch_version": torch.__version__,
            "wrapped_modules": self._wrapped_module_names,
            "state_dict_mode": "full_state_dict=false,cpu_offload=false",
            "world_size": self.world_size,
        }

    def validate_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """读取 DCP metadata 并验证模型/优化器分片命名空间。"""

        self._require_supported_dcp()
        self._require_model(model)
        from torch.distributed.checkpoint.default_planner import DefaultLoadPlanner
        from torch.distributed.checkpoint.filesystem import FileSystemReader

        metadata = FileSystemReader(str(path)).read_metadata()
        keys = tuple(sorted(str(key) for key in metadata.state_dict_metadata))
        if not any(key == "model" or key.startswith("model.") for key in keys):
            raise ValueError("FSDP2 checkpoint metadata lacks model state")
        if not any(key == "optimizer" or key.startswith("optimizer.") for key in keys):
            raise ValueError("FSDP2 checkpoint metadata lacks optimizer state")
        planner = _require_load_planner(DefaultLoadPlanner())
        model_state, optimizer_state = self._sharded_state(model, optimizer)
        state: dict[str, object] = {"model": model_state, "optimizer": optimizer_state}
        planner.set_up_planner(
            state,
            metadata=metadata,
            is_coordinator=self.is_primary,
        )
        planner.create_local_plan()
        return {
            "storage": "distributed_sharded",
            "metadata_key_count": len(keys),
            "wrapped_modules": self._wrapped_module_names,
            "world_size": self.world_size,
        }

    def load_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        """由全部 rank 使用公共 DCP 和 state-dict API 恢复分片。"""

        self._require_supported_dcp()
        from torch.distributed.checkpoint.state_dict import (
            StateDictOptions,
            set_model_state_dict,
            set_optimizer_state_dict,
        )

        prepared = self._require_model(model)
        model_state, optimizer_state = self._sharded_state(model, optimizer)
        state: dict[str, object] = {"model": model_state, "optimizer": optimizer_state}
        _run_dcp_operation(
            "torch.distributed.checkpoint.state_dict_loader",
            "load",
            state,
            path,
        )
        options = StateDictOptions(full_state_dict=False, cpu_offload=False)
        set_model_state_dict(
            prepared,
            model_state_dict=model_state,
            options=options,
        )
        set_optimizer_state_dict(
            prepared,
            optimizer,
            optim_state_dict=optimizer_state,
            options=options,
        )

    def gather_checkpoint_status(
        self,
        status: CheckpointCollectiveStatus,
    ) -> tuple[CheckpointCollectiveStatus, ...]:
        """用仅含标量的有界载荷收集全部 rank 的 checkpoint 结果。"""

        if status.rank != self.rank:
            raise RuntimeError("local checkpoint status rank does not match FSDP2 rank")
        payloads: list[object] = [None for _ in range(self.world_size)]
        _distributed_all_gather_object(payloads, status.to_payload())
        return tuple(CheckpointCollectiveStatus.from_payload(payload) for payload in payloads)

    def barrier(self) -> None:
        """同步当前 FSDP2 进程组。"""

        if dist.is_initialized():
            _distributed_barrier()

    def close(self) -> None:
        """释放本策略创建的进程组和模型引用。"""

        self._prepared_model = None
        self._wrapped_module_names = ()
        if self._owns_process_group and dist.is_initialized():
            dist.destroy_process_group()
        self._owns_process_group = False
        self._device = None


__all__ = ["FullyShardedDataParallelStrategy"]
