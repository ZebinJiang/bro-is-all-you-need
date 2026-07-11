"""基于 PyTorch composable FSDP2 的生产训练策略。"""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path

import torch
from torch import distributed as dist
from torch import nn

from autovla.training.precision import PrecisionPolicy
from autovla.training.strategy.base import CheckpointCollectiveStatus, TrainingStrategy


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
        self._world_size = 1
        self._owns_process_group = False
        self._prepared_model: nn.Module | None = None
        self._wrapped_module_names: tuple[str, ...] = ()

    @property
    def rank(self) -> int:
        """返回全局 rank。"""

        return self._rank

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

        from torch.distributed._composable.fsdp import fully_shard

        model = model.to(self.device)
        selected = [
            (name, module)
            for name, module in model.named_modules()
            if name and self._module_filter(name, module)
        ]
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
        dist.all_reduce(flag, op=dist.ReduceOp.MIN)
        return bool(flag.item())

    def reduce_mean(self, value: float) -> float:
        """计算跨 FSDP2 rank 平均标量。"""

        tensor = torch.tensor(value, device=self.device, dtype=torch.float64)
        dist.all_reduce(tensor, op=dist.ReduceOp.SUM)
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
    ) -> dict[str, object]:
        """通过公开 state-dict API 返回 DTensor 模型和优化器状态。"""

        self._require_supported_dcp()
        from torch.distributed.checkpoint.state_dict import (
            StateDictOptions,
            get_model_state_dict,
            get_optimizer_state_dict,
        )

        prepared = self._require_model(model)
        options = StateDictOptions(full_state_dict=False, cpu_offload=False)
        return {
            "model": get_model_state_dict(prepared, options=options),
            "optimizer": get_optimizer_state_dict(prepared, optimizer, options=options),
        }

    def save_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """由全部 rank 使用公共 DCP API 保存 DTensor 分片。"""

        self._require_supported_dcp()
        from torch.distributed.checkpoint import save

        save(self._sharded_state(model, optimizer), checkpoint_id=str(path))
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
        from torch.distributed.checkpoint import DefaultLoadPlanner, FileSystemReader

        metadata = FileSystemReader(str(path)).read_metadata()
        keys = tuple(sorted(str(key) for key in metadata.state_dict_metadata))
        if not any(key == "model" or key.startswith("model.") for key in keys):
            raise ValueError("FSDP2 checkpoint metadata lacks model state")
        if not any(key == "optimizer" or key.startswith("optimizer.") for key in keys):
            raise ValueError("FSDP2 checkpoint metadata lacks optimizer state")
        planner = DefaultLoadPlanner()
        planner.set_up_planner(
            self._sharded_state(model, optimizer),
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
        from torch.distributed.checkpoint import load
        from torch.distributed.checkpoint.state_dict import (
            StateDictOptions,
            set_model_state_dict,
            set_optimizer_state_dict,
        )

        prepared = self._require_model(model)
        state = self._sharded_state(model, optimizer)
        load(state, checkpoint_id=str(path))
        options = StateDictOptions(full_state_dict=False, cpu_offload=False)
        set_model_state_dict(
            prepared,
            model_state_dict=state["model"],
            options=options,
        )
        set_optimizer_state_dict(
            prepared,
            optimizer,
            optim_state_dict=state["optimizer"],
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
        dist.all_gather_object(payloads, status.to_payload())
        return tuple(CheckpointCollectiveStatus.from_payload(payload) for payload in payloads)

    def barrier(self) -> None:
        """同步当前 FSDP2 进程组。"""

        if dist.is_initialized():
            dist.barrier()

    def close(self) -> None:
        """释放本策略创建的进程组和模型引用。"""

        self._prepared_model = None
        self._wrapped_module_names = ()
        if self._owns_process_group and dist.is_initialized():
            dist.destroy_process_group()
        self._owns_process_group = False
        self._device = None


__all__ = ["FullyShardedDataParallelStrategy"]
