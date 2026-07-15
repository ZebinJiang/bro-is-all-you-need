"""生产训练 callback 事件契约。"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from autovla.training.state import TrainingState
from autovla.training.step import TrainingStepOutput


class TrainingCallback:
    """接收完整 fit、epoch、step、optimizer、checkpoint 和异常事件。"""

    def on_fit_start(self, state: TrainingState) -> None:
        """在 fit 循环开始前调用。"""

        return None

    def on_fit_end(self, state: TrainingState) -> None:
        """在 fit 正常或受控停止后调用。"""

        return None

    def on_epoch_start(self, state: TrainingState) -> None:
        """在 epoch 迭代前调用。"""

        return None

    def on_epoch_end(self, state: TrainingState) -> None:
        """在 epoch 完成后调用。"""

        return None

    def on_step_start(self, state: TrainingState) -> None:
        """在处理一个微批次前调用。"""

        return None

    def on_step_end(self, state: TrainingState, output: TrainingStepOutput) -> None:
        """在状态和遥测完成更新后调用。"""

        return None

    def on_optimizer_step(self, state: TrainingState, output: TrainingStepOutput) -> None:
        """在真实优化器更新后调用。"""

        return None

    def on_checkpoint_saved(self, state: TrainingState, path: Path, reason: str) -> None:
        """在原子 checkpoint 发布并同步后调用。"""

        return None

    def on_exception(self, state: TrainingState, error: BaseException) -> None:
        """在异常或中断即将离开引擎时调用。"""

        return None

    def state_dict(self) -> Mapping[str, object]:
        """返回 callback 可恢复状态;默认 callback 无可变状态。"""

        return {}

    def validate_state_dict(self, state: Mapping[str, object]) -> None:
        """不修改 callback 地验证状态。"""

        if state:
            raise ValueError(f"{type(self).__name__} checkpoint state must be empty")

    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """验证并恢复 callback 状态。"""

        self.validate_state_dict(state)


__all__ = ["TrainingCallback"]
