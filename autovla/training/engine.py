"""AutoVLA 可读、显式且可恢复的生产训练引擎。"""

from __future__ import annotations

import time
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Protocol, TypeGuard, runtime_checkable

import torch

from autovla.core.types.training import TrainingBatch
from autovla.data.sampling import PartitionContext
from autovla.data.types import DataStage
from autovla.models.outputs import ModelOutput
from autovla.training.context import TrainingContext
from autovla.training.state import StepStatus, StopReason, TrainingState
from autovla.training.step import TrainingStepOutput
from autovla.training.telemetry.metrics import TrainingMetrics
from autovla.training.telemetry.timers import PhaseTimers


@runtime_checkable
class _TrainingLoader(Protocol):
    """约束训练引擎消费的有界 loader 接口。"""

    def __iter__(self) -> Iterator[TrainingBatch]: ...

    def __len__(self) -> int: ...


def _is_object_list(value: object) -> TypeGuard[list[object]]:
    """判断动态异常属性是否为对象列表。"""

    return isinstance(value, list)


def _require_training_loader(loader: object) -> _TrainingLoader:
    """运行时校验 loader 同时提供长度和规范批迭代。"""

    if not isinstance(loader, _TrainingLoader):
        raise TypeError("DataModule must return an iterable training loader with a length")
    return loader


def _add_exception_note(
    error: BaseException,
    prefix: str,
    secondary_error: BaseException,
) -> None:
    """安全渲染并附加次要异常,任何失败都不遮蔽原始异常。"""

    try:
        original_args = error.args
    except BaseException:
        original_args = None
    try:
        try:
            rendered = repr(secondary_error)
        except BaseException:
            rendered = "<secondary exception representation unavailable>"
        try:
            note = f"{prefix}: {rendered}"
        except BaseException:
            note = "secondary exception unavailable"
        try:
            native = getattr(error, "add_note", None)
        except BaseException:
            native = None
        if callable(native):
            try:
                native(note)
                return
            except BaseException:
                pass
        try:
            notes = getattr(error, "__notes__", None)
        except BaseException:
            notes = None
        if _is_object_list(notes):
            note_list = notes
        else:
            note_list = []
            try:
                error.__dict__["__notes__"] = note_list
            except BaseException:
                return
        try:
            note_list.append(note)
        except BaseException:
            return
    finally:
        if original_args is not None:
            try:
                error.args = original_args
            except BaseException:
                pass


def _require_training_batch(batch: object) -> TrainingBatch:
    """在运行时边界校验并返回规范 TrainingBatch。"""

    if not isinstance(batch, TrainingBatch):
        raise TypeError("DataModule must yield canonical TrainingBatch instances")
    return batch


class CheckpointReason(str, Enum):
    """声明生产 checkpoint 的保存触发原因。"""

    SCHEDULED = "scheduled"
    FINAL = "final"
    MANUAL = "manual"
    INTERRUPTED = "interrupted"
    EXCEPTION = "exception"


class TrainingEngine:
    """按固定顺序协调 DataModule、处理器、模型、策略和持久化。"""

    def __init__(self, context: TrainingContext) -> None:
        """保存无副作用组件上下文。"""

        self.context = context
        self._setup = False
        self._closed = False
        self._force_accumulation_boundary = False
        self._is_final_loader_batch = False
        self._deferred_optimizer_step_output: TrainingStepOutput | None = None
        self._deferred_scheduled_checkpoint = False
        self._data_wait_seconds = 0.0

    @property
    def state(self) -> TrainingState:
        """返回当前可恢复训练状态。"""

        return self.context.state

    def setup(self) -> None:
        """按策略拓扑、模型、优化器、Data、调度器顺序建立运行时。"""

        if self._closed:
            raise RuntimeError("training engine is closed")
        if self._setup:
            return
        try:
            self.context.strategy.setup()
            self.context.data_module.bind_partition(
                PartitionContext(
                    rank=self.context.strategy.rank,
                    local_rank=self.context.strategy.local_rank,
                    world_size=self.context.strategy.world_size,
                )
            )
            prepared = self.context.strategy.prepare_model(self.context.model)
            self.context.model = prepared
            if self.context.optimizer_factory is not None:
                if self.context.optimizer is not None:
                    raise ValueError("optimizer and optimizer_factory are mutually exclusive")
                optimizer = self.context.optimizer_factory(prepared)
            else:
                if self.context.optimizer is None:
                    raise ValueError("training context requires an optimizer or optimizer_factory")
                if self.context.strategy.requires_post_prepare_optimizer:
                    raise ValueError(
                        "selected strategy requires optimizer construction after model preparation"
                    )
                optimizer = self.context.optimizer
            prepared_optimizer = self.context.strategy.prepare_optimizer(optimizer)
            self.context.optimizer = prepared_optimizer
            self.context.data_module.setup(DataStage.FIT)
            loader = _require_training_loader(self.context.data_module.train_dataloader())
            if self.context.scheduler_factory is not None:
                if self.context.scheduler is not None:
                    raise ValueError("scheduler and scheduler_factory are mutually exclusive")
                self.context.scheduler = self.context.scheduler_factory(
                    prepared_optimizer,
                    len(loader),
                )
            elif self.context.scheduler is None:
                raise ValueError("training context requires a scheduler or scheduler_factory")
            prepared_optimizer.zero_grad(set_to_none=True)
            if self.context.resume_from is not None:
                self.load_checkpoint(self.context.resume_from)
        except BaseException as error:
            reason = (
                StopReason.INTERRUPTED
                if isinstance(error, KeyboardInterrupt)
                else StopReason.EXCEPTION
            )
            self.state.request_stop(reason)
            self._call_on_exception(error)
            self._close_after_error(error)
            raise
        self._setup = True

    def fit(self) -> TrainingState:
        """运行配置限定的 epoch,并保证异常 callback 与资源清理。"""

        try:
            self.setup()
            self._call("on_fit_start", self.state)
            while self.state.epoch < self.context.config.epochs and not self.state.should_stop:
                self.train_epoch()
            if self.state.stop_reason is None:
                self.state.request_stop(StopReason.EPOCHS_COMPLETED)
            clean_stop = self.state.stop_reason in {
                StopReason.EPOCHS_COMPLETED,
                StopReason.MAX_STEPS,
            } or (
                self.state.stop_reason is StopReason.CALLBACK_REQUEST
                and self.state.microbatch_step == 0
            )
            if self.context.config.checkpoint.save_final and clean_stop:
                self.save_checkpoint(CheckpointReason.FINAL)
            self._call("on_fit_end", self.state)
        except KeyboardInterrupt as error:
            self.state.request_stop(StopReason.INTERRUPTED)
            if not self._closed:
                self._call_on_exception(error)
                self._close_after_error(error)
            raise
        except BaseException as error:
            self.state.request_stop(StopReason.EXCEPTION)
            if not self._closed:
                self._call_on_exception(error)
                self._close_after_error(error)
            raise
        self.close()
        return self.state

    def train_epoch(self) -> TrainingState:
        """迭代一个 DataModule epoch,测量每批等待时间并处理末尾累积窗口。"""

        if not self._setup:
            raise RuntimeError("training engine is not set up")
        if self._max_steps_reached():
            self.state.request_stop(StopReason.MAX_STEPS)
            return self.state
        self._force_accumulation_boundary = False
        self._is_final_loader_batch = False
        self._deferred_optimizer_step_output = None
        self._deferred_scheduled_checkpoint = False
        self._call("on_epoch_start", self.state)
        loader = _require_training_loader(self.context.data_module.train_dataloader())
        total_batches = len(loader)
        iterator = iter(loader)
        consumed_final_loader_batch = False
        for index in range(total_batches):
            if self._max_steps_reached():
                self.state.request_stop(StopReason.MAX_STEPS)
                break
            started = time.perf_counter()
            try:
                batch = _require_training_batch(next(iterator))
            except StopIteration as error:
                raise RuntimeError(
                    f"training loader underflow: declared {total_batches} batches, "
                    f"delivered {index}"
                ) from error
            self._data_wait_seconds = time.perf_counter() - started
            max_steps = self.context.config.max_steps
            reaches_limit = max_steps is not None and self.state.global_step + 1 >= max_steps
            self._is_final_loader_batch = index + 1 == total_batches
            self._force_accumulation_boundary = self._is_final_loader_batch or reaches_limit
            try:
                self.train_step(batch)
            finally:
                consumed_final_loader_batch = self._is_final_loader_batch
                self._is_final_loader_batch = False
                self._force_accumulation_boundary = False
            if self.state.should_stop:
                break
        terminally_exhausted = False
        if total_batches == 0 and not self.state.should_stop:
            try:
                next(iterator)
            except StopIteration:
                terminally_exhausted = True
            else:
                raise RuntimeError("training loader overflow: declared zero batches")
        elif consumed_final_loader_batch:
            try:
                next(iterator)
            except StopIteration:
                terminally_exhausted = True
            else:
                raise RuntimeError(
                    f"training loader overflow: declared {total_batches} batches but delivered more"
                )
        if not terminally_exhausted:
            close_iterator = getattr(iterator, "close", None)
            if callable(close_iterator):
                close_iterator()
        completed_empty_loader = total_batches == 0 and terminally_exhausted
        commit_completed_epoch = completed_empty_loader or (
            consumed_final_loader_batch
            and terminally_exhausted
            and (
                not self.state.should_stop
                or self.state.stop_reason is StopReason.MAX_STEPS
                or self._deferred_optimizer_step_output is not None
                or self._deferred_scheduled_checkpoint
            )
        )
        if commit_completed_epoch:
            self.state.epoch += 1
            self.state.resume_seed += 1
        deferred_optimizer_step_output = self._deferred_optimizer_step_output
        deferred_scheduled_checkpoint = self._deferred_scheduled_checkpoint
        self._deferred_optimizer_step_output = None
        self._deferred_scheduled_checkpoint = False
        if deferred_optimizer_step_output is not None:
            self._call("on_optimizer_step", self.state, deferred_optimizer_step_output)
        if deferred_scheduled_checkpoint:
            self.save_checkpoint(CheckpointReason.SCHEDULED)
        self._call("on_epoch_end", self.state)
        return self.state

    def train_step(self, batch: TrainingBatch) -> TrainingStepOutput:
        """按规范顺序执行一个微批次并返回显式更新状态。"""

        if not self._setup:
            raise RuntimeError("training engine is not set up")
        self._call("on_step_start", self.state)
        timers = PhaseTimers()
        timers.add("data_wait", self._data_wait_seconds)
        self._data_wait_seconds = 0.0

        # 1. 处理器拥有 CPU batch 到设备张量的转换。
        with timers.measure("processor"):
            model_batch = self.context.processor.prepare_batch(
                batch,
                device=self.context.strategy.device,
                dtype=self.context.strategy.precision.model_dtype,
                training=True,
            )

        accumulation = self.context.config.gradient_accumulation_steps
        max_steps = self.context.config.max_steps
        reaches_limit = max_steps is not None and self.state.global_step + 1 >= max_steps
        boundary = (
            (self.state.microbatch_step + 1) % accumulation == 0
            or self._force_accumulation_boundary
            or reaches_limit
        )
        window_size = self.state.microbatch_step + 1

        # 2. DDP/FSDP2 非边界上下文同时包围前向和反向,边界批次保持同步。
        with self.context.strategy.accumulation_context(
            self.context.model,
            synchronize=boundary,
        ):
            with timers.measure("forward"):
                with self.context.strategy.autocast():
                    raw_model_output: object = self.context.model(model_batch)
                    if not isinstance(raw_model_output, ModelOutput):
                        raise TypeError("training model must return ModelOutput")
                    model_output = raw_model_output
                loss = model_output.loss
            if loss.numel() != 1:
                raise ValueError("training loss must contain exactly one scalar")
            finite = self.context.strategy.all_finite(bool(torch.isfinite(loss.detach()).item()))
            if not finite:
                optimizer = self.context.optimizer
                if optimizer is None:
                    raise RuntimeError("optimizer must exist after setup")
                optimizer.zero_grad(set_to_none=True)
                self.state.record_step(
                    status=StepStatus.NONFINITE,
                    batch_size=batch.batch_size,
                    loss=None,
                    accumulation_steps=accumulation,
                    optimizer_updated=False,
                    gradient_window_reset=True,
                )
                self.state.request_stop(StopReason.NONFINITE_LOSS)
                output = TrainingStepOutput(
                    status=StepStatus.NONFINITE,
                    loss=None,
                    scaled_loss=None,
                    batch_size=batch.batch_size,
                    optimizer_updated=False,
                    message="non-finite loss observed on at least one rank",
                )
                self._call("on_step_end", self.state, output)
                return output

            loss_value = self.context.strategy.reduce_mean(float(loss.detach().float().item()))
            scaled_loss = loss / accumulation

            # 3. 强制短窗口在更新前修正为实际 k 项平均。
            with timers.measure("backward"):
                self.context.strategy.backward(scaled_loss)
        optimizer_updated = False
        gradient_norm: float | None = None
        status = StepStatus.COMPLETED
        if boundary:
            # 4. 边界顺序固定为 unscale、clip、optimizer、scheduler、zero-grad。
            with timers.measure("optimizer"):
                if window_size < accumulation:
                    self.context.strategy.scale_gradients(
                        self.context.model,
                        accumulation / window_size,
                    )
                if self.context.optimizer is None or self.context.scheduler is None:
                    raise RuntimeError("optimizer and scheduler must exist after setup")
                self.context.strategy.unscale(self.context.optimizer)
                if self.context.config.gradient_clip_norm is not None:
                    gradient_norm = self.context.strategy.clip_gradients(
                        self.context.model,
                        self.context.config.gradient_clip_norm,
                    )
                optimizer_updated = self.context.strategy.optimizer_step(self.context.optimizer)
                if optimizer_updated:
                    self.context.scheduler.step()
                else:
                    status = StepStatus.SKIPPED
                self.context.optimizer.zero_grad(set_to_none=True)

        self.state.record_step(
            status=status,
            batch_size=batch.batch_size,
            loss=loss_value,
            accumulation_steps=accumulation,
            optimizer_updated=optimizer_updated,
            gradient_window_reset=boundary,
        )
        if self._max_steps_reached():
            self.state.request_stop(StopReason.MAX_STEPS)
        metrics = self._metrics(
            loss=loss_value,
            gradient_norm=gradient_norm,
            batch_size=batch.batch_size,
            timers=timers,
        )
        output = TrainingStepOutput(
            status=status,
            loss=loss_value,
            scaled_loss=loss_value / accumulation,
            batch_size=batch.batch_size,
            optimizer_updated=optimizer_updated,
            gradient_norm=gradient_norm,
            metrics={
                key: float(value) for key, value in metrics.to_dict().items() if value is not None
            },
        )

        # 5. 状态和指标先完成,再通知 callbacks,最后执行 checkpoint cadence。
        self._call("on_step_end", self.state, output)
        if optimizer_updated:
            if self._is_final_loader_batch:
                self._deferred_optimizer_step_output = output
            else:
                self._call("on_optimizer_step", self.state, output)
            cadence = self.context.config.checkpoint.save_every_steps
            if cadence is not None and self.state.optimizer_step % cadence == 0:
                if self._is_final_loader_batch:
                    self._deferred_scheduled_checkpoint = True
                else:
                    self.save_checkpoint(CheckpointReason.SCHEDULED)
        return output

    def _metrics(
        self,
        *,
        loss: float,
        gradient_norm: float | None,
        batch_size: int,
        timers: PhaseTimers,
    ) -> TrainingMetrics:
        """从计时器、优化器和可选 CUDA 状态生成完整遥测。"""

        elapsed = sum(
            timers.value(name)
            for name in ("data_wait", "processor", "forward", "backward", "optimizer")
        )
        memory_allocated: int | None = None
        memory_reserved: int | None = None
        if self.context.strategy.device.type == "cuda":
            memory_allocated = torch.cuda.memory_allocated(self.context.strategy.device)
            memory_reserved = torch.cuda.memory_reserved(self.context.strategy.device)
        if self.context.optimizer is None:
            raise RuntimeError("optimizer must exist after setup")
        learning_rate = float(self.context.optimizer.param_groups[0]["lr"])
        return TrainingMetrics(
            loss=loss,
            learning_rate=learning_rate,
            gradient_norm=gradient_norm,
            data_wait_seconds=timers.value("data_wait"),
            processor_seconds=timers.value("processor"),
            forward_seconds=timers.value("forward"),
            backward_seconds=timers.value("backward"),
            optimizer_seconds=timers.value("optimizer"),
            samples_per_second=0.0 if elapsed == 0.0 else batch_size / elapsed,
            memory_allocated_bytes=memory_allocated,
            memory_reserved_bytes=memory_reserved,
        )

    def save_checkpoint(self, reason: CheckpointReason) -> Path:
        """委托 CheckpointManager 保存并发送完成事件。"""

        if self.context.optimizer is None or self.context.scheduler is None:
            raise RuntimeError("optimizer and scheduler must exist before checkpoint save")
        path = self.context.checkpoint_manager.save(
            model=self.context.model,
            optimizer=self.context.optimizer,
            scheduler=self.context.scheduler,
            strategy=self.context.strategy,
            data_module=self.context.data_module,
            callbacks=self.context.callbacks,
            metric_logger=self.context.metric_logger,
            state=self.state,
            reason=reason.value,
        )
        self._call("on_checkpoint_saved", self.state, path, reason.value)
        return path

    def load_checkpoint(self, path: Path) -> TrainingState:
        """在 setup 阶段恢复完整生产训练状态。"""

        if self.context.optimizer is None or self.context.scheduler is None:
            raise RuntimeError("optimizer and scheduler must exist before checkpoint load")
        restored = self.context.checkpoint_manager.load(
            path,
            model=self.context.model,
            optimizer=self.context.optimizer,
            scheduler=self.context.scheduler,
            strategy=self.context.strategy,
            data_module=self.context.data_module,
            family_adapter=self.context.family_checkpoint_adapter,
            callbacks=self.context.callbacks,
            metric_logger=self.context.metric_logger,
        )
        self.context.state = restored
        self.context.strategy.barrier()
        return restored

    def close(self) -> None:
        """幂等关闭 logger、DataModule 和策略,并保留首个清理异常。"""

        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        for close in (
            self.context.metric_logger.close,
            self.context.data_module.close,
            self.context.strategy.close,
        ):
            try:
                close()
            except BaseException as error:
                errors.append(error)
        if errors:
            primary = errors[0]
            for error in errors[1:]:
                _add_exception_note(primary, "additional cleanup failure", error)
            raise primary

    def _call(self, event: str, *args: object) -> None:
        """按注册顺序派发完整 callback 事件。"""

        for callback in self.context.callbacks:
            handler = getattr(callback, event)
            handler(*args)

    def _call_on_exception(self, error: BaseException) -> None:
        """独立通知全部异常 callback,并把失败附加到根异常。"""

        for callback in self.context.callbacks:
            try:
                callback.on_exception(self.state, error)
            except BaseException as callback_error:
                _add_exception_note(error, "on_exception callback failed", callback_error)

    def _max_steps_reached(self) -> bool:
        """判断已消费微批次数是否达到引擎硬上限。"""

        max_steps = self.context.config.max_steps
        return max_steps is not None and self.state.global_step >= max_steps

    def _close_after_error(self, error: BaseException) -> None:
        """清理资源并把清理失败附加到原始异常。"""

        if self._closed:
            return
        self._closed = True
        for close in (
            self.context.metric_logger.close,
            self.context.data_module.close,
            self.context.strategy.close,
        ):
            try:
                close()
            except BaseException as cleanup_error:
                _add_exception_note(error, "training cleanup failed", cleanup_error)


__all__ = ["CheckpointReason", "TrainingEngine"]
