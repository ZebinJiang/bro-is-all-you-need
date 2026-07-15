"""DeepSpeed ZeRO 1/2/3 官方公共 API 集成。"""

from __future__ import annotations

import importlib
import importlib.util
import json
import os
from collections.abc import Mapping, Sequence
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Protocol, cast, runtime_checkable

import torch
from torch import distributed as dist
from torch import nn

from autovla.config.schema.distributed import DeepSpeedConfig
from autovla.config.schema.training import TrainingConfig
from autovla.core.registry import OptionalDependencyError
from autovla.models.outputs import ModelInputBatch, ModelOutput
from autovla.training.precision import PrecisionPolicy
from autovla.training.session import (
    OptimizerFactory,
    OptimizerStepResult,
    PartitionedModelConstruction,
    PreparedTrainingSession,
    SchedulerFactory,
    TrainingTopology,
)
from autovla.training.strategy.base import CheckpointCollectiveStatus
from autovla.training.strategy.distributed_data_parallel import parse_distributed_topology

_DEEPSPEED_CHECKPOINT_SCHEMA = "autovla.deepspeed_checkpoint.v1"


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


class _DistributedCollectives(Protocol):
    """收窄 Torch 未完整标注的 collective 模块面。"""

    def all_reduce(self, tensor: torch.Tensor, *, op: object) -> object: ...

    def all_gather_object(self, output: list[object], value: object) -> None: ...

    def barrier(self) -> object: ...


_collectives = cast(_DistributedCollectives, cast(object, dist))


def _rollback_failed_prepare(
    *,
    engine: object | None,
    process_group_preexisting: bool,
) -> None:
    """回滚未提交的 DeepSpeed engine 与本次新建进程组。"""

    if engine is not None:
        destroy = getattr(engine, "destroy", None)
        if callable(destroy):
            destroy()
    if not process_group_preexisting and dist.is_initialized():
        dist.destroy_process_group()


def _load_deepspeed() -> _DeepSpeedModule:
    """仅在策略被选择时导入固定 profile 提供的 DeepSpeed。"""

    if importlib.util.find_spec("deepspeed") is None:
        raise OptionalDependencyError(
            "deepspeed strategy requires deepspeed==0.19.2; install training-deepspeed"
        )
    module: object = importlib.import_module("deepspeed")
    initialize: object = getattr(module, "initialize", None)
    if not callable(initialize):
        raise RuntimeError("installed DeepSpeed module lacks public initialize")
    return cast(_DeepSpeedModule, module)


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
        self._engine = engine
        self._optimizer = optimizer
        self._scheduler = scheduler
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
        if config.distributed.strategy_key != "deepspeed" or canonical_deepspeed is None:
            raise ValueError("DeepSpeed session requires canonical DeepSpeed training config")
        if canonical_deepspeed.zero_stage != self._zero_stage:
            raise ValueError("generated DeepSpeed ZeRO stage differs from AutoVLA config")
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
        self._pending_boundary: bool | None = None
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
        if not isinstance(engine, nn.Module):
            raise TypeError("DeepSpeedEngine must remain a torch.nn.Module")
        return engine

    @property
    def optimizer(self) -> torch.optim.Optimizer:
        """返回组合根创建并交给 DeepSpeed 的优化器句柄。"""

        return self._optimizer

    @property
    def scheduler(self) -> torch.optim.lr_scheduler.LRScheduler:
        """返回由 DeepSpeed step 驱动的调度器句柄。"""

        return self._scheduler

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

        boundary = self._engine.is_gradient_accumulation_boundary()
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
        output = self._engine(model_input)
        if not isinstance(output, ModelOutput):
            raise TypeError("training model must return ModelOutput")
        self._pending_boundary = natural
        return output

    def backward(self, loss: torch.Tensor) -> None:
        """把未预缩放标量损失直接交给 DeepSpeedEngine。"""

        if self._pending_boundary is None:
            raise RuntimeError("DeepSpeed backward requires a preceding forward")
        self._engine.backward(loss)

    def step(self, *, force_boundary: bool) -> OptimizerStepResult:
        """调用一次且仅一次 DeepSpeedEngine.step 并翻译提交状态。"""

        if type(force_boundary) is not bool:
            raise TypeError("force_boundary must be boolean")
        boundary = self._pending_boundary
        self._pending_boundary = None
        if boundary is None:
            raise RuntimeError("DeepSpeed step requires forward and backward")
        if force_boundary != boundary:
            raise RuntimeError("DeepSpeed step boundary changed after forward")
        before_steps = _require_engine_counter(self._engine.global_steps, "global_steps")
        before_skipped = _require_engine_counter(self._engine.skipped_steps, "skipped_steps")
        before_committed = _committed_optimizer_steps(before_steps, before_skipped)
        if before_committed != self._optimizer_steps:
            raise RuntimeError("DeepSpeed committed-step authority drifted before step")
        self._engine.step()
        after_steps = _require_engine_counter(self._engine.global_steps, "global_steps")
        after_skipped = _require_engine_counter(self._engine.skipped_steps, "skipped_steps")
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
        micro_step = _require_engine_counter(self._engine.micro_steps, "micro_steps")
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
            self._engine.zero_grad()
        finally:
            self._pending_boundary = None
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
            "topology": self.topology.to_dict(),
        }
        result = self._engine.save_checkpoint(
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
        expected = {"schema": _DEEPSPEED_CHECKPOINT_SCHEMA, "topology": self.topology.to_dict()}
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
        load_path, client_state = self._engine.load_checkpoint(
            str(path),
            tag="engine",
            load_module_strict=True,
            load_optimizer_states=True,
            load_lr_scheduler_states=True,
        )
        if load_path is None or not isinstance(client_state, Mapping):
            raise RuntimeError("DeepSpeed load_checkpoint did not restore a completed checkpoint")
        expected = {"schema": _DEEPSPEED_CHECKPOINT_SCHEMA, "topology": self.topology.to_dict()}
        if dict(cast(Mapping[str, object], client_state)) != expected:
            raise ValueError("DeepSpeed restored client state has a different topology")

    def strategy_state_dict(self) -> Mapping[str, object]:
        """保存 DeepSpeed 配置、拓扑与提交计数身份。"""

        committed_steps = _committed_optimizer_steps(
            self._engine.global_steps,
            self._engine.skipped_steps,
        )
        if committed_steps != self._optimizer_steps:
            raise RuntimeError("DeepSpeed committed-step authority drifted before checkpoint")
        return {
            "name": type(self).__name__,
            "precision": self.precision.state_dict(),
            "topology": self.topology.to_dict(),
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
        if state.get("topology") != self.topology.to_dict():
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
            self._engine.global_steps,
            self._engine.skipped_steps,
        )
        if engine_steps != optimizer_steps:
            raise ValueError("DeepSpeed engine counters differ from checkpoint session state")
        self._optimizer_steps = optimizer_steps
        self._pending_boundary = None
        self._window_micro_steps = 0

    def barrier(self) -> None:
        """同步 DeepSpeed 使用的 NCCL 进程组。"""

        if dist.is_initialized():
            _collectives.barrier()

    def close(self) -> None:
        """仅在本 session 触发初始化时销毁进程组。"""

        if self._pending_boundary is not None:
            raise RuntimeError("cannot close DeepSpeed session during a training step")
        if self._owns_process_group and dist.is_initialized():
            dist.destroy_process_group()
        self._owns_process_group = False
        self._window_micro_steps = 0
        self._device = None


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

    @property
    def name(self) -> str:
        """返回规范策略键。"""

        return "deepspeed"

    @property
    def topology(self) -> TrainingTopology:
        """返回已验证 torchrun/DeepSpeed 拓扑。"""

        return self._topology

    @property
    def generated_config(self) -> Mapping[str, object]:
        """返回确定性只读配置视图。"""

        return dict(self._generated_config)

    def configure_process_environment(self) -> None:
        """在模型构造前验证 CUDA 并绑定 local rank。"""

        if not torch.cuda.is_available():
            raise RuntimeError("deepspeed strategy requires CUDA")
        if self.topology.local_rank >= torch.cuda.device_count():
            raise RuntimeError("LOCAL_RANK exceeds visible CUDA device count")
        torch.cuda.set_device(self.topology.device_index)

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
        module = _load_deepspeed()
        process_group_preexisting = dist.is_initialized()
        engine_value: object | None = None
        try:
            if self._deepspeed_config.zero_stage == 3:
                if not isinstance(model, PartitionedModelConstruction):
                    raise TypeError("DeepSpeed ZeRO-3 requires partitioned model construction")
                # 模型参数与基础 checkpoint 加载都发生在官方 ZeRO.Init 边界内。
                with module.zero.Init(config_dict_or_path=self._generated_config):
                    model = model.construct_model()
            elif isinstance(model, PartitionedModelConstruction):
                raise TypeError("DeepSpeed ZeRO-1/2 require direct model construction")
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
                owns_process_group=not process_group_preexisting,
            )
            session.setup()
            return session
        except BaseException:
            _rollback_failed_prepare(
                engine=engine_value,
                process_group_preexisting=process_group_preexisting,
            )
            raise


__all__ = ["DeepSpeedStrategy", "DeepSpeedTrainingSession"]
