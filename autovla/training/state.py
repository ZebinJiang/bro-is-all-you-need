"""AutoVLA 生产训练状态与显式停止语义。"""

from __future__ import annotations

import math
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

    def __post_init__(self) -> None:
        """校验持久化计数、损失和边界字段。"""

        counters = (
            self.global_step,
            self.optimizer_step,
            self.microbatch_step,
            self.epoch,
            self.samples_seen,
            self.skipped_steps,
            self.nonfinite_steps,
            self.resume_seed,
        )
        if any(type(value) is not int or value < 0 for value in counters):
            raise ValueError("training state counters must be non-negative integers")
        if self.optimizer_step > self.global_step:
            raise ValueError("optimizer_step cannot exceed global_step")
        for value in (self.accumulated_loss, self.best_metric):
            if value is not None and not isinstance(value, (int, float)):
                raise TypeError("training state metrics must be numeric or null")
            if value is not None and not math.isfinite(float(value)):
                raise ValueError("training state metrics must be finite")

    def validate_resume_boundary(self) -> None:
        """仅允许已提交优化器步和完整 batch 边界恢复。"""

        if self.microbatch_step != 0:
            raise ValueError(
                "checkpoint resume requires a committed optimizer-step/batch boundary; "
                "partial gradients and mid-microstep resume are unsupported"
            )

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

        expected = {
            "global_step",
            "optimizer_step",
            "microbatch_step",
            "epoch",
            "samples_seen",
            "accumulated_loss",
            "best_metric",
            "best_checkpoint",
            "stop_reason",
            "last_step_status",
            "skipped_steps",
            "nonfinite_steps",
            "resume_seed",
        }
        if set(payload) != expected:
            raise ValueError("training state fields are incomplete or unknown")
        values: dict[str, Any] = dict(payload)
        stop_reason = values.get("stop_reason")
        step_status = values.get("last_step_status")
        values["stop_reason"] = None if stop_reason is None else StopReason(str(stop_reason))
        values["last_step_status"] = None if step_status is None else StepStatus(str(step_status))
        return cls(**values)


__all__ = ["StepStatus", "StopReason", "TrainingState"]
