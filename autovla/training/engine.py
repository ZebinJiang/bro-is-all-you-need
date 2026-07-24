"""AutoVLA 可读、显式且可恢复的生产训练引擎。"""

from __future__ import annotations

import time
from collections.abc import Iterator
from enum import Enum
from pathlib import Path
from typing import Protocol, TypeGuard, runtime_checkable

import torch

from autovla.config.schema.data import validate_collective_loader_policy
from autovla.core.types.training import TrainingBatch
from autovla.data.contracts import DataAccessMode, DistributedBatchPlan
from autovla.data.sampling import PartitionContext
from autovla.data.types import DataModuleState, DataStage
from autovla.training.context import TrainingContext
from autovla.training.session import (
    CheckpointLoadRequest,
    CheckpointSaveRequest,
    PreparedTrainingSession,
    TrainingTopology,
)
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

    @property
    def session(self) -> PreparedTrainingSession:
        """返回 setup 后唯一 prepared training session。"""

        session = self.context.session
        if session is None:
            raise RuntimeError("training session is not prepared")
        return session

    @staticmethod
    def _partition_from_topology(topology: TrainingTopology) -> PartitionContext:
        """把 Training 拓扑逐字段投影为 Data 自有分区类型。"""

        return PartitionContext(
            rank=topology.rank,
            local_rank=topology.local_rank,
            world_size=topology.world_size,
            node_rank=topology.node_rank,
            local_world_size=topology.local_world_size,
            launcher=topology.launcher,
            strategy=topology.strategy,
        )

    def _validate_distributed_loader_plan(
        self,
        topology: TrainingTopology,
        loader: _TrainingLoader,
    ) -> int:
        """在建组或恢复后证明所有 rank 将提交相同批次数。"""

        committed_batches = len(loader)
        if topology.world_size == 1:
            return committed_batches
        module_state = DataModuleState.from_dict(self.context.data_module.state_dict())
        loader_state = module_state.train_loader
        if loader_state is None:
            raise RuntimeError("distributed training requires a train loader state")
        if (
            loader_state.global_rank != topology.rank
            or loader_state.world_size != topology.world_size
        ):
            raise RuntimeError("distributed loader topology does not match training topology")
        validate_collective_loader_policy(
            loader_state.access_mode,
            loader_state.partition_policy,
        )
        manifest = self.context.data_module.dataset_manifest()
        sample_counts = tuple(
            count
            for count, split in zip(manifest.sample_counts, manifest.splits, strict=True)
            if split == "train"
        )
        if not sample_counts or any(count is None for count in sample_counts):
            raise ValueError("distributed loader requires explicit finite sample counts")
        nominal_samples = sum(count for count in sample_counts if count is not None)
        if loader_state.access_mode == DataAccessMode.MAP.value:
            plan = DistributedBatchPlan.for_map_sample_count(
                sample_count=nominal_samples,
                world_size=topology.world_size,
                batch_size=loader_state.batch_size,
                drop_last=loader_state.drop_last,
                policy=loader_state.partition_policy,
                committed_sample_cursor=loader_state.committed_batch_cursor,
            )
        else:
            plan = DistributedBatchPlan.for_streaming(
                world_size=topology.world_size,
                nominal_epoch_size=nominal_samples,
                batch_size=loader_state.batch_size,
                drop_last=loader_state.drop_last,
                policy=loader_state.partition_policy,
                committed_sample_cursor=loader_state.committed_batch_cursor,
            )
        if plan.rank_batch_counts[topology.rank] != committed_batches:
            raise RuntimeError("rank-local loader length differs from its committed batch plan")
        if plan.committed_batches <= 0:
            raise ValueError("distributed loader must commit at least one batch per rank")
        return plan.committed_batches

    def setup(self) -> None:
        """按拓扑、Data 和唯一 session 顺序建立运行时。"""

        if self._closed:
            raise RuntimeError("training engine is closed")
        if self._setup:
            return
        try:
            topology = self.context.strategy.topology
            self.context.data_module.bind_partition(self._partition_from_topology(topology))
            self.context.data_module.setup(DataStage.FIT)
            loader = _require_training_loader(self.context.data_module.train_dataloader())
            batches_per_epoch = self._validate_distributed_loader_plan(topology, loader)
            if self.context.optimizer_factory is None or self.context.scheduler_factory is None:
                raise ValueError("training context requires optimizer and scheduler factories")
            self.context.session = self.context.strategy.prepare(
                model=self.context.model,
                config=self.context.config,
                optimizer_factory=self.context.optimizer_factory,
                scheduler_factory=self.context.scheduler_factory,
                batches_per_epoch=batches_per_epoch,
            )
            self.context.model = self.session.model
            if self.context.resume_from is not None:
                self.load_checkpoint(self.context.resume_from)
                resumed_loader = _require_training_loader(
                    self.context.data_module.train_dataloader()
                )
                self._validate_distributed_loader_plan(topology, resumed_loader)
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

        # 1. 处理器拥有 CPU batch 到本 rank CUDA 张量的唯一传输。
        with timers.measure("processor"):
            model_batch = self.context.processor.prepare_batch(
                batch,
                device=self.session.device,
                dtype=self.session.precision.model_dtype,
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
        # 2. Session 独占前向、反向、累积、裁剪、step、scheduler 和 zero-grad。
        with timers.measure("forward"):
            model_output = self.session.forward(model_batch, force_boundary=boundary)
            loss = model_output.loss
        if loss.numel() != 1:
            raise ValueError("training loss must contain exactly one scalar")
        finite = self.session.all_finite(bool(torch.isfinite(loss.detach()).item()))
        if not finite:
            self.session.zero_grad()
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

        loss_value = self.session.reduce_mean(float(loss.detach().float().item()))
        with timers.measure("backward"):
            self.session.backward(loss)
        with timers.measure("optimizer"):
            step_result = self.session.step(force_boundary=boundary)
        optimizer_updated = step_result.update_committed
        gradient_norm = step_result.global_grad_norm
        status = StepStatus.SKIPPED if step_result.overflow_detected else StepStatus.COMPLETED
        gradient_window_reset = step_result.skipped_reason != "gradient_accumulation"

        self.state.record_step(
            status=status,
            batch_size=batch.batch_size,
            loss=loss_value,
            accumulation_steps=accumulation,
            optimizer_updated=optimizer_updated,
            gradient_window_reset=gradient_window_reset,
        )
        if optimizer_updated and self.state.optimizer_step != step_result.optimizer_step:
            raise RuntimeError("session and TrainingState optimizer-step counters diverged")
        if self._max_steps_reached():
            self.state.request_stop(StopReason.MAX_STEPS)
        metrics = self._metrics(
            loss=loss_value,
            gradient_norm=gradient_norm,
            batch_size=batch.batch_size,
            timers=timers,
            learning_rate=(step_result.learning_rates[0] if step_result.learning_rates else 0.0),
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

        # 3. 状态和指标先完成,再通知 callbacks,最后执行 checkpoint cadence。
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
        learning_rate: float,
    ) -> TrainingMetrics:
        """从计时器、优化器和可选 CUDA 状态生成完整遥测。"""

        elapsed = sum(
            timers.value(name)
            for name in ("data_wait", "processor", "forward", "backward", "optimizer")
        )
        memory_allocated: int | None = None
        memory_reserved: int | None = None
        if self.session.device.type == "cuda":
            memory_allocated = torch.cuda.memory_allocated(self.session.device)
            memory_reserved = torch.cuda.memory_reserved(self.session.device)
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

        result = self.session.save_checkpoint(
            CheckpointSaveRequest(
                manager=self.context.checkpoint_manager,
                data_module=self.context.data_module,
                callbacks=self.context.callbacks,
                metric_logger=self.context.metric_logger,
                state=self.state,
                reason=reason.value,
            )
        )
        path = result.path
        self._call("on_checkpoint_saved", self.state, path, reason.value)
        return path

    def load_checkpoint(self, path: Path) -> TrainingState:
        """在 setup 阶段恢复完整生产训练状态。"""

        result = self.session.load_checkpoint(
            CheckpointLoadRequest(
                manager=self.context.checkpoint_manager,
                path=path,
                data_module=self.context.data_module,
                family_adapter=self.context.family_checkpoint_adapter,
                callbacks=self.context.callbacks,
                metric_logger=self.context.metric_logger,
            )
        )
        restored = result.restored_state
        if restored is None:
            raise RuntimeError("checkpoint load did not return TrainingState")
        self.context.state = restored
        return restored

    def close(self) -> None:
        """幂等关闭 logger、DataModule 和策略,并保留首个清理异常。"""

        if self._closed:
            return
        self._closed = True
        errors: list[BaseException] = []
        closes = [self.context.metric_logger.close, self.context.data_module.close]
        if self.context.session is not None:
            closes.append(self.context.session.close)
        for close in closes:
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
        closes = [self.context.metric_logger.close, self.context.data_module.close]
        if self.context.session is not None:
            closes.append(self.context.session.close)
        for close in closes:
            try:
                close()
            except BaseException as cleanup_error:
                _add_exception_note(error, "training cleanup failed", cleanup_error)


__all__ = ["CheckpointReason", "TrainingEngine"]
