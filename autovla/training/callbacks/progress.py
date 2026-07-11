"""训练停止条件 callback。"""

from __future__ import annotations

from autovla.training.callbacks.base import TrainingCallback
from autovla.training.state import StopReason, TrainingState
from autovla.training.step import TrainingStepOutput


class ProgressCallback(TrainingCallback):
    """在达到最大微批次步数时设置显式停止原因。"""

    def __init__(self, max_steps: int | None) -> None:
        """保存可选正步数上限。"""

        if max_steps is not None and max_steps <= 0:
            raise ValueError("max_steps must be positive")
        self._max_steps = max_steps

    def on_step_end(self, state: TrainingState, output: TrainingStepOutput) -> None:
        """达到上限时请求受控停止。"""

        if self._max_steps is not None and state.global_step >= self._max_steps:
            state.request_stop(StopReason.MAX_STEPS)


__all__ = ["ProgressCallback"]
