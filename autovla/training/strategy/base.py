"""生产训练策略抽象和公共状态语义。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping, Sequence
from contextlib import AbstractContextManager, nullcontext
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, TypeGuard

if TYPE_CHECKING:
    import torch
    from torch import nn

    from autovla.training.precision import PrecisionPolicy
else:
    try:
        import torch
    except ModuleNotFoundError:
        torch = None


_COLLECTIVE_STATUS_SCHEMA = "autovla.checkpoint_collective_status.v1"
_COLLECTIVE_PHASE_LIMIT = 96
_COLLECTIVE_CODE_LIMIT = 96
_COLLECTIVE_DETAIL_LIMIT = 512
_COLLECTIVE_MESSAGE_LIMIT = 4096


def _is_object_mapping(value: object) -> TypeGuard[Mapping[object, object]]:
    """判断动态值是否可作为对象映射读取。"""

    return isinstance(value, Mapping)


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """判断动态值是否为对象列表。"""

    return isinstance(value, list)


def _object_mapping(value: object, name: str) -> Mapping[object, object]:
    """把运行时值收窄为对象键值映射。"""

    if not _is_object_mapping(value):
        raise TypeError(f"{name} must be a mapping")
    return value


def _string_object_mapping(value: object, name: str) -> dict[str, object]:
    """逐键验证并复制字符串键映射。"""

    mapping = _object_mapping(value, name)
    result: dict[str, object] = {}
    for key, item in mapping.items():
        if not isinstance(key, str):
            raise TypeError(f"{name} keys must be strings")
        result[key] = item
    return result


def _object_list(value: object, name: str) -> list[object]:
    """把运行时列表收窄为对象列表。"""

    if not _is_object_list(value):
        raise TypeError(f"{name} must be a list")
    return value


def _bounded_status_text(value: str, limit: int) -> str:
    """把集体状态文本压缩到单行固定上限。"""

    normalized = " ".join(value[: limit * 2].split())
    return normalized[:limit]


@dataclass(frozen=True, slots=True)
class CheckpointCollectiveStatus:
    """表示一个 rank 在单个 checkpoint 集体阶段的有界结果。"""

    phase: str
    rank: int
    ok: bool
    code: str
    detail: str

    def __post_init__(self) -> None:
        """拒绝无界、歧义或不可稳定编码的状态。"""

        if not self.phase:
            raise ValueError("checkpoint collective phase must be nonempty text")
        if len(self.phase) > _COLLECTIVE_PHASE_LIMIT:
            raise ValueError("checkpoint collective phase exceeds the bounded limit")
        if type(self.rank) is not int or self.rank < 0:
            raise ValueError("checkpoint collective rank must be a non-negative integer")
        if type(self.ok) is not bool:
            raise TypeError("checkpoint collective outcome must be boolean")
        if not self.code:
            raise ValueError("checkpoint collective code must be nonempty text")
        if len(self.code) > _COLLECTIVE_CODE_LIMIT:
            raise ValueError("checkpoint collective code exceeds the bounded limit")
        if len(self.detail) > _COLLECTIVE_DETAIL_LIMIT:
            raise ValueError("checkpoint collective detail exceeds the bounded limit")
        if self.ok and (self.code != "OK" or self.detail):
            raise ValueError("successful checkpoint collective status must use OK with no detail")
        if not self.ok and self.code == "OK":
            raise ValueError("failed checkpoint collective status cannot use OK")

    @classmethod
    def success(cls, phase: str, rank: int) -> CheckpointCollectiveStatus:
        """构造成功状态。"""

        return cls(phase=phase, rank=rank, ok=True, code="OK", detail="")

    @classmethod
    def failure(
        cls,
        phase: str,
        rank: int,
        error: BaseException,
    ) -> CheckpointCollectiveStatus:
        """把本地异常转换成不携带异常对象的有界状态。"""

        try:
            detail = str(error)
        except BaseException:
            detail = "exception text unavailable"
        return cls(
            phase=phase,
            rank=rank,
            ok=False,
            code=_bounded_status_text(type(error).__name__, _COLLECTIVE_CODE_LIMIT)
            or "UnknownError",
            detail=_bounded_status_text(detail, _COLLECTIVE_DETAIL_LIMIT),
        )

    def to_payload(self) -> dict[str, object]:
        """返回仅含标量的集体传输载荷。"""

        return {
            "schema": _COLLECTIVE_STATUS_SCHEMA,
            "phase": self.phase,
            "rank": self.rank,
            "ok": self.ok,
            "code": self.code,
            "detail": self.detail,
        }

    @classmethod
    def from_payload(cls, payload: object) -> CheckpointCollectiveStatus:
        """从公共集体载荷严格恢复状态。"""

        values = _object_mapping(payload, "checkpoint collective payload")
        expected = {"schema", "phase", "rank", "ok", "code", "detail"}
        if set(values) != expected or values.get("schema") != _COLLECTIVE_STATUS_SCHEMA:
            raise ValueError("checkpoint collective payload schema is invalid")
        phase = values["phase"]
        rank = values["rank"]
        ok = values["ok"]
        code = values["code"]
        detail = values["detail"]
        if not isinstance(phase, str) or type(rank) is not int or type(ok) is not bool:
            raise TypeError("checkpoint collective payload scalar types are invalid")
        if not isinstance(code, str) or not isinstance(detail, str):
            raise TypeError("checkpoint collective payload text fields are invalid")
        return cls(
            phase=phase,
            rank=rank,
            ok=ok,
            code=code,
            detail=detail,
        )


class CheckpointCollectiveTransport(Protocol):
    """约束 checkpoint 控制协议所需的最小集体传输面。"""

    @property
    def rank(self) -> int:
        """返回本地 rank。"""

        ...

    @property
    def world_size(self) -> int:
        """返回参与协议的 rank 数。"""

        ...

    @property
    def is_primary(self) -> bool:
        """返回本地是否为 rank 0。"""

        ...

    def gather_checkpoint_status(
        self,
        status: CheckpointCollectiveStatus,
    ) -> Sequence[CheckpointCollectiveStatus]:
        """按 rank 顺序收集一个阶段的结构化状态。"""

        ...

    def barrier(self) -> None:
        """等待全部 rank 到达共同阶段边界。"""

        ...


class CheckpointCollectiveError(RuntimeError):
    """报告全部 rank 已共同完成失败处理后的 checkpoint 结论。"""

    def __init__(self, statuses: Sequence[CheckpointCollectiveStatus]) -> None:
        """用确定顺序和固定上限构造所有 rank 相同的错误。"""

        failures = tuple(status for status in statuses if not status.ok)
        if not failures:
            raise ValueError("checkpoint collective error requires at least one failure")
        detail = "; ".join(
            f"phase={status.phase},rank={status.rank},code={status.code},detail={status.detail}"
            for status in failures
        )
        message = (
            "checkpoint collective operation failed; all ranks reached a common decision; "
            "restart all ranks before retrying from a completed checkpoint; "
            f"{detail}"
        )
        super().__init__(message[:_COLLECTIVE_MESSAGE_LIMIT])
        self.statuses = failures


class CheckpointCollectiveProtocol:
    """保证 checkpoint 分支只在全体 rank 形成同一结论后发生。"""

    def __init__(self, transport: CheckpointCollectiveTransport) -> None:
        """绑定一个提供有序状态集合和 barrier 的传输。"""

        if transport.world_size <= 0:
            raise ValueError("checkpoint collective world size must be positive")
        if transport.rank < 0 or transport.rank >= transport.world_size:
            raise ValueError("checkpoint collective local rank is out of range")
        self._transport = transport

    def _local_status(
        self,
        phase: str,
        action: Callable[[], object],
        *,
        primary_only: bool,
    ) -> CheckpointCollectiveStatus:
        """执行本 rank 动作并把异常收窄为结构化状态。"""

        if primary_only and not self._transport.is_primary:
            return CheckpointCollectiveStatus.success(phase, self._transport.rank)
        try:
            action()
        except BaseException as error:
            return CheckpointCollectiveStatus.failure(phase, self._transport.rank, error)
        return CheckpointCollectiveStatus.success(phase, self._transport.rank)

    def _gather(
        self,
        local_status: CheckpointCollectiveStatus,
    ) -> tuple[CheckpointCollectiveStatus, ...]:
        """收集并验证全体 rank 的同阶段有序结果。"""

        gathered = tuple(self._transport.gather_checkpoint_status(local_status))
        if len(gathered) != self._transport.world_size:
            raise RuntimeError("checkpoint collective status count does not match world size")
        for expected_rank, status in enumerate(gathered):
            if status.rank != expected_rank or status.phase != local_status.phase:
                raise RuntimeError("checkpoint collective status order or phase is inconsistent")
        return gathered

    def run_phase(
        self,
        phase: str,
        action: Callable[[], object],
        *,
        primary_only: bool = False,
        cleanup: Callable[[], object] | None = None,
        cleanup_primary_only: bool = True,
    ) -> None:
        """共同决定一个阶段;失败时共同完成可选清理后再抛错。"""

        statuses = self._gather(self._local_status(phase, action, primary_only=primary_only))
        failures: tuple[CheckpointCollectiveStatus, ...] = tuple(
            status for status in statuses if not status.ok
        )
        cleanup_statuses: tuple[CheckpointCollectiveStatus, ...] = ()
        if failures and cleanup is not None:
            cleanup_phase = f"{phase}.cleanup"
            cleanup_statuses = self._gather(
                self._local_status(
                    cleanup_phase,
                    cleanup,
                    primary_only=cleanup_primary_only,
                )
            )
        self._transport.barrier()
        combined = (*statuses, *cleanup_statuses)
        if any(not status.ok for status in combined):
            raise CheckpointCollectiveError(combined)

    def run_apply_with_rollback(
        self,
        *,
        apply: Callable[[], object],
        rollback: Callable[[], object],
        cleanup: Callable[[], object],
    ) -> None:
        """先共同决定应用结果,失败时让全部 rank 同序回滚和清理。"""

        apply_statuses = self._gather(
            self._local_status("restore.apply", apply, primary_only=False)
        )
        rollback_statuses: tuple[CheckpointCollectiveStatus, ...] = ()
        if any(not status.ok for status in apply_statuses):
            rollback_statuses = self._gather(
                self._local_status("restore.rollback", rollback, primary_only=False)
            )
        cleanup_statuses = self._gather(
            self._local_status("restore.cleanup", cleanup, primary_only=True)
        )
        self._transport.barrier()
        combined = (*apply_statuses, *rollback_statuses, *cleanup_statuses)
        if any(not status.ok for status in combined):
            raise CheckpointCollectiveError(combined)


class PreparedTrainingSessionBase(ABC):
    """提供 session 共用的设备、collective 和 checkpoint 状态能力。"""

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
    def local_rank(self) -> int:
        """返回当前节点内的进程编号。"""

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
            payload = _string_object_mapping(value, "rank runtime state payload")
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

    def validate_model_state_dict(
        self,
        model: nn.Module,
        state: Mapping[str, torch.Tensor],
    ) -> None:
        """不修改模型地验证完整键、形状和 dtype。"""

        expected = self.model_state_dict(model)
        if set(state) != set(expected):
            missing = sorted(set(expected) - set(state))
            unexpected = sorted(set(state) - set(expected))
            raise ValueError(
                f"checkpoint model keys mismatch: missing={missing}, unexpected={unexpected}"
            )
        for name, tensor in state.items():
            current = expected[name]
            if tensor.shape != current.shape or tensor.dtype != current.dtype:
                raise ValueError(
                    f"checkpoint model tensor mismatch for {name!r}: "
                    f"shape={tuple(tensor.shape)}/{tuple(current.shape)}, "
                    f"dtype={tensor.dtype}/{current.dtype}"
                )
            if tensor.is_floating_point() and not bool(torch.isfinite(tensor).all()):
                raise ValueError(f"checkpoint model tensor {name!r} must be finite")

    def optimizer_state_dict(self, optimizer: torch.optim.Optimizer) -> Mapping[str, object]:
        """物化优化器状态。"""

        return optimizer.state_dict()

    def load_optimizer_state_dict(
        self, optimizer: torch.optim.Optimizer, state: Mapping[str, object]
    ) -> None:
        """恢复优化器状态。"""

        optimizer.load_state_dict(dict(state))

    def validate_optimizer_state_dict(
        self,
        optimizer: torch.optim.Optimizer,
        state: Mapping[str, object],
    ) -> None:
        """不修改优化器地验证参数组、参数身份和 tensor 状态。"""

        if set(state) != {"state", "param_groups"}:
            raise ValueError("checkpoint optimizer fields are incomplete or unknown")
        saved_groups = _object_list(state.get("param_groups"), "checkpoint optimizer param_groups")
        saved_state = _object_mapping(state.get("state"), "checkpoint optimizer state")
        current = _string_object_mapping(optimizer.state_dict(), "current optimizer state")
        current_groups = _object_list(current.get("param_groups"), "current optimizer param_groups")
        live_groups = _object_list(optimizer.param_groups, "live optimizer param_groups")
        if len(saved_groups) != len(current_groups):
            raise ValueError("checkpoint optimizer parameter-group count mismatch")
        parameter_by_id: dict[int, torch.Tensor] = {}
        for raw_live_group, raw_saved_group, raw_current_group in zip(
            live_groups,
            saved_groups,
            current_groups,
            strict=True,
        ):
            live_group = _string_object_mapping(raw_live_group, "live optimizer parameter group")
            saved_group = _string_object_mapping(
                raw_saved_group, "checkpoint optimizer parameter group"
            )
            current_group = _string_object_mapping(
                raw_current_group, "current optimizer parameter group"
            )
            saved_parameters = _object_list(
                saved_group.get("params"), "checkpoint optimizer parameters"
            )
            _object_list(current_group.get("params"), "current optimizer parameters")
            live_parameters = _object_list(live_group.get("params"), "live optimizer parameters")
            if len(saved_parameters) != len(live_parameters):
                raise ValueError("checkpoint optimizer parameter-group width mismatch")
            if set(saved_group) != set(current_group):
                raise ValueError("checkpoint optimizer parameter-group fields mismatch")
            for name, saved_value in saved_group.items():
                if name == "params":
                    continue
                current_value = current_group[name]
                if current_value is not None and type(saved_value) is not type(current_value):
                    raise TypeError(
                        f"checkpoint optimizer parameter-group field {name!r} has invalid type"
                    )
            for identifier, parameter in zip(saved_parameters, live_parameters, strict=True):
                if type(identifier) is not int or not isinstance(parameter, torch.Tensor):
                    raise TypeError("checkpoint optimizer parameter identity is invalid")
                if identifier in parameter_by_id:
                    raise ValueError("checkpoint optimizer parameter identity is duplicated")
                parameter_by_id[identifier] = parameter
        if not set(saved_state).issubset(parameter_by_id):
            raise ValueError("checkpoint optimizer state references an unknown parameter")
        for identifier, raw_item in saved_state.items():
            if type(identifier) is not int:
                raise TypeError("checkpoint optimizer per-parameter state is invalid")
            item = _string_object_mapping(raw_item, "checkpoint optimizer parameter state")
            parameter = parameter_by_id[identifier]
            if isinstance(optimizer, torch.optim.AdamW):
                required = {"step", "exp_avg", "exp_avg_sq"}
                allowed = required | {"max_exp_avg_sq"}
                if not required.issubset(item) or not set(item).issubset(allowed):
                    raise ValueError("checkpoint AdamW state fields are incomplete or unknown")
            for name, value in item.items():
                if isinstance(value, torch.Tensor) and value.is_floating_point():
                    if not bool(torch.isfinite(value).all()):
                        raise ValueError(f"checkpoint optimizer tensor {name!r} must be finite")
                if isinstance(value, torch.Tensor) and value.numel() != 1:
                    if value.shape != parameter.shape:
                        raise ValueError(f"checkpoint optimizer tensor {name!r} shape mismatch")
                    if value.dtype != parameter.dtype:
                        raise ValueError(f"checkpoint optimizer tensor {name!r} dtype mismatch")

    def strategy_state_dict(self) -> Mapping[str, object]:
        """返回精度及策略身份状态。"""

        return {"name": type(self).__name__, "precision": self.precision.state_dict()}

    def load_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """校验策略身份并恢复精度状态。"""

        self.validate_strategy_state_dict(state)
        precision = _string_object_mapping(state.get("precision"), "checkpoint precision state")
        self.precision.load_state_dict(precision)

    def validate_strategy_state_dict(self, state: Mapping[str, object]) -> None:
        """不修改策略地验证身份和精度状态。"""

        if set(state) != {"name", "precision"}:
            raise ValueError("checkpoint strategy fields are incomplete or unknown")
        if state.get("name") != type(self).__name__:
            raise ValueError("checkpoint strategy does not match current strategy")
        precision: object = state.get("precision")
        if not _is_object_mapping(precision):
            raise ValueError("checkpoint strategy lacks precision state")
        self.precision.validate_state_dict(
            _string_object_mapping(precision, "checkpoint precision state")
        )

    @property
    def uses_sharded_checkpoint(self) -> bool:
        """声明是否由策略使用公共 DCP 目录保存模型和优化器。"""

        return False

    def save_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """保存策略拥有的分片状态;普通策略拒绝该路径。"""

        del path, model, optimizer
        raise RuntimeError("selected strategy does not support sharded checkpoints")

    def validate_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> Mapping[str, object]:
        """非变异验证分片目录;普通策略拒绝该路径。"""

        del path, model, optimizer
        raise RuntimeError("selected strategy does not support sharded checkpoints")

    def load_sharded_checkpoint(
        self,
        path: Path,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ) -> None:
        """恢复策略拥有的分片状态;普通策略拒绝该路径。"""

        del path, model, optimizer
        raise RuntimeError("selected strategy does not support sharded checkpoints")

    def gather_checkpoint_status(
        self,
        status: CheckpointCollectiveStatus,
    ) -> Sequence[CheckpointCollectiveStatus]:
        """为单进程策略返回唯一的本地 checkpoint 状态。"""

        if status.rank != self.rank or self.world_size != 1:
            raise RuntimeError("local checkpoint collective topology is inconsistent")
        return (status,)

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


__all__ = [
    "CheckpointCollectiveError",
    "CheckpointCollectiveProtocol",
    "CheckpointCollectiveStatus",
    "CheckpointCollectiveTransport",
    "PreparedTrainingSessionBase",
    "require_local_checkpoint_root",
]
