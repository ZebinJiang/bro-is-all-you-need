"""DeepSpeed ZeRO 1/2/3 官方公共 API 集成。"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from pathlib import Path
from types import TracebackType
from typing import Callable, Protocol, TypeVar, cast, runtime_checkable

import torch
from torch import distributed as dist
from torch import nn

from autovla.config.schema.distributed import (
    DEEPSPEED_PUBLIC_API_SURFACE,
    DeepSpeedConfig,
    DeepSpeedVersion,
    validate_deepspeed_engine_public_api,
    validate_deepspeed_public_api,
)
from autovla.config.schema.training import TrainingConfig
from autovla.core.registry import OptionalDependencyError
from autovla.models.assembly.contracts import (
    PartitionedCheckpointLoadSink,
    logical_parameter_shape,
)
from autovla.models.outputs import ModelInputBatch, ModelOutput
from autovla.training.checkpointing.identity import stable_fingerprint
from autovla.training.distributed_receipts import (
    StrategySessionIdentity,
    StrategyTeardownReceipt,
)
from autovla.training.precision import PrecisionPolicy
from autovla.training.session import (
    OptimizerFactory,
    OptimizerStepResult,
    PreparedTrainingSession,
    SchedulerFactory,
    TrainingTopology,
)
from autovla.training.strategy.base import CheckpointCollectiveStatus
from autovla.training.strategy.distributed_data_parallel import parse_distributed_topology

_DEEPSPEED_CHECKPOINT_SCHEMA = "autovla.deepspeed_checkpoint.v1"
OfficialCheckpointLoadT = TypeVar("OfficialCheckpointLoadT")


@runtime_checkable
class _DeepSpeedEngine(Protocol):
    """约束 AutoVLA 使用的 DeepSpeed 公共运行面与只读计数。"""

    module: nn.Module
    global_steps: int
    micro_steps: int
    skipped_steps: int

    def __call__(self, model_input: ModelInputBatch) -> object: ...

    def backward(self, loss: torch.Tensor) -> object: ...

    def is_gradient_accumulation_boundary(self) -> bool: ...

    def step(self) -> object: ...

    def zero_grad(self) -> None: ...

    def save_checkpoint(
        self,
        save_dir: str,
        tag: str,
        client_state: Mapping[str, object],
        save_latest: bool,
    ) -> object: ...

    def load_checkpoint(
        self,
        load_dir: str,
        tag: str,
        load_module_strict: bool,
        load_optimizer_states: bool,
        load_lr_scheduler_states: bool,
    ) -> tuple[object, object]: ...


class _DeepSpeedModule(Protocol):
    """约束延迟导入模块的 ``initialize`` 公共函数。"""

    zero: "_DeepSpeedZero"

    def initialize(
        self,
        *,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        lr_scheduler: torch.optim.lr_scheduler.LRScheduler,
        config: Mapping[str, object],
        dist_init_required: bool | None,
    ) -> tuple[object, object, object, object]: ...


class _DeepSpeedZero(Protocol):
    """约束 DeepSpeed 官方 ZeRO 分区构造上下文。"""

    def Init(
        self,
        *,
        config_dict_or_path: Mapping[str, object],
    ) -> AbstractContextManager[None]: ...

    def GatheredParameters(
        self,
        params: Sequence[nn.Parameter],
        *,
        modifier_rank: int,
    ) -> AbstractContextManager[None]: ...


class _DistributedCollectives(Protocol):
    """收窄 Torch 未完整标注的 collective 模块面。"""

    def all_reduce(self, tensor: torch.Tensor, *, op: object) -> object: ...

    def all_gather_object(self, output: list[object], value: object) -> None: ...

    def broadcast(self, tensor: torch.Tensor, *, src: int) -> object: ...

    def broadcast_object_list(self, object_list: list[object], *, src: int) -> None: ...

    def barrier(self) -> object: ...


_collectives = cast(_DistributedCollectives, cast(object, dist))


def _run_rank_zero_action(
    *,
    rank: int,
    world_size: int,
    action: Callable[[], None],
) -> None:
    """只在 rank 0 执行动作,并把失败对称传播到全部 rank。"""

    local_error: BaseException | None = None
    if rank == 0:
        try:
            action()
        except BaseException as error:
            local_error = error
    status: list[object] = [
        None if local_error is None else (type(local_error).__name__, str(local_error))
    ]
    if world_size > 1:
        _collectives.broadcast_object_list(status, src=0)
    failure = status[0]
    if failure is None:
        return
    if local_error is not None:
        raise local_error
    if (
        type(failure) is not tuple
        or len(failure) != 2
        or any(not isinstance(item, str) for item in failure)
    ):
        raise RuntimeError("rank 0 checkpoint failure payload is invalid")
    failure_type, message = cast(tuple[str, str], failure)
    raise RuntimeError(f"rank 0 partitioned checkpoint load failed: {failure_type}: {message}")


def _checkpoint_result_payload(value: object) -> Mapping[str, object]:
    """校验 collective 传输后的 family 结果载荷。"""

    if not isinstance(value, Mapping):
        raise TypeError("partitioned checkpoint result payload must be a mapping")
    raw = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) or not key for key in raw):
        raise ValueError("partitioned checkpoint result payload keys must be non-empty strings")
    return cast(Mapping[str, object], raw)


def _persistent_named_buffers(model: nn.Module) -> tuple[tuple[str, torch.Tensor], ...]:
    """枚举严格 state_dict 语义中的持久 buffer,排除运行时缓存。"""

    buffers: list[tuple[str, torch.Tensor]] = []
    for module_prefix, child in model.named_modules():
        raw_non_persistent = getattr(child, "_non_persistent_buffers_set", None)
        if not isinstance(raw_non_persistent, set) or any(
            not isinstance(name, str) for name in raw_non_persistent
        ):
            raise RuntimeError("torch module does not expose a valid buffer persistence inventory")
        non_persistent = raw_non_persistent
        for local_name, buffer in child.named_buffers(
            recurse=False,
            remove_duplicate=False,
        ):
            if local_name in non_persistent:
                continue
            qualified = f"{module_prefix}.{local_name}" if module_prefix else local_name
            buffers.append((qualified, buffer))
    names = tuple(name for name, _ in buffers)
    if len(names) != len(set(names)):
        raise RuntimeError("persistent buffer inventory contains duplicate qualified names")
    return tuple(buffers)


def _rollback_failed_prepare(
    *,
    engine: object | None,
    process_group_preexisting: bool,
) -> None:
    """尽力回滚未提交 engine 与本次新建进程组,保留首个异常。"""

    errors: list[BaseException] = []
    if engine is not None:
        destroy = getattr(engine, "destroy", None)
        if callable(destroy):
            try:
                destroy()
            except BaseException as error:
                errors.append(error)
    if not process_group_preexisting and dist.is_initialized():
        try:
            dist.destroy_process_group()
        except BaseException as error:
            errors.append(error)
    _raise_first_cleanup_error(errors)


def _raise_first_cleanup_error(errors: Sequence[BaseException]) -> None:
    """抛出首个清理异常,并把后续异常作为附注保留下来。"""

    if not errors:
        return
    primary = errors[0]
    for error in errors[1:]:
        _append_cleanup_note(
            primary,
            "additional DeepSpeed cleanup failure: " f"{type(error).__name__}: {error}",
        )
    raise primary


def _append_cleanup_note(error: BaseException, note: str) -> None:
    """附加清理说明,旧 Python 用专用 evidence 属性保存。"""

    try:
        add_note = getattr(error, "add_note", None)
    except BaseException:
        add_note = None
    if callable(add_note):
        try:
            add_note(note)
        except BaseException:
            pass
        else:
            return
    try:
        existing = getattr(error, "_autovla_cleanup_notes", ())
        if not isinstance(existing, tuple) or any(not isinstance(item, str) for item in existing):
            existing = ()
        error.__dict__["_autovla_cleanup_notes"] = (*existing, note)
    except BaseException:
        return


def _load_deepspeed(
    selected_version: DeepSpeedVersion,
) -> tuple[_DeepSpeedModule, dict[str, object]]:
    """导入 profile 选择的 exact DeepSpeed 并验证共同公共 API。"""

    if importlib.util.find_spec("deepspeed") is None:
        raise OptionalDependencyError(
            "deepspeed strategy dependency is absent: "
            f"selected={selected_version!r}, installed=None"
        )
    module: object = importlib.import_module("deepspeed")
    diagnostic = validate_deepspeed_public_api(
        module,
        selected_version=selected_version,
    )
    return cast(_DeepSpeedModule, module), diagnostic


def _require_engine_counter(value: object, name: str) -> int:
    """校验 DeepSpeed 公共计数为非负内置整数。"""

    if type(value) is not int:
        raise TypeError(f"DeepSpeed {name} must be a built-in integer")
    if value < 0:
        raise ValueError(f"DeepSpeed {name} must be non-negative")
    return value


def _committed_optimizer_steps(global_steps: object, skipped_steps: object) -> int:
    """由 DeepSpeed 尝试计数和跳过计数计算规范提交次数。"""

    attempted = _require_engine_counter(global_steps, "global_steps")
    skipped = _require_engine_counter(skipped_steps, "skipped_steps")
    if skipped > attempted:
        raise ValueError("DeepSpeed skipped_steps cannot exceed global_steps")
    return attempted - skipped


class _ZeroInitializationTransaction:
    """集中管理一次性 ZeRO-3 构造状态和进程组所有权。"""

    def __init__(self, *, required: bool) -> None:
        """按 ZeRO stage 初始化未消费或不适用的事务。"""

        self._state = "required" if required else "unused"
        self._owns_process_group = False

    @property
    def state(self) -> str:
        """返回只读初始化状态。"""

        return self._state

    @property
    def owns_process_group(self) -> bool:
        """返回完成事务是否创建并拥有进程组。"""

        return self._owns_process_group

    def issue(self) -> None:
        """签发唯一一次官方 ``zero.Init`` 上下文。"""

        if self._state != "required":
            raise RuntimeError("DeepSpeed ZeRO-3 initialization context may be requested once")
        self._state = "issued"

    def enter(self) -> None:
        """在官方上下文副作用前提交进入状态。"""

        if self._state != "issued":
            raise RuntimeError("DeepSpeed ZeRO-3 initialization context is not enterable")
        self._state = "entered"

    def fail(self, *, owns_process_group: bool) -> None:
        """标记失败并保留仍需重试销毁的进程组所有权。"""

        self._state = "failed"
        self._owns_process_group = owns_process_group

    def release_process_group(self) -> None:
        """仅在销毁成功或组已不存在后释放所有权。"""

        self._owns_process_group = False

    def complete(self, *, owns_process_group: bool) -> None:
        """完成事务并记录仅由本次初始化创建的进程组。"""

        if self._state != "entered":
            raise RuntimeError("DeepSpeed ZeRO-3 initialization transaction is not active")
        self._state = "completed"
        self._owns_process_group = owns_process_group


def _destroy_initialization_process_group(
    transaction: _ZeroInitializationTransaction,
    *,
    process_group_preexisting: bool,
    primary_error: BaseException | None,
) -> None:
    """回收本次初始化创建的组,并把清理失败降为 secondary note。"""

    owns_process_group = not process_group_preexisting and dist.is_initialized()
    transaction.fail(owns_process_group=owns_process_group)
    if not owns_process_group:
        return
    try:
        dist.destroy_process_group()
    except BaseException as cleanup_error:
        if primary_error is None:
            raise
        _append_cleanup_note(
            primary_error,
            "DeepSpeed process-group cleanup failed: "
            f"{type(cleanup_error).__name__}: {cleanup_error}",
        )
    else:
        transaction.release_process_group()


def _retry_owned_initialization_process_group(
    transaction: _ZeroInitializationTransaction,
) -> None:
    """重试销毁失败事务仍拥有的进程组。"""

    if not transaction.owns_process_group:
        return
    if not dist.is_initialized():
        transaction.release_process_group()
        return
    dist.destroy_process_group()
    transaction.release_process_group()


class _ZeroInitializationContext(AbstractContextManager[None]):
    """把官方 ``zero.Init`` 收窄为策略拥有的一次性构造事务。"""

    def __init__(
        self,
        transaction: _ZeroInitializationTransaction,
        context: AbstractContextManager[None],
        *,
        process_group_preexisting: bool,
    ) -> None:
        """保存事务、官方上下文和进入前进程组所有权。"""

        self._transaction = transaction
        self._context = context
        self._process_group_preexisting = process_group_preexisting

    def __enter__(self) -> None:
        """进入一次且仅一次 ZeRO-3 参数分区构造边界。"""

        self._transaction.enter()
        try:
            self._context.__enter__()
        except BaseException as error:
            _destroy_initialization_process_group(
                self._transaction,
                process_group_preexisting=self._process_group_preexisting,
                primary_error=error,
            )
            raise
        return None

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """结束官方上下文并记录本策略是否拥有新建进程组。"""

        try:
            suppress = self._context.__exit__(error_type, error, traceback)
        except BaseException as exit_error:
            primary_error = error if error is not None else exit_error
            if error is not None:
                _append_cleanup_note(
                    error,
                    "DeepSpeed zero.Init exit failed: "
                    f"{type(exit_error).__name__}: {exit_error}",
                )
            _destroy_initialization_process_group(
                self._transaction,
                process_group_preexisting=self._process_group_preexisting,
                primary_error=primary_error,
            )
            if error is not None:
                return False
            raise
        if error_type is None:
            self._transaction.complete(
                owns_process_group=(not self._process_group_preexisting and dist.is_initialized())
            )
        else:
            if error is None:
                raise RuntimeError("DeepSpeed zero.Init received an exception type without value")
            _destroy_initialization_process_group(
                self._transaction,
                process_group_preexisting=self._process_group_preexisting,
                primary_error=error,
            )
        return False if error_type is not None else suppress


class DeepSpeedTrainingSession(PreparedTrainingSession):
    """由 DeepSpeedEngine 独占 backward、step、scheduler 和分片 checkpoint。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        engine: _DeepSpeedEngine,
        optimizer: torch.optim.Optimizer,
        scheduler: torch.optim.lr_scheduler.LRScheduler,
        config: TrainingConfig,
        topology: TrainingTopology,
        generated_config: Mapping[str, object],
        owns_process_group: bool,
    ) -> None:
        """绑定官方 engine 与确定性 AutoVLA 配置。"""

        super().__init__(precision)
        self._engine: _DeepSpeedEngine | None = engine
        self._optimizer: torch.optim.Optimizer | None = optimizer
        self._scheduler: torch.optim.lr_scheduler.LRScheduler | None = scheduler
        self._config = config
        self._topology = topology
        self._generated_config = dict(generated_config)
        zero_config = self._generated_config.get("zero_optimization")
        if not isinstance(cast(object, zero_config), Mapping):
            raise TypeError("generated DeepSpeed config lacks integer ZeRO stage")
        zero_mapping = cast(Mapping[str, object], zero_config)
        if type(zero_mapping.get("stage")) is not int:
            raise TypeError("generated DeepSpeed config lacks integer ZeRO stage")
        self._zero_stage = cast(int, zero_mapping["stage"])
        canonical_deepspeed = config.distributed.deepspeed
        if canonical_deepspeed is None:
            raise ValueError("DeepSpeed session requires canonical DeepSpeed training config")
        if canonical_deepspeed.zero_stage != self._zero_stage:
            raise ValueError("generated DeepSpeed ZeRO stage differs from AutoVLA config")
        if config.distributed.strategy_key != f"deepspeed_zero_{self._zero_stage}":
            raise ValueError("DeepSpeed session strategy key differs from its ZeRO stage")
        generated_accumulation = self._generated_config.get("gradient_accumulation_steps")
        if (
            type(generated_accumulation) is not int
            or generated_accumulation != config.gradient_accumulation_steps
        ):
            raise ValueError(
                "generated DeepSpeed accumulation differs from AutoVLA training config"
            )
        if config.distributed.world_size != topology.world_size:
            raise ValueError("DeepSpeed topology differs from AutoVLA world_size")
        self._owns_process_group = owns_process_group
        self._closed = False
        self._teardown_receipt: StrategyTeardownReceipt | None = None
        self._session_identity = StrategySessionIdentity(
            strategy=config.distributed.strategy_key,
            rank=topology.rank,
            world_size=topology.world_size,
            topology_fingerprint=stable_fingerprint(topology.checkpoint_identity()),
            configuration_fingerprint=stable_fingerprint(self._generated_config),
        )
        self._pending_boundary: bool | None = None
        self._backward_complete = False
        self._window_micro_steps = 0
        self._optimizer_steps = _committed_optimizer_steps(
            engine.global_steps,
            engine.skipped_steps,
        )
        _require_engine_counter(engine.micro_steps, "micro_steps")
        self._device = torch.device("cuda", topology.device_index)

    @property
    def model(self) -> nn.Module:
        """返回 DeepSpeedEngine 作为唯一模型调用边界。"""

        engine = self._engine
        if engine is None:
            raise RuntimeError("DeepSpeed session is closed")
        if not isinstance(engine, nn.Module):
            raise TypeError("DeepSpeedEngine must remain a torch.nn.Module")
        return engine

    @property
    def optimizer(self) -> torch.optim.Optimizer:
        """返回组合根创建并交给 DeepSpeed 的优化器句柄。"""

        optimizer = self._optimizer
        if optimizer is None:
            raise RuntimeError("DeepSpeed session is closed")
        return optimizer

    @property
    def scheduler(self) -> torch.optim.lr_scheduler.LRScheduler:
        """返回由 DeepSpeed step 驱动的调度器句柄。"""

        scheduler = self._scheduler
        if scheduler is None:
            raise RuntimeError("DeepSpeed session is closed")
        return scheduler

    @property
    def teardown_receipt(self) -> StrategyTeardownReceipt | None:
        """返回最近一次资源回收结果,未关闭时为空。"""

        return self._teardown_receipt

    def _active_engine(self) -> _DeepSpeedEngine:
        """返回未关闭的 DeepSpeed engine。"""

        engine = self._engine
        if engine is None:
            raise RuntimeError("DeepSpeed session is closed")
        return engine

    @property
    def topology(self) -> TrainingTopology:
        """返回同拓扑恢复所需身份。"""

        return self._topology

    @property
    def rank(self) -> int:
        """返回全局 rank。"""

        return self.topology.rank

    @property
    def local_rank(self) -> int:
        """返回节点内 rank。"""

        return self.topology.local_rank

    @property
    def world_size(self) -> int:
        """返回数据并行 world size。"""

        return self.topology.world_size

    def setup(self) -> None:
        """验证 ``deepspeed.initialize`` 已建立匹配 NCCL 进程组。"""

        if not dist.is_initialized() or dist.get_backend() != "nccl":
            raise RuntimeError("DeepSpeed production session requires initialized NCCL")
        if dist.get_rank() != self.rank or dist.get_world_size() != self.world_size:
            raise RuntimeError("DeepSpeed process group does not match configured topology")

    def prepare_model(self, model: nn.Module) -> nn.Module:
        """拒绝在 initialize 后重复包装模型。"""

        if model is not self._engine.module:
            raise ValueError("DeepSpeed session cannot prepare a second model")
        return self.model

    def _natural_boundary(self) -> bool:
        """通过官方 DeepSpeedEngine API 查询当前累积边界。"""

        boundary = self._active_engine().is_gradient_accumulation_boundary()
        if type(boundary) is not bool:
            raise TypeError("DeepSpeed accumulation boundary must be boolean")
        return boundary

    def forward(self, model_input: ModelInputBatch, *, force_boundary: bool) -> ModelOutput:
        """调用 DeepSpeedEngine 前向并拒绝无法证明的强制短窗口。"""

        if type(force_boundary) is not bool:
            raise TypeError("force_boundary must be boolean")
        if self._pending_boundary is not None:
            raise RuntimeError("previous DeepSpeed forward has no matching step")
        natural = self._natural_boundary()
        if force_boundary and not natural:
            raise RuntimeError(
                "DeepSpeed cannot prove exact forced short accumulation semantics; "
                "adjust max_steps or loader length to an accumulation boundary"
            )
        if natural and not force_boundary:
            raise RuntimeError(
                "DeepSpeed accumulation boundary differs from AutoVLA training config"
            )
        output = self._active_engine()(model_input)
        if not isinstance(output, ModelOutput):
            raise TypeError("training model must return ModelOutput")
        self._pending_boundary = natural
        self._backward_complete = False
        return output

    def backward(self, loss: torch.Tensor) -> None:
        """把未预缩放标量损失直接交给 DeepSpeedEngine。"""

        if self._pending_boundary is None:
            raise RuntimeError("DeepSpeed backward requires a preceding forward")
        if self._backward_complete:
            raise RuntimeError("DeepSpeed backward may run only once per forward")
        try:
            self._active_engine().backward(loss)
        except BaseException:
            self._pending_boundary = None
            self._backward_complete = False
            raise
        self._backward_complete = True

    def step(self, *, force_boundary: bool) -> OptimizerStepResult:
        """调用一次且仅一次 DeepSpeedEngine.step 并翻译提交状态。"""

        if type(force_boundary) is not bool:
            raise TypeError("force_boundary must be boolean")
        boundary = self._pending_boundary
        self._pending_boundary = None
        if boundary is None or not self._backward_complete:
            raise RuntimeError("DeepSpeed step requires forward and backward")
        self._backward_complete = False
        if force_boundary != boundary:
            raise RuntimeError("DeepSpeed step boundary changed after forward")
        engine = self._active_engine()
        before_steps = _require_engine_counter(engine.global_steps, "global_steps")
        before_skipped = _require_engine_counter(engine.skipped_steps, "skipped_steps")
        before_committed = _committed_optimizer_steps(before_steps, before_skipped)
        if before_committed != self._optimizer_steps:
            raise RuntimeError("DeepSpeed committed-step authority drifted before step")
        engine.step()
        after_steps = _require_engine_counter(engine.global_steps, "global_steps")
        after_skipped = _require_engine_counter(engine.skipped_steps, "skipped_steps")
        if boundary and after_steps != before_steps + 1:
            raise RuntimeError("DeepSpeed did not report exactly one accumulation-boundary step")
        if not boundary and after_steps != before_steps:
            raise RuntimeError("DeepSpeed committed an update outside the accumulation boundary")
        overflow = after_skipped > before_skipped
        if after_skipped < before_skipped or after_skipped > before_skipped + 1:
            raise RuntimeError("DeepSpeed skipped-step counter changed unexpectedly")
        after_committed = _committed_optimizer_steps(after_steps, after_skipped)
        expected_committed = before_committed + int(boundary and not overflow)
        if after_committed != expected_committed:
            raise RuntimeError("DeepSpeed committed-step count changed unexpectedly")
        committed = after_committed == before_committed + 1
        self._optimizer_steps = after_committed
        self._window_micro_steps = 0 if boundary else self._window_micro_steps + 1
        micro_step = _require_engine_counter(engine.micro_steps, "micro_steps")
        learning_rates = tuple(float(group["lr"]) for group in self.optimizer.param_groups)
        return OptimizerStepResult(
            update_committed=committed,
            global_grad_norm=None,
            learning_rates=learning_rates,
            overflow_detected=overflow,
            skipped_reason=(
                None if committed else "gradient_accumulation" if not boundary else "overflow"
            ),
            micro_step=micro_step,
            optimizer_step=self._optimizer_steps,
        )

    def zero_grad(self) -> None:
        """通过官方 engine 清梯度并复位未提交的本地窗口状态。"""

        try:
            self._active_engine().zero_grad()
        finally:
            self._pending_boundary = None
            self._backward_complete = False
            self._window_micro_steps = 0

    def all_finite(self, finite: bool) -> bool:
        """用 NCCL MIN reduction 要求全部 rank 损失有限。"""

        flag = torch.tensor(int(finite), device=self.device, dtype=torch.int32)
        _collectives.all_reduce(flag, op=dist.ReduceOp.MIN)
        return bool(flag.item())

    def reduce_mean(self, value: float) -> float:
        """计算跨 rank 平均损失。"""

        tensor = torch.tensor(value, device=self.device, dtype=torch.float64)
        _collectives.all_reduce(tensor, op=dist.ReduceOp.SUM)
        return float((tensor / self.world_size).item())

    def clip_gradients(self, model: nn.Module, max_norm: float) -> float:
        """拒绝在 DeepSpeed 内部裁剪之外再裁剪一次。"""

        del model, max_norm
        raise RuntimeError("DeepSpeed owns gradient clipping through generated config")

    def broadcast_text(self, value: str) -> str:
        """从 rank 0 广播 checkpoint 控制文本。"""

        values = [value if self.is_primary else ""]
        dist.broadcast_object_list(values, src=0, device=self.device)
        result = values[0]
        if not result:
            raise RuntimeError("DeepSpeed broadcast returned invalid text")
        return result

    def collect_rank_runtime_state(
        self, local_state: Mapping[str, object]
    ) -> Mapping[str, Mapping[str, object]] | None:
        """在主 rank 收集 DataModule 与 RNG 状态。"""

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

    def gather_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """按 rank 顺序收集严格训练收据载荷。"""

        payloads: list[object] = [object() for _ in range(self.world_size)]
        _collectives.all_gather_object(payloads, dict(payload))
        gathered: list[Mapping[str, object]] = []
        for value in payloads:
            if not isinstance(value, Mapping):
                raise TypeError("DeepSpeed receipt collective returned a non-mapping payload")
            mapping = cast(Mapping[object, object], value)
            if any(not isinstance(key, str) for key in mapping):
                raise TypeError("DeepSpeed receipt payload keys must be strings")
            gathered.append(cast(Mapping[str, object], mapping))
        return tuple(gathered)

    def gather_bounded_receipt_payloads(
        self,
        payload: Mapping[str, object],
    ) -> Sequence[Mapping[str, object]]:
        """只在 rank 0 收集有界 receipt manifest 或 digest slot。"""

        payloads: list[object] | None = (
            [object() for _ in range(self.world_size)] if self.is_primary else None
        )
        dist.gather_object(dict(payload), payloads, dst=0)
        if payloads is None:
            return ()
        gathered: list[Mapping[str, object]] = []
        for value in payloads:
            if not isinstance(value, Mapping):
                raise TypeError(
                    "DeepSpeed bounded receipt collective returned a non-mapping payload"
                )
            mapping = cast(Mapping[object, object], value)
            if any(not isinstance(key, str) for key in mapping):
                raise TypeError("DeepSpeed bounded receipt payload keys must be strings")
            gathered.append(cast(Mapping[str, object], mapping))
        return tuple(gathered)

    def broadcast_receipt_payload(
        self,
        payload: Mapping[str, object] | None,
    ) -> Mapping[str, object]:
        """从 rank 0 广播固定大小 receipt control 或 summary。"""

        if self.is_primary != (payload is not None):
            raise ValueError("DeepSpeed receipt broadcast payload ownership differs from rank")
        values: list[object] = [None if payload is None else dict(payload)]
        dist.broadcast_object_list(values, src=0, device=self.device)
        value = values[0]
        if not isinstance(value, Mapping):
            raise TypeError("DeepSpeed receipt broadcast returned a non-mapping payload")
        mapping = cast(Mapping[object, object], value)
        if any(not isinstance(key, str) for key in mapping):
            raise TypeError("DeepSpeed receipt broadcast payload keys must be strings")
        return cast(Mapping[str, object], mapping)

    @property
    def uses_sharded_checkpoint(self) -> bool:
        """声明模型、优化器和 scheduler 由 DeepSpeed collective checkpoint 保存。"""

        return True

    def model_state_dict(self, model: nn.Module) -> Mapping[str, torch.Tensor]:
        """禁止隐式物化 ZeRO 分片为完整模型状态。"""

        del model
        raise RuntimeError("DeepSpeed checkpoint does not implicitly consolidate model weights")

    def load_model_state_dict(self, model: nn.Module, state: Mapping[str, torch.Tensor]) -> None:
        """禁止绕过 DeepSpeedEngine.load_checkpoint 恢复模型。"""

        del model, state
        raise RuntimeError("DeepSpeed model restore requires engine.load_checkpoint")

    def save_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """由所有 rank 调用官方 engine.save_checkpoint 并写完成标记。"""

        del model, optimizer
        client_state = {
            "schema": _DEEPSPEED_CHECKPOINT_SCHEMA,
            "topology": self.topology.checkpoint_identity(),
        }
        result = self._active_engine().save_checkpoint(
            str(path),
            tag="engine",
            client_state=client_state,
            save_latest=False,
        )
        if result is False:
            raise RuntimeError("DeepSpeed save_checkpoint reported failure")
        self.barrier()
        marker = path / "AUTOVLA_DEEPSPEED_COMPLETE.json"
        if self.is_primary:
            marker.write_text(
                json.dumps(client_state, sort_keys=True, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
        self.barrier()
        return {"backend": "deepspeed", "zero_stage": self._zero_stage}

    def validate_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """静态验证 DeepSpeed 完成标记与同拓扑身份。"""

        del model, optimizer
        marker = path / "AUTOVLA_DEEPSPEED_COMPLETE.json"
        if not marker.is_file():
            raise ValueError("DeepSpeed checkpoint completion marker is missing")
        payload = json.loads(marker.read_text(encoding="utf-8"))
        expected = {
            "schema": _DEEPSPEED_CHECKPOINT_SCHEMA,
            "topology": self.topology.checkpoint_identity(),
        }
        if payload != expected:
            raise ValueError("DeepSpeed checkpoint topology does not match current session")
        if not any(candidate.is_file() and candidate != marker for candidate in path.rglob("*")):
            raise ValueError("DeepSpeed checkpoint contains no engine shard files")
        return {"backend_validation": "completion_marker_and_shards"}

    def load_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        """通过官方 engine.load_checkpoint 恢复同拓扑 ZeRO 状态。"""

        del model, optimizer
        self.validate_sharded_checkpoint(path, self.model, self.optimizer)
        load_path, client_state = self._active_engine().load_checkpoint(
            str(path),
            tag="engine",
            load_module_strict=True,
            load_optimizer_states=True,
            load_lr_scheduler_states=True,
        )
        if load_path is None or not isinstance(client_state, Mapping):
            raise RuntimeError("DeepSpeed load_checkpoint did not restore a completed checkpoint")
        expected = {
            "schema": _DEEPSPEED_CHECKPOINT_SCHEMA,
            "topology": self.topology.checkpoint_identity(),
        }
        if dict(cast(Mapping[str, object], client_state)) != expected:
            raise ValueError("DeepSpeed restored client state has a different topology")

    def strategy_state_dict(self) -> Mapping[str, object]:
        """保存 DeepSpeed 配置、拓扑与提交计数身份。"""

        committed_steps = _committed_optimizer_steps(
            self._active_engine().global_steps,
            self._active_engine().skipped_steps,
        )
        if committed_steps != self._optimizer_steps:
            raise RuntimeError("DeepSpeed committed-step authority drifted before checkpoint")
        return {
            "name": type(self).__name__,
            "precision": self.precision.state_dict(),
            "topology": self.topology.checkpoint_identity(),
            "deepspeed_config": self._generated_config,
            "optimizer_steps": committed_steps,
        }

    def validate_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """要求相同 DeepSpeed 配置和拓扑恢复。"""

        expected = {"name", "precision", "topology", "deepspeed_config", "optimizer_steps"}
        if set(state) != expected:
            raise ValueError("DeepSpeed checkpoint session fields are incomplete or unknown")
        if state.get("name") != type(self).__name__:
            raise ValueError("DeepSpeed checkpoint session type differs")
        if state.get("topology") != self.topology.checkpoint_identity():
            raise ValueError("DeepSpeed changed-topology resume is unsupported")
        if state.get("deepspeed_config") != self._generated_config:
            raise ValueError("DeepSpeed config differs from checkpoint")
        precision = state.get("precision")
        if not isinstance(precision, Mapping):
            raise TypeError("DeepSpeed checkpoint precision state must be a mapping")
        self.precision.validate_state_dict(dict(cast(Mapping[str, object], precision)))
        optimizer_steps = state.get("optimizer_steps")
        if type(optimizer_steps) is not int or optimizer_steps < 0:
            raise ValueError("DeepSpeed checkpoint optimizer_steps must be non-negative")

    def load_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """恢复 DeepSpeed session 控制计数。"""

        self.validate_strategy_state_dict(state)
        precision = state["precision"]
        if not isinstance(precision, Mapping):
            raise TypeError("DeepSpeed checkpoint precision state must be a mapping")
        self.precision.load_state_dict(dict(cast(Mapping[str, object], precision)))
        optimizer_steps = state["optimizer_steps"]
        if type(optimizer_steps) is not int:
            raise TypeError("DeepSpeed checkpoint optimizer_steps must be an integer")
        engine_steps = _committed_optimizer_steps(
            self._active_engine().global_steps,
            self._active_engine().skipped_steps,
        )
        if engine_steps != optimizer_steps:
            raise ValueError("DeepSpeed engine counters differ from checkpoint session state")
        self._optimizer_steps = optimizer_steps
        self._pending_boundary = None
        self._backward_complete = False
        self._window_micro_steps = 0

    def load_scheduler_state_dict(self, state: Mapping[str, object]) -> None:
        """验证 engine 已恢复 scheduler,禁止公共 manager 重复加载。"""

        self.validate_scheduler_state_dict(state)
        if dict(self.scheduler.state_dict()) != dict(state):
            raise ValueError("DeepSpeed engine did not restore the expected scheduler state")

    def barrier(self) -> None:
        """同步 DeepSpeed 使用的 NCCL 进程组。"""

        if dist.is_initialized():
            _collectives.barrier()

    def close(self) -> None:
        """幂等回收 engine、引用和自有进程组,保留首个异常。"""

        if self._closed:
            return
        errors: list[BaseException] = []
        incomplete_step = self._pending_boundary is not None or self._backward_complete
        if incomplete_step:
            errors.append(RuntimeError("cannot close DeepSpeed session during a training step"))
        engine = self._engine
        process_group_owned = self._owns_process_group
        self._engine = None
        self._optimizer = None
        self._scheduler = None
        self._pending_boundary = None
        self._backward_complete = False
        self._window_micro_steps = 0
        self._device = None
        engine_status = "destroy_not_exposed"
        if engine is not None:
            destroy = getattr(engine, "destroy", None)
            if callable(destroy):
                try:
                    destroy()
                    engine_status = "destroyed"
                except BaseException as error:
                    engine_status = "failed"
                    errors.append(error)
        if process_group_owned and dist.is_initialized():
            try:
                dist.destroy_process_group()
                process_group_status = "destroyed"
                self._owns_process_group = False
            except BaseException as error:
                process_group_status = "failed"
                errors.append(error)
        elif process_group_owned:
            process_group_status = "already_absent"
            self._owns_process_group = False
        else:
            process_group_status = "preserved_external"
        self._closed = not self._owns_process_group
        self._teardown_receipt = StrategyTeardownReceipt(
            identity=self._session_identity,
            step_state_status="abandoned_incomplete_step" if incomplete_step else "clean",
            engine_status=engine_status,
            references_cleared=True,
            process_group_owned=process_group_owned,
            process_group_status=process_group_status,
            failure_types=tuple(type(error).__name__ for error in errors),
        )
        _raise_first_cleanup_error(errors)


class DeepSpeedStrategy:
    """通过一个 typed config 支持 ZeRO stage 1、2 和 3。"""

    def __init__(
        self,
        precision: PrecisionPolicy,
        *,
        expected_world_size: int,
        deepspeed_config: DeepSpeedConfig,
        micro_batch_size_per_gpu: int,
        gradient_accumulation_steps: int,
        gradient_clipping: float | None,
    ) -> None:
        """解析进程环境并生成确定性 DeepSpeed 配置。"""

        self._precision = precision
        self._topology = parse_distributed_topology(os.environ, strategy="deepspeed")
        if self._topology.world_size != expected_world_size:
            raise ValueError("configured world_size does not match torchrun WORLD_SIZE")
        self._deepspeed_config = deepspeed_config
        self._generated_config = deepspeed_config.to_deepspeed_dict(
            micro_batch_size_per_gpu=micro_batch_size_per_gpu,
            gradient_accumulation_steps=gradient_accumulation_steps,
            data_parallel_world_size=expected_world_size,
            gradient_clipping=gradient_clipping,
        )
        self._deepspeed_module: _DeepSpeedModule | None = None
        self._runtime_diagnostic: dict[str, object] = {
            "selected_version": deepspeed_config.version,
            "installed_version": None,
            "validation_status": "runtime_import_deferred",
            "validated_public_api_surface": (),
            "deferred_public_api_surface": DEEPSPEED_PUBLIC_API_SURFACE,
        }
        self._initialization = _ZeroInitializationTransaction(
            required=deepspeed_config.zero_stage == 3
        )

    @property
    def name(self) -> str:
        """返回规范策略键。"""

        return f"deepspeed_zero_{self._deepspeed_config.zero_stage}"

    @property
    def topology(self) -> TrainingTopology:
        """返回已验证 torchrun/DeepSpeed 拓扑。"""

        return self._topology

    @property
    def generated_config(self) -> Mapping[str, object]:
        """返回确定性只读配置视图。"""

        return dict(self._generated_config)

    @property
    def runtime_diagnostic(self) -> Mapping[str, object]:
        """报告 profile 选择版本、已安装版本和公共 API 验证状态。"""

        return dict(self._runtime_diagnostic)

    def _validated_deepspeed_module(self) -> _DeepSpeedModule:
        """延迟导入并保存 exact 版本/API 诊断。"""

        module, diagnostic = _load_deepspeed(self._deepspeed_config.version)
        self._deepspeed_module = module
        self._runtime_diagnostic = diagnostic
        return module

    def configure_process_environment(self) -> None:
        """在模型构造前验证 CUDA 并绑定 local rank。"""

        if not torch.cuda.is_available():
            raise RuntimeError("deepspeed strategy requires CUDA")
        if self.topology.local_rank >= torch.cuda.device_count():
            raise RuntimeError("LOCAL_RANK exceeds visible CUDA device count")
        torch.cuda.set_device(self.topology.device_index)

    def model_initialization_context(self) -> AbstractContextManager[None]:
        """为 ZeRO-3 交出一次性官方初始化上下文,其他 stage 不操作。"""

        if self._deepspeed_config.zero_stage != 3:
            return nullcontext()
        if self._initialization.state != "required":
            raise RuntimeError("DeepSpeed ZeRO-3 initialization context may be requested once")
        module = self._validated_deepspeed_module()
        self._initialization.issue()
        process_group_preexisting = dist.is_initialized()
        try:
            context = module.zero.Init(config_dict_or_path=self._generated_config)
        except BaseException as error:
            _destroy_initialization_process_group(
                self._initialization,
                process_group_preexisting=process_group_preexisting,
                primary_error=error,
            )
            raise
        return _ZeroInitializationContext(
            self._initialization,
            context,
            process_group_preexisting=process_group_preexisting,
        )

    def load_official_checkpoint(
        self,
        model: object,
        loader: Callable[[], OfficialCheckpointLoadT],
        /,
        *,
        partitioned_loader: (
            Callable[[], PartitionedCheckpointLoadSink[OfficialCheckpointLoadT]] | None
        ) = None,
    ) -> OfficialCheckpointLoadT:
        """让 family loader 在官方 ZeRO 分区参数协调边界内保持语义所有权。"""

        if self._deepspeed_config.zero_stage == 3:
            if self._initialization.state != "completed":
                raise RuntimeError(
                    "DeepSpeed ZeRO-3 official checkpoint loading requires completed "
                    "partition-aware construction"
                )
            if not isinstance(model, nn.Module):
                raise TypeError("DeepSpeed ZeRO-3 official checkpoint target must be nn.Module")
            module = self._deepspeed_module
            if module is None:
                raise RuntimeError("DeepSpeed ZeRO-3 initialization module is unavailable")
            if partitioned_loader is None:
                raise RuntimeError(
                    "DeepSpeed ZeRO-3 official checkpoint loading requires a "
                    "family-owned partitioned adapter"
                )
            if self.topology.world_size > 1 and not dist.is_initialized():
                raise RuntimeError(
                    "DeepSpeed ZeRO-3 partitioned loading requires initialized collectives"
                )
            parameter_inventory = tuple(
                (name, logical_parameter_shape(parameter))
                for name, parameter in model.named_parameters()
            )
            persistent_buffers = _persistent_named_buffers(model)
            buffer_inventory = tuple(
                (name, tuple(buffer.shape)) for name, buffer in persistent_buffers
            )
            parameter_names = tuple(name for name, _ in parameter_inventory)
            buffer_names = tuple(name for name, _ in buffer_inventory)
            if len(parameter_names) < 2:
                raise ValueError("DeepSpeed ZeRO-3 checkpoint groups must be strict model subsets")
            inventory = (parameter_inventory, buffer_inventory)
            if self.topology.world_size > 1:
                inventories: list[object] = [object() for _ in range(self.topology.world_size)]
                _collectives.all_gather_object(inventories, inventory)
                if any(value != inventory for value in inventories):
                    raise RuntimeError(
                        "DeepSpeed ZeRO-3 checkpoint tensor inventory differs across ranks"
                    )
            sink = partitioned_loader()
            if not isinstance(sink, PartitionedCheckpointLoadSink):
                raise TypeError(
                    "family partitioned checkpoint loader must satisfy the shared sink protocol"
                )
            rank = self.topology.rank
            world_size = self.topology.world_size
            _run_rank_zero_action(
                rank=rank,
                world_size=world_size,
                action=sink.prepare,
            )

            def audit_checkpoint() -> None:
                """在 rank 0 用纯 metadata inventory 一次完成严格全局审计。"""

                for name, logical_shape in parameter_inventory:
                    sink.audit_tensor(name, logical_shape)
                for name, logical_shape in buffer_inventory:
                    sink.audit_tensor(name, logical_shape)
                sink.complete_audit(
                    parameter_names=parameter_names,
                    buffer_names=buffer_names,
                )

            # metadata 审计只做一次状态广播,不进入 GatheredParameters。
            _run_rank_zero_action(
                rank=rank,
                world_size=world_size,
                action=audit_checkpoint,
            )

            # 每组恰含一个参数,上界为一且严格小于模型参数总数。
            for name, parameter in model.named_parameters():
                with module.zero.GatheredParameters((parameter,), modifier_rank=0):
                    _run_rank_zero_action(
                        rank=rank,
                        world_size=world_size,
                        action=lambda name=name, parameter=parameter: sink.load_tensor(
                            name,
                            parameter,
                        ),
                    )
                # modifier_rank=0 使修改在退出公共上下文时重新分片并同步。
            for name, buffer in persistent_buffers:
                _run_rank_zero_action(
                    rank=rank,
                    world_size=world_size,
                    action=lambda name=name, buffer=buffer: sink.load_tensor(name, buffer),
                )
                if world_size > 1:
                    # buffer 不受 ZeRO 参数分片管理,显式广播保持复制语义。
                    _collectives.broadcast(buffer, src=0)

            result_payloads: list[object] = [None]

            def finish() -> None:
                """在 rank 0 生成可传输的 family 证据载荷。"""

                result_payloads[0] = dict(sink.finish())

            _run_rank_zero_action(
                rank=rank,
                world_size=world_size,
                action=finish,
            )
            if world_size > 1:
                _collectives.broadcast_object_list(result_payloads, src=0)
            return sink.restore_result(_checkpoint_result_payload(result_payloads[0]))
        return loader()

    def prepare(
        self,
        *,
        model: nn.Module,
        config: TrainingConfig,
        optimizer_factory: OptimizerFactory,
        scheduler_factory: SchedulerFactory,
        batches_per_epoch: int,
    ) -> DeepSpeedTrainingSession:
        """事务式构造 ZeRO 运行时;stage 3 先进入官方分区构造边界。"""

        if (
            config.distributed.strategy_key != self.name
            or config.distributed.world_size != self.topology.world_size
            or config.distributed.deepspeed != self._deepspeed_config
        ):
            raise ValueError("DeepSpeed strategy preparation differs from AutoVLA config")
        if self._deepspeed_config.zero_stage == 3 and self._initialization.state != "completed":
            raise RuntimeError(
                "DeepSpeed ZeRO-3 model must be built inside model_initialization_context"
            )
        module = self._deepspeed_module or self._validated_deepspeed_module()
        process_group_preexisting = dist.is_initialized()
        owns_process_group = (
            self._initialization.owns_process_group or not process_group_preexisting
        )
        engine_value: object | None = None
        try:
            optimizer = optimizer_factory(model)
            scheduler = scheduler_factory(optimizer, batches_per_epoch)
            initialized = module.initialize(
                model=model,
                optimizer=optimizer,
                lr_scheduler=scheduler,
                config=self._generated_config,
                dist_init_required=None,
            )
            engine_value, optimizer_value, _, scheduler_value = initialized
            installed_version = self._runtime_diagnostic.get("installed_version")
            if type(installed_version) is not str:
                raise RuntimeError("DeepSpeed installed version diagnostic is unavailable")
            self._runtime_diagnostic = validate_deepspeed_engine_public_api(
                engine_value,
                selected_version=self._deepspeed_config.version,
                installed_version=installed_version,
            )
            if not isinstance(engine_value, _DeepSpeedEngine):
                raise TypeError("deepspeed.initialize returned an incompatible engine")
            if not isinstance(optimizer_value, torch.optim.Optimizer):
                optimizer_value = optimizer
            if not isinstance(scheduler_value, torch.optim.lr_scheduler.LRScheduler):
                scheduler_value = scheduler
            session = DeepSpeedTrainingSession(
                self._precision,
                engine=engine_value,
                optimizer=optimizer_value,
                scheduler=scheduler_value,
                config=config,
                topology=self.topology,
                generated_config=self._generated_config,
                owns_process_group=owns_process_group,
            )
            session.setup()
            return session
        except BaseException as error:
            try:
                _rollback_failed_prepare(
                    engine=engine_value,
                    process_group_preexisting=not owns_process_group,
                )
            except BaseException as cleanup_error:
                _append_cleanup_note(
                    error,
                    "DeepSpeed prepare rollback failed: " f"{type(cleanup_error).__name__}",
                )
            raise

    def close(self) -> None:
        """重试释放 ZeRO 初始化失败后仍由策略拥有的进程组。"""

        _retry_owned_initialization_process_group(self._initialization)


__all__ = ["DeepSpeedStrategy", "DeepSpeedTrainingSession"]
