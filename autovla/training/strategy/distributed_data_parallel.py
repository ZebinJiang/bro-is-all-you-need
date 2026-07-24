"""CUDA/NCCL DistributedDataParallel 生产策略与 session。"""

from __future__ import annotations

import os
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from datetime import timedelta
from typing import Protocol, cast

import torch
from torch import distributed as dist
from torch import nn
from torch.nn.parallel import DistributedDataParallel

from autovla.config.schema.training import TrainingConfig
from autovla.training.precision import PrecisionPolicy
from autovla.training.session import (
    NativePreparedTrainingSession,
    OptimizerFactory,
    SchedulerFactory,
    TrainingTopology,
)
from autovla.training.strategy.base import CheckpointCollectiveStatus


class _DistributedCollectives(Protocol):
    """收窄 Torch 未完整标注的 collective 模块面。"""

    def all_reduce(self, tensor: torch.Tensor, *, op: object) -> object: ...

    def all_gather_object(self, output: list[object], value: object) -> None: ...

    def barrier(self) -> object: ...


_collectives = cast(_DistributedCollectives, cast(object, dist))


def _parse_decimal(environment: Mapping[str, str], names: tuple[str, ...]) -> dict[str, int]:
    """严格解析一组非空 ASCII 十进制环境变量。"""

    missing = [name for name in names if name not in environment]
    if missing:
        raise RuntimeError(f"distributed launcher requires variables: {missing}")
    parsed: dict[str, int] = {}
    for name in names:
        raw = environment[name]
        if not raw or any(character < "0" or character > "9" for character in raw):
            raise ValueError(f"distributed launcher {name} must be nonempty ASCII decimal digits")
        parsed[name] = int(raw)
    return parsed


def _parse_slurm_local_world_size(raw: str) -> int:
    """解析 Slurm 均匀 ``SLURM_NTASKS_PER_NODE`` 表示。"""

    count, marker, repetition = raw.partition("(x")
    if not count or any(character < "0" or character > "9" for character in count):
        raise ValueError("SLURM_NTASKS_PER_NODE must describe one uniform task count")
    if marker and (
        not repetition.endswith(")")
        or not repetition[:-1]
        or any(character < "0" or character > "9" for character in repetition[:-1])
    ):
        raise ValueError("SLURM_NTASKS_PER_NODE has an invalid repetition suffix")
    return int(count)


def _parse_master_endpoint(environment: Mapping[str, str]) -> tuple[str, int]:
    """严格解析 torch.distributed 共享的 rendezvous 主地址和端口。"""

    missing = [name for name in ("MASTER_ADDR", "MASTER_PORT") if name not in environment]
    if missing:
        raise RuntimeError(f"distributed launcher requires variables: {missing}")
    address = environment["MASTER_ADDR"]
    if not address.strip() or any(character.isspace() for character in address):
        raise ValueError("distributed launcher MASTER_ADDR must be non-empty without whitespace")
    port = _parse_decimal(environment, ("MASTER_PORT",))["MASTER_PORT"]
    if not 1 <= port <= 65535:
        raise ValueError("distributed launcher MASTER_PORT must be in [1, 65535]")
    return address, port


def _parse_distributed_topology(
    environment: Mapping[str, str],
    *,
    strategy: str,
) -> TrainingTopology:
    """从标准 torchrun 或 Slurm 环境构造统一 CUDA 拓扑。"""

    torchrun_names = ("RANK", "WORLD_SIZE", "LOCAL_RANK", "LOCAL_WORLD_SIZE", "GROUP_RANK")
    slurm_names = ("SLURM_PROCID", "SLURM_NTASKS", "SLURM_LOCALID", "SLURM_NODEID")
    if any(name in environment for name in torchrun_names):
        parsed = _parse_decimal(environment, torchrun_names)
        rank = parsed["RANK"]
        world_size = parsed["WORLD_SIZE"]
        local_rank = parsed["LOCAL_RANK"]
        local_world_size = parsed["LOCAL_WORLD_SIZE"]
        node_rank = parsed["GROUP_RANK"]
        launcher = "torchrun"
        launch_run_id = environment.get("TORCHELASTIC_RUN_ID") or environment.get("SLURM_JOB_ID")
    elif any(name in environment for name in slurm_names):
        parsed = _parse_decimal(environment, slurm_names)
        rank = parsed["SLURM_PROCID"]
        world_size = parsed["SLURM_NTASKS"]
        local_rank = parsed["SLURM_LOCALID"]
        node_rank = parsed["SLURM_NODEID"]
        raw_local_world_size = environment.get("SLURM_NTASKS_PER_NODE")
        if raw_local_world_size is None:
            raise RuntimeError("distributed launcher requires variables: ['SLURM_NTASKS_PER_NODE']")
        local_world_size = _parse_slurm_local_world_size(raw_local_world_size)
        launcher = "slurm"
        launch_run_id = environment.get("SLURM_JOB_ID")
    else:
        raise RuntimeError("distributed strategy requires a torchrun or Slurm environment")
    if world_size < 2:
        raise ValueError("distributed WORLD_SIZE must be at least two")
    master_addr, master_port = _parse_master_endpoint(environment)
    return TrainingTopology(
        rank=rank,
        local_rank=local_rank,
        world_size=world_size,
        backend="nccl",
        device_index=local_rank,
        node_rank=node_rank,
        local_world_size=local_world_size,
        launcher=launcher,
        strategy=strategy,
        master_addr=master_addr,
        master_port=master_port,
        launch_run_id=launch_run_id,
    )


def _parse_torchrun_topology(environment: Mapping[str, str]) -> TrainingTopology:
    """保留内部调用名并返回 DDP 身份的统一分布式拓扑。"""

    return _parse_distributed_topology(
        environment,
        strategy="distributed_data_parallel",
    )


def parse_distributed_topology(
    environment: Mapping[str, str],
    *,
    strategy: str,
) -> TrainingTopology:
    """公开复用 DDP/DeepSpeed 完全一致的 launcher 拓扑解析。"""

    return _parse_distributed_topology(environment, strategy=strategy)


class DistributedDataParallelTrainingSession(NativePreparedTrainingSession):
    """封装 DDP、NCCL collective 与 native 优化生命周期。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        config: TrainingConfig,
        topology: TrainingTopology,
        timeout_seconds: int,
        gradient_as_bucket_view: bool,
        find_unused_parameters: bool,
    ) -> None:
        """保存已验证拓扑和 DDP 包装参数。"""

        super().__init__(precision, config=config, topology=topology)
        self._timeout_seconds = timeout_seconds
        self._gradient_as_bucket_view = gradient_as_bucket_view
        self._find_unused_parameters = find_unused_parameters
        self._owns_process_group = False
        self._device = torch.device("cuda", topology.device_index)

    @property
    def rank(self) -> int:
        """返回 torchrun 全局 rank。"""

        return self.topology.rank

    @property
    def local_rank(self) -> int:
        """返回 torchrun 节点内 rank。"""

        return self.topology.local_rank

    @property
    def world_size(self) -> int:
        """返回 torchrun world size。"""

        return self.topology.world_size

    def _rendezvous_init_method(self) -> str:
        """从已验证拓扑构造不依赖 ``RANK/WORLD_SIZE`` 环境的入口。"""

        address = self.topology.master_addr
        port = self.topology.master_port
        if (
            address is None
            or not address.strip()
            or any(character.isspace() for character in address)
        ):
            raise ValueError("DDP topology requires a valid rendezvous master address")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("DDP topology requires a valid rendezvous master port")
        host = f"[{address}]" if ":" in address and not address.startswith("[") else address
        return f"tcp://{host}:{port}"

    def setup(self) -> None:
        """仅以 NCCL 建立或验证匹配的进程组。"""

        init_method = self._rendezvous_init_method()
        if not torch.cuda.is_available():
            raise RuntimeError("distributed_data_parallel requires CUDA")
        torch.cuda.set_device(self.device)
        process_group_preexisting = dist.is_initialized()
        if not process_group_preexisting:
            try:
                dist.init_process_group(
                    backend="nccl",
                    init_method=init_method,
                    rank=self.rank,
                    world_size=self.world_size,
                    timeout=timedelta(seconds=self._timeout_seconds),
                )
            except BaseException:
                # 初始化抛错后也可能留下可见进程组;只回收本次创建的资源。
                if dist.is_initialized():
                    dist.destroy_process_group()
                raise
            self._owns_process_group = True
        if dist.get_backend() != "nccl":
            raise RuntimeError("distributed_data_parallel requires an NCCL process group")
        if dist.get_world_size() != self.world_size or dist.get_rank() != self.rank:
            raise RuntimeError("initialized NCCL group does not match torchrun topology")
        self.precision.setup(self.device)

    def prepare_model(self, model: nn.Module) -> nn.Module:
        """移动模型后构造单进程单 GPU DDP 包装器。"""

        model = model.to(self.device)
        return DistributedDataParallel(
            model,
            device_ids=[self.device.index],
            output_device=self.device.index,
            gradient_as_bucket_view=self._gradient_as_bucket_view,
            find_unused_parameters=self._find_unused_parameters,
        )

    def accumulation_context(
        self, model: nn.Module, *, synchronize: bool
    ) -> AbstractContextManager[None]:
        """在非边界微批次关闭 DDP 梯度 all-reduce。"""

        if not isinstance(model, DistributedDataParallel):
            raise TypeError("DDP session requires a prepared DDP model")
        if synchronize:
            return super().accumulation_context(model, synchronize=True)
        return model.no_sync()

    @staticmethod
    def _module(model: nn.Module) -> nn.Module:
        """返回 DDP 内部模型并拒绝错误包装。"""

        if not isinstance(model, DistributedDataParallel):
            raise TypeError("DDP session requires a DistributedDataParallel model")
        module: object = getattr(model, "module", None)
        if not isinstance(module, nn.Module):
            raise TypeError("DDP wrapper lacks an nn.Module payload")
        return module

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """裁剪 DDP 内部模型参数。"""

        norm = torch.nn.utils.clip_grad_norm_(self._module(model).parameters(), max_norm)
        return float(norm.item())

    def all_finite(self, finite: bool) -> bool:
        """用 MIN reduction 要求全部 rank 均为有限值。"""

        flag = torch.tensor(int(finite), device=self.device, dtype=torch.int32)
        _collectives.all_reduce(flag, op=dist.ReduceOp.MIN)
        return bool(flag.item())

    def reduce_mean(self, value: float) -> float:
        """计算跨 rank 平均标量。"""

        tensor = torch.tensor(value, device=self.device, dtype=torch.float64)
        _collectives.all_reduce(tensor, op=dist.ReduceOp.SUM)
        return float((tensor / self.world_size).item())

    def broadcast_text(self, value: str) -> str:
        """从 rank 0 广播 checkpoint 控制文本。"""

        values = [value if self.is_primary else ""]
        dist.broadcast_object_list(values, src=0, device=self.device)
        result = values[0]
        if not result:
            raise RuntimeError("DDP broadcast returned invalid text")
        return result

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """在主 rank 收齐全部 DataModule 与 RNG 状态。"""

        gathered: list[object] | None = (
            [object() for _ in range(self.world_size)] if self.is_primary else None
        )
        dist.gather_object(dict(local_state), gathered, dst=0)
        return None if gathered is None else self._validate_rank_runtime_states(gathered)

    def gather_checkpoint_status(
        self, status: CheckpointCollectiveStatus
    ) -> Sequence[CheckpointCollectiveStatus]:
        """在所有 rank 收集有界 checkpoint 阶段状态。"""

        payloads: list[object] = [object() for _ in range(self.world_size)]
        _collectives.all_gather_object(payloads, status.to_payload())
        return tuple(CheckpointCollectiveStatus.from_payload(payload) for payload in payloads)

    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """物化无 ``module.`` 前缀的模型状态。"""

        return self._module(model).state_dict()

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """严格恢复 DDP 内部模型状态。"""

        self._module(model).load_state_dict(dict(state), strict=True)

    def barrier(self) -> None:
        """同步当前 NCCL 进程组。"""

        if dist.is_initialized():
            _collectives.barrier()

    def close(self) -> None:
        """仅销毁本 session 创建的进程组。"""

        if self._accumulation_context is not None:
            raise RuntimeError("cannot close DDP session during forward/backward")
        self._model = None
        self._optimizer = None
        self._scheduler = None
        if self._owns_process_group and dist.is_initialized():
            dist.destroy_process_group()
        self._owns_process_group = False
        self._device = None


class DistributedDataParallelStrategy:
    """从严格 torchrun 环境准备 CUDA/NCCL DDP session。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        expected_world_size: int,
        timeout_seconds: int = 1800,
        gradient_as_bucket_view: bool = True,
        find_unused_parameters: bool = False,
    ) -> None:
        """解析拓扑但不初始化 distributed runtime。"""

        self._precision = precision
        self._topology = _parse_torchrun_topology(os.environ)
        if self._topology.world_size != expected_world_size:
            raise ValueError("configured world_size does not match torchrun WORLD_SIZE")
        self._timeout_seconds = timeout_seconds
        self._gradient_as_bucket_view = gradient_as_bucket_view
        self._find_unused_parameters = find_unused_parameters

    @property
    def name(self) -> str:
        """返回规范策略键。"""

        return "distributed_data_parallel"

    @property
    def topology(self) -> TrainingTopology:
        """返回已验证 torchrun 拓扑。"""

        return self._topology

    def configure_process_environment(self) -> None:
        """在模型构造前验证 CUDA 并绑定 local rank。"""

        if not torch.cuda.is_available():
            raise RuntimeError("distributed_data_parallel requires CUDA")
        if self.topology.local_rank >= torch.cuda.device_count():
            raise RuntimeError("LOCAL_RANK exceeds visible CUDA device count")
        torch.cuda.set_device(self.topology.device_index)

    def model_initialization_context(self) -> AbstractContextManager[None]:
        """DDP 在模型构造阶段不分区参数。"""

        return nullcontext()

    def prepare(
        self,
        *,
        model: nn.Module,
        config: TrainingConfig,
        optimizer_factory: OptimizerFactory,
        scheduler_factory: SchedulerFactory,
        batches_per_epoch: int,
    ) -> DistributedDataParallelTrainingSession:
        """建立 NCCL、包装模型并绑定 native 优化生命周期。"""

        session = DistributedDataParallelTrainingSession(
            self._precision,
            config=config,
            topology=self.topology,
            timeout_seconds=self._timeout_seconds,
            gradient_as_bucket_view=self._gradient_as_bucket_view,
            find_unused_parameters=self._find_unused_parameters,
        )
        try:
            session.setup()
            prepared = session.prepare_model(model)
            optimizer = optimizer_factory(prepared)
            scheduler = scheduler_factory(optimizer, batches_per_epoch)
            session.bind(prepared, optimizer, scheduler)
            return session
        except BaseException:
            # prepare 未提交给 Engine 前由策略事务回滚,预存进程组不会被销毁。
            session.close()
            raise


__all__ = [
    "DistributedDataParallelStrategy",
    "DistributedDataParallelTrainingSession",
]
