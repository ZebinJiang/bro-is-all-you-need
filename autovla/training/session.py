"""统一生产训练 session 契约与 native 优化生命周期。"""

from __future__ import annotations

import math
from abc import abstractmethod
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Protocol, cast, runtime_checkable

from autovla.config.schema.training import TrainingConfig
from autovla.training.strategy.base import PreparedTrainingSessionBase

if TYPE_CHECKING:
    import torch
    from torch import nn

    from autovla.data.module import DataModule
    from autovla.models.interfaces.checkpoint import ModelCheckpointAdapter
    from autovla.models.outputs import ModelInputBatch, ModelOutput
    from autovla.training.callbacks.base import TrainingCallback
    from autovla.training.checkpointing.manager import CheckpointManager
    from autovla.training.precision import PrecisionPolicy
    from autovla.training.state import TrainingState
    from autovla.training.telemetry.logger import MetricLogger


class OptimizerFactory(Protocol):
    """约束从模型构造优化器的可调用对象。"""

    def __call__(self, model: nn.Module) -> torch.optim.Optimizer:
        """为给定模型返回优化器。"""

        ...


class SchedulerFactory(Protocol):
    """约束从优化器和总步数构造调度器的可调用对象。"""

    def __call__(
        self,
        optimizer: torch.optim.Optimizer,
        total_steps: int,
    ) -> torch.optim.lr_scheduler.LRScheduler:
        """为给定优化器返回学习率调度器。"""

        ...


def _require_exact_non_negative_int(value: object, name: str) -> int:
    """校验运行时计数为非负内置整数,拒绝 bool 和整数子类。"""

    if type(value) is not int:
        raise TypeError(f"{name} must be a built-in integer")
    if value < 0:
        raise ValueError(f"{name} must be non-negative")
    return value


@dataclass(frozen=True, slots=True)
class TrainingTopology:
    """记录 CUDA 数据并行拓扑身份。"""

    rank: int
    local_rank: int
    world_size: int
    backend: str
    device_index: int
    node_rank: int
    local_world_size: int
    launcher: str
    strategy: str
    master_addr: str | None = None
    master_port: int | None = None
    launch_run_id: str | None = None

    def __post_init__(self) -> None:
        """校验 rank 范围、NCCL 后端和 CUDA 设备编号。"""

        rank = _require_exact_non_negative_int(self.rank, "training topology rank")
        local_rank = _require_exact_non_negative_int(
            self.local_rank,
            "training topology local_rank",
        )
        world_size = _require_exact_non_negative_int(
            self.world_size,
            "training topology world_size",
        )
        device_index = _require_exact_non_negative_int(
            self.device_index,
            "training topology device_index",
        )
        node_rank = _require_exact_non_negative_int(
            self.node_rank,
            "training topology node_rank",
        )
        local_world_size = _require_exact_non_negative_int(
            self.local_world_size,
            "training topology local_world_size",
        )
        if world_size <= 0:
            raise ValueError("training topology world_size must be positive")
        if local_world_size <= 0:
            raise ValueError("training topology local_world_size must be positive")
        if rank >= world_size:
            raise ValueError("training topology rank is out of range")
        if local_rank >= local_world_size:
            raise ValueError("training topology local rank is out of range")
        if world_size % local_world_size != 0:
            raise ValueError("training topology requires uniform local world sizes")
        node_count = world_size // local_world_size
        if node_rank >= node_count:
            raise ValueError("training topology node rank is out of range")
        if rank != node_rank * local_world_size + local_rank:
            raise ValueError("training topology rank does not match node/local rank")
        if device_index != local_rank:
            raise ValueError("training topology device index must match local rank")
        if self.backend not in {"none", "nccl"}:
            raise ValueError("production training topology supports only none or nccl")
        if world_size > 1 and self.backend != "nccl":
            raise ValueError("multi-rank production training requires NCCL")
        if world_size == 1 and self.backend != "none":
            raise ValueError("single-rank production training topology requires backend none")
        if self.launcher not in {"direct", "torchrun", "slurm"}:
            raise ValueError("training topology launcher must be direct, torchrun, or slurm")
        if self.strategy not in {
            "single_gpu",
            "distributed_data_parallel",
            "deepspeed",
        }:
            raise ValueError("training topology strategy is not a production strategy")
        if world_size == 1 and (self.launcher != "direct" or self.strategy != "single_gpu"):
            raise ValueError("single GPU topology requires direct/single_gpu identity")
        if world_size > 1 and (self.launcher == "direct" or self.strategy == "single_gpu"):
            raise ValueError("distributed topology requires a distributed launcher and strategy")
        if world_size == 1:
            if any(
                value is not None
                for value in (self.master_addr, self.master_port, self.launch_run_id)
            ):
                raise ValueError("single GPU topology cannot carry distributed launch metadata")
            return
        if self.master_addr is None or not self.master_addr.strip():
            raise ValueError("distributed topology requires a non-empty master address")
        if any(character.isspace() for character in self.master_addr):
            raise ValueError("distributed topology master address cannot contain whitespace")
        if type(self.master_port) is not int or not 1 <= self.master_port <= 65535:
            raise ValueError("distributed topology master port must be in [1, 65535]")
        if self.node_count > 1:
            if self.master_addr in {"localhost", "127.0.0.1", "::1"}:
                raise ValueError("cross-node topology cannot use a loopback master address")
            if self.launch_run_id is None or not self.launch_run_id.strip():
                raise ValueError("cross-node topology requires a stable launcher run id")

    @property
    def node_count(self) -> int:
        """返回由均匀每节点进程数推导的节点数量。"""

        return self.world_size // self.local_world_size

    def checkpoint_identity(self) -> dict[str, object]:
        """返回跨 rank 一致且允许新 rendezvous 的恢复拓扑身份。"""

        return {
            "world_size": self.world_size,
            "backend": self.backend,
            "local_world_size": self.local_world_size,
            "node_count": self.node_count,
            "launcher": self.launcher,
            "strategy": self.strategy,
        }

    def to_dict(self) -> dict[str, object]:
        """返回包含 rank 与 rendezvous 的完整运行拓扑元数据。"""

        return {
            "rank": self.rank,
            "local_rank": self.local_rank,
            "world_size": self.world_size,
            "backend": self.backend,
            "device_index": self.device_index,
            "node_rank": self.node_rank,
            "local_world_size": self.local_world_size,
            "launcher": self.launcher,
            "strategy": self.strategy,
            "master_addr": self.master_addr,
            "master_port": self.master_port,
            "launch_run_id": self.launch_run_id,
        }


@dataclass(frozen=True, slots=True)
class OptimizerStepResult:
    """报告一个微批次是否提交了真实优化器更新。"""

    update_committed: bool
    global_grad_norm: float | None
    learning_rates: tuple[float, ...]
    overflow_detected: bool
    skipped_reason: str | None
    micro_step: int
    optimizer_step: int

    def __post_init__(self) -> None:
        """拒绝矛盾提交、overflow 和计数状态。"""

        _require_exact_non_negative_int(self.micro_step, "optimizer result micro_step")
        _require_exact_non_negative_int(self.optimizer_step, "optimizer result optimizer_step")
        if type(self.update_committed) is not bool or type(self.overflow_detected) is not bool:
            raise TypeError("optimizer result flags must be booleans")
        if self.global_grad_norm is not None and (
            type(self.global_grad_norm) is not float
            or not math.isfinite(self.global_grad_norm)
            or self.global_grad_norm < 0.0
        ):
            raise ValueError("global_grad_norm must be a finite non-negative float or None")
        if type(self.learning_rates) is not tuple or any(
            type(rate) is not float or not math.isfinite(rate) or rate < 0.0
            for rate in self.learning_rates
        ):
            raise ValueError("learning rates must be finite non-negative float values")
        if self.skipped_reason is not None and (
            type(self.skipped_reason) is not str or not self.skipped_reason
        ):
            raise ValueError("skipped_reason must be non-empty text or None")
        if self.update_committed and (self.overflow_detected or self.skipped_reason is not None):
            raise ValueError("committed optimizer update cannot be skipped or overflowed")
        if self.overflow_detected and self.skipped_reason is None:
            raise ValueError("optimizer overflow requires an explicit skipped_reason")


@dataclass(frozen=True, slots=True)
class CheckpointSaveRequest:
    """携带 session 保存公共控制状态所需的组件。"""

    manager: CheckpointManager
    data_module: DataModule
    callbacks: Sequence[TrainingCallback]
    metric_logger: MetricLogger
    state: TrainingState
    reason: str


@dataclass(frozen=True, slots=True)
class CheckpointLoadRequest:
    """携带 session 恢复公共控制状态所需的组件。"""

    manager: CheckpointManager
    path: Path
    data_module: DataModule
    family_adapter: ModelCheckpointAdapter
    callbacks: Sequence[TrainingCallback]
    metric_logger: MetricLogger


@dataclass(frozen=True, slots=True)
class StrategyCheckpointResult:
    """返回 checkpoint 路径及可选恢复训练状态。"""

    path: Path
    restored_state: TrainingState | None = None


@runtime_checkable
class TrainingStrategy(Protocol):
    """把无运行时副作用的策略配置准备为唯一 session。"""

    @property
    def name(self) -> str:
        """返回规范生产策略键。"""

        ...

    @property
    def topology(self) -> TrainingTopology:
        """返回从进程环境严格解析的目标拓扑。"""

        ...

    def configure_process_environment(self) -> None:
        """在模型构造前绑定本地 CUDA 设备。"""

        ...

    def model_initialization_context(self) -> AbstractContextManager[None]:
        """返回模型工厂必须进入的一次性策略初始化上下文。"""

        ...

    def prepare(
        self,
        *,
        model: nn.Module,
        config: TrainingConfig,
        optimizer_factory: OptimizerFactory,
        scheduler_factory: SchedulerFactory,
        batches_per_epoch: int,
    ) -> PreparedTrainingSession:
        """构造模型、优化器、调度器和策略运行时的唯一所有者。"""

        ...


@dataclass(frozen=True, slots=True)
class StrategyInitializationContextFactory:
    """把训练策略初始化上下文适配为模型装配层的无后端工厂。"""

    strategy: TrainingStrategy

    def __post_init__(self) -> None:
        """拒绝不满足完整策略协议的动态对象。"""

        if not isinstance(self.strategy, TrainingStrategy):
            raise TypeError("strategy must satisfy the canonical TrainingStrategy protocol")

    @property
    def identity(self) -> str:
        """返回进入模型装配与 checkpoint 指纹的稳定策略身份。"""

        return f"autovla.training.initialization.{self.strategy.name}.v1"

    def __call__(self) -> AbstractContextManager[None]:
        """把模型工厂调用转交给策略的一次性初始化边界。"""

        return self.strategy.model_initialization_context()


class PreparedTrainingSession(PreparedTrainingSessionBase):
    """统一拥有 prepared model、优化生命周期和策略 checkpoint。"""

    @property
    @abstractmethod
    def model(self) -> nn.Module:
        """返回当前策略准备后的模型调用边界。"""

        raise NotImplementedError

    @property
    @abstractmethod
    def optimizer(self) -> torch.optim.Optimizer:
        """返回 session 拥有的优化器。"""

        raise NotImplementedError

    @property
    @abstractmethod
    def scheduler(self) -> torch.optim.lr_scheduler.LRScheduler:
        """返回 session 拥有的学习率调度器。"""

        raise NotImplementedError

    @property
    @abstractmethod
    def topology(self) -> TrainingTopology:
        """返回不可变训练拓扑。"""

        raise NotImplementedError

    @abstractmethod
    def forward(self, model_input: ModelInputBatch, *, force_boundary: bool) -> ModelOutput:
        """执行 session 拥有的前向及累积同步上下文。"""

        raise NotImplementedError

    @abstractmethod
    def backward(self, loss: torch.Tensor) -> None:
        """执行 session 拥有的缩放与反向传播。"""

        raise NotImplementedError

    @abstractmethod
    def step(self, *, force_boundary: bool) -> OptimizerStepResult:
        """执行或跳过本微批次对应的优化器更新。"""

        raise NotImplementedError

    @abstractmethod
    def zero_grad(self) -> None:
        """清除 session 拥有的梯度。"""

        raise NotImplementedError

    def scheduler_state_dict(self) -> Mapping[str, object]:
        """由 session 读取自身 scheduler checkpoint 状态。"""

        return self.scheduler.state_dict()

    def validate_scheduler_state_dict(self, state: Mapping[str, object]) -> None:
        """不修改 scheduler 地验证字段和容器形状。"""

        expected = self.scheduler.state_dict()
        if set(state) != set(expected):
            raise ValueError("checkpoint scheduler fields mismatch")
        for name, value in state.items():
            current = expected[name]
            if isinstance(current, list):
                if not isinstance(value, list) or len(value) != len(current):
                    raise ValueError(f"checkpoint scheduler list {name!r} mismatch")
            elif isinstance(current, Mapping):
                if not isinstance(value, Mapping) or set(value) != set(current):
                    raise ValueError(f"checkpoint scheduler mapping {name!r} mismatch")
            elif current is not None and type(value) is not type(current):
                raise TypeError(f"checkpoint scheduler field {name!r} has invalid type")

    def load_scheduler_state_dict(self, state: Mapping[str, object]) -> None:
        """由 session 唯一恢复自身 scheduler 状态。"""

        self.scheduler.load_state_dict(dict(state))

    def save_checkpoint(self, request: CheckpointSaveRequest) -> StrategyCheckpointResult:
        """通过公共协调器保存控制状态与策略状态。"""

        path = request.manager.save(
            model=self.model,
            optimizer=self.optimizer,
            scheduler=self.scheduler,
            strategy=self,
            data_module=request.data_module,
            callbacks=request.callbacks,
            metric_logger=request.metric_logger,
            state=request.state,
            reason=request.reason,
        )
        return StrategyCheckpointResult(path=path)

    def load_checkpoint(self, request: CheckpointLoadRequest) -> StrategyCheckpointResult:
        """通过公共协调器恢复同拓扑完整训练状态。"""

        state = request.manager.load(
            request.path,
            model=self.model,
            optimizer=self.optimizer,
            scheduler=self.scheduler,
            strategy=self,
            data_module=request.data_module,
            family_adapter=request.family_adapter,
            callbacks=request.callbacks,
            metric_logger=request.metric_logger,
        )
        self.barrier()
        return StrategyCheckpointResult(path=request.path, restored_state=state)


class NativePreparedTrainingSession(PreparedTrainingSession):
    """实现 single-GPU 与 DDP 共用的 native 优化语义。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        config: TrainingConfig,
        topology: TrainingTopology,
    ) -> None:
        """保存累积配置,模型和优化器由 ``bind`` 一次性绑定。"""

        super().__init__(precision)
        self._config = config
        self._topology = topology
        self._model: nn.Module | None = None
        self._optimizer: torch.optim.Optimizer | None = None
        self._scheduler: torch.optim.lr_scheduler.LRScheduler | None = None
        self._accumulation_context: AbstractContextManager[None] | None = None
        self._pending_boundary: bool | None = None
        self._window_micro_steps = 0
        self._total_micro_steps = 0
        self._optimizer_steps = 0

    def bind(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
    ) -> None:
        """一次性绑定 prepared model 与其优化状态。"""

        if self._model is not None:
            raise RuntimeError("training session is already bound")
        self._model = model
        self._optimizer = optimizer
        self._scheduler = scheduler
        self.zero_grad()

    @property
    def model(self) -> nn.Module:
        """返回已绑定模型。"""

        if self._model is None:
            raise RuntimeError("training session model is not bound")
        return self._model

    @property
    def optimizer(self) -> torch.optim.Optimizer:
        """返回已绑定优化器。"""

        if self._optimizer is None:
            raise RuntimeError("training session optimizer is not bound")
        return self._optimizer

    @property
    def scheduler(self) -> torch.optim.lr_scheduler.LRScheduler:
        """返回已绑定调度器。"""

        if self._scheduler is None:
            raise RuntimeError("training session scheduler is not bound")
        return self._scheduler

    @property
    def topology(self) -> TrainingTopology:
        """返回 native session 拓扑。"""

        return self._topology

    def _boundary(self, force_boundary: bool) -> bool:
        """计算 native 累积自然边界或显式短尾边界。"""

        accumulation = self._config.gradient_accumulation_steps
        return (self._window_micro_steps + 1) % accumulation == 0 or force_boundary

    def forward(self, model_input: ModelInputBatch, *, force_boundary: bool) -> ModelOutput:
        """在 DDP no-sync 与精度上下文内执行模型前向。"""

        from autovla.models.outputs import ModelOutput

        if self._accumulation_context is not None:
            raise RuntimeError("previous forward has no matching backward")
        boundary = self._boundary(force_boundary)
        context = self.accumulation_context(self.model, synchronize=boundary)
        context.__enter__()
        self._accumulation_context = context
        self._pending_boundary = boundary
        try:
            with self.autocast():
                output: object = self.model(model_input)
            if not isinstance(output, ModelOutput):
                raise TypeError("training model must return ModelOutput")
            return output
        except BaseException as error:
            self._finish_accumulation_context(type(error), error, error.__traceback__)
            raise

    def backward(self, loss: torch.Tensor) -> None:
        """按配置累积缩放损失并结束同步上下文。"""

        if self._accumulation_context is None:
            raise RuntimeError("backward requires a preceding forward")
        error: BaseException | None = None
        try:
            self.precision.backward(loss / self._config.gradient_accumulation_steps)
        except BaseException as caught:
            error = caught
            raise
        finally:
            if error is None:
                self._finish_accumulation_context(None, None, None)
            else:
                self._finish_accumulation_context(type(error), error, error.__traceback__)

    def _finish_accumulation_context(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """严格结束一次 forward/backward 共享的同步上下文。"""

        context = self._accumulation_context
        self._accumulation_context = None
        if context is not None:
            context.__exit__(error_type, error, traceback)

    def step(self, *, force_boundary: bool) -> OptimizerStepResult:
        """仅在累积边界执行 unscale、clip、step、scheduler 与清梯度。"""

        import torch

        if self._accumulation_context is not None:
            raise RuntimeError("step requires backward to finish")
        boundary = self._pending_boundary
        self._pending_boundary = None
        if boundary is None or boundary != self._boundary(force_boundary):
            raise RuntimeError("training step boundary changed after forward")
        self._total_micro_steps += 1
        self._window_micro_steps += 1
        if not boundary:
            return self._result(False, None, False, "gradient_accumulation")

        accumulation = self._config.gradient_accumulation_steps
        if self._window_micro_steps < accumulation:
            self.scale_gradients(self.model, accumulation / self._window_micro_steps)
        self.precision.unscale(self.optimizer)
        gradients_finite = all(
            parameter.grad is None or bool(torch.isfinite(parameter.grad.detach()).all().item())
            for parameter in self.model.parameters()
        )
        gradients_finite = self.all_finite(gradients_finite)
        gradient_norm: float | None = None
        if gradients_finite and self._config.gradient_clip_norm is not None:
            gradient_norm = self.clip_gradients(self.model, self._config.gradient_clip_norm)
        committed = gradients_finite and self.precision.step(self.optimizer)
        overflow = not committed
        if committed:
            self.scheduler.step()
            self._optimizer_steps += 1
        self.zero_grad()
        self._window_micro_steps = 0
        return self._result(
            committed,
            gradient_norm,
            overflow,
            None if committed else "nonfinite_gradient_or_precision_overflow",
        )

    def _result(
        self,
        committed: bool,
        gradient_norm: float | None,
        overflow: bool,
        reason: str | None,
    ) -> OptimizerStepResult:
        """构造学习率与计数一致的不可变 step 结果。"""

        learning_rates = tuple(float(group["lr"]) for group in self.optimizer.param_groups)
        return OptimizerStepResult(
            update_committed=committed,
            global_grad_norm=gradient_norm,
            learning_rates=learning_rates,
            overflow_detected=overflow,
            skipped_reason=reason,
            micro_step=self._total_micro_steps,
            optimizer_step=self._optimizer_steps,
        )

    def zero_grad(self) -> None:
        """按 set-to-none 语义清除 native 梯度。"""

        if self._accumulation_context is not None:
            self._finish_accumulation_context(None, None, None)
        self._pending_boundary = None
        self._window_micro_steps = 0
        self.optimizer.zero_grad(set_to_none=True)

    def strategy_state_dict(self) -> dict[str, object]:
        """保存精度、拓扑和 session 内部提交计数。"""

        return {
            "name": type(self).__name__,
            "precision": self.precision.state_dict(),
            "topology": self.topology.checkpoint_identity(),
            "total_micro_steps": self._total_micro_steps,
            "optimizer_steps": self._optimizer_steps,
        }

    def validate_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """要求 native checkpoint 使用相同 session 类型与 GPU 拓扑。"""

        expected = {"name", "precision", "topology", "total_micro_steps", "optimizer_steps"}
        if set(state) != expected:
            raise ValueError("checkpoint session fields are incomplete or unknown")
        if (
            state.get("name") != type(self).__name__
            or state.get("topology") != self.topology.checkpoint_identity()
        ):
            raise ValueError("checkpoint session type or topology does not match current session")
        precision = state.get("precision")
        if not isinstance(precision, dict):
            raise TypeError("checkpoint precision state must be a mapping")
        self.precision.validate_state_dict(cast(dict[str, object], precision))
        for name in ("total_micro_steps", "optimizer_steps"):
            value = state.get(name)
            if type(value) is not int or value < 0:
                raise ValueError(f"checkpoint session {name} must be non-negative")

    def load_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """恢复 native session 计数与精度状态。"""

        self.validate_strategy_state_dict(state)
        precision = state["precision"]
        if not isinstance(precision, dict):
            raise TypeError("checkpoint precision state must be a mapping")
        self.precision.load_state_dict(cast(dict[str, object], precision))
        total_micro_steps = _require_exact_non_negative_int(
            state["total_micro_steps"],
            "checkpoint session total_micro_steps",
        )
        optimizer_steps = _require_exact_non_negative_int(
            state["optimizer_steps"],
            "checkpoint session optimizer_steps",
        )
        self._total_micro_steps = total_micro_steps
        self._optimizer_steps = optimizer_steps
        self._window_micro_steps = 0


__all__ = [
    "CheckpointLoadRequest",
    "CheckpointSaveRequest",
    "NativePreparedTrainingSession",
    "OptimizerFactory",
    "OptimizerStepResult",
    "PreparedTrainingSession",
    "SchedulerFactory",
    "StrategyCheckpointResult",
    "StrategyInitializationContextFactory",
    "TrainingStrategy",
    "TrainingTopology",
]
