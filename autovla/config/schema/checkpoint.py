"""AutoVLA 检查点配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_bool, require_non_empty_str, require_positive_int


@dataclass(frozen=True, slots=True)
class CheckpointConfig:
    """描述本地原子检查点保存和恢复策略。"""

    directory: str = "runs/checkpoints"
    save_every_steps: int | None = None
    keep_last: int = 3
    resume_from: str | None = None
    save_optimizer: bool = True
    save_final: bool = True

    def __post_init__(self) -> None:
        """校验本地路径和保存频率。"""
        require_non_empty_str(self.directory, "training.checkpoint.directory")
        if self.save_every_steps is not None:
            require_positive_int(self.save_every_steps, "checkpoint.save_every_steps")
        require_positive_int(self.keep_last, "checkpoint.keep_last")
        if self.resume_from is not None:
            require_non_empty_str(self.resume_from, "checkpoint.resume_from")
        require_bool(self.save_optimizer, "checkpoint.save_optimizer")
        require_bool(self.save_final, "checkpoint.save_final")


__all__ = ["CheckpointConfig"]
