"""按步数间隔记录训练指标的 callback。"""

from __future__ import annotations

from autovla.training.callbacks.base import TrainingCallback
from autovla.training.state import TrainingState
from autovla.training.step import TrainingStepOutput
from autovla.training.telemetry.logger import MetricLogger


class LoggingCallback(TrainingCallback):
    """把单步有限指标写入本地 stdout/JSONL sink。"""

    def __init__(self, logger: MetricLogger, every_steps: int = 1) -> None:
        """保存 logger 和正日志间隔。"""

        if every_steps <= 0:
            raise ValueError("logging interval must be positive")
        self._logger = logger
        self._interval = every_steps

    def on_step_end(self, state: TrainingState, output: TrainingStepOutput) -> None:
        """在间隔边界记录状态与步骤指标。"""

        if state.global_step % self._interval:
            return
        record: dict[str, object] = {
            "event": "train_step",
            "global_step": state.global_step,
            "optimizer_step": state.optimizer_step,
            "epoch": state.epoch,
            "samples_seen": state.samples_seen,
            "status": output.status.value,
            "optimizer_updated": output.optimizer_updated,
        }
        record.update(output.metrics)
        self._logger.log(record)


__all__ = ["LoggingCallback"]
