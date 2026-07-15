"""Checkpoint cadence callback。"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from autovla.training.callbacks.base import TrainingCallback
from autovla.training.state import TrainingState
from autovla.training.step import TrainingStepOutput


class CheckpointCallback(TrainingCallback):
    """在成功优化器步达到固定间隔时请求保存。"""

    def __init__(self, every_optimizer_steps: int, save: Callable[[str], Path]) -> None:
        """保存正间隔和引擎提供的保存函数。"""

        if every_optimizer_steps <= 0:
            raise ValueError("checkpoint interval must be positive")
        self._interval = every_optimizer_steps
        self._save = save

    def on_optimizer_step(self, state: TrainingState, output: TrainingStepOutput) -> None:
        """在 cadence 边界调用保存函数。"""

        if output.optimizer_updated and state.optimizer_step % self._interval == 0:
            self._save("scheduled")


__all__ = ["CheckpointCallback"]
