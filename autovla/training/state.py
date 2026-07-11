"""AutoVLA 生产训练状态与显式停止语义。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class StepStatus(str, Enum):
    """标识微批次是完成、跳过还是因非有限值失败。"""

    COMPLETED = "completed"
    SKIPPED = "skipped"
    NONFINITE = "nonfinite"


class StopReason(str, Enum):
    """记录训练循环终止原因,避免用隐式布尔值表达。"""

    MAX_STEPS = "max_steps"
    EPOCHS_COMPLETED = "epochs_completed"
    CALLBACK_REQUEST = "callback_request"
    NONFINITE_LOSS = "nonfinite_loss"
    INTERRUPTED = "interrupted"
    EXCEPTION = "exception"


@dataclass(slots=True)
class TrainingState:
    """保存可恢复的生产训练进度与显式异常状态。

    ``global_step`` 统计已读取微批次,``optimizer_step`` 仅在成功更新后增加,
    ``microbatch_step`` 保存当前累积窗口位置。``resume_seed`` 随 epoch 推进,
    供 DataModule 或采样器在恢复后重建确定性顺序。
    """

    global_step: int = 0
    optimizer_step: int = 0
    microbatch_step: int = 0
    epoch: int = 0
    samples_seen: int = 0
    accumulated_loss: float = 0.0
    best_metric: float | None = None
    best_checkpoint: str | None = None
    stop_reason: StopReason | None = None
    last_step_status: StepStatus | None = None
    skipped_steps: int = 0
    nonfinite_steps: int = 0
    resume_seed: int = 0

    @property
    def should_stop(self) -> bool:
        """返回是否已进入显式停止状态。"""

        return self.stop_reason is not None

    def request_stop(self, reason: StopReason) -> None:
        """记录首次停止原因,保留最接近根因的状态。"""

        if self.stop_reason is None:
            self.stop_reason = reason

    def record_step(
        self,
        *,
        status: StepStatus,
        batch_size: int,
        loss: float | None,
        accumulation_steps: int,
        optimizer_updated: bool,
        gradient_window_reset: bool,
    ) -> None:
        """原子推进微批次、样本、损失和优化器计数。"""

        if batch_size <= 0 or accumulation_steps <= 0:
            raise ValueError("batch_size and accumulation_steps must be positive")
        self.global_step += 1
        self.samples_seen += batch_size
        self.last_step_status = status
        if loss is not None:
            self.accumulated_loss += loss
        if status is StepStatus.SKIPPED:
            self.skipped_steps += 1
        elif status is StepStatus.NONFINITE:
            self.nonfinite_steps += 1
        if optimizer_updated:
            self.optimizer_step += 1
        if gradient_window_reset:
            self.microbatch_step = 0
        else:
            self.microbatch_step = (self.microbatch_step + 1) % accumulation_steps

    def to_dict(self) -> dict[str, object]:
        """返回稳定、可写入 manifest 的 JSON 值。"""

        payload = asdict(self)
        payload["stop_reason"] = None if self.stop_reason is None else self.stop_reason.value
        payload["last_step_status"] = (
            None if self.last_step_status is None else self.last_step_status.value
        )
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "TrainingState":
        """从受信 manifest 字段恢复状态并执行类型化枚举转换。"""

        values: dict[str, Any] = dict(payload)
        stop_reason = values.get("stop_reason")
        step_status = values.get("last_step_status")
        values["stop_reason"] = None if stop_reason is None else StopReason(str(stop_reason))
        values["last_step_status"] = None if step_status is None else StepStatus(str(step_status))
        return cls(**values)


__all__ = ["StepStatus", "StopReason", "TrainingState"]
