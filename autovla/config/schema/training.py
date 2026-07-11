"""AutoVLA 生产训练配置。"""

from dataclasses import dataclass, field

from autovla.config.schema.base import require_number, require_positive_int
from autovla.config.schema.checkpoint import CheckpointConfig
from autovla.config.schema.distributed import DistributedConfig, PrecisionConfig
from autovla.config.schema.logging import LoggingConfig
from autovla.config.schema.optimization import OptimizationConfig


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    """组合训练生命周期、优化、策略、精度、检查点和日志配置。"""

    epochs: int = 1
    max_steps: int | None = None
    gradient_accumulation_steps: int = 1
    gradient_clip_norm: float | None = None
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    distributed: DistributedConfig = field(default_factory=DistributedConfig)
    precision: PrecisionConfig = field(default_factory=PrecisionConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)

    def __post_init__(self) -> None:
        """校验训练边界和嵌套配置类型。"""
        require_positive_int(self.epochs, "training.epochs")
        if self.max_steps is not None:
            require_positive_int(self.max_steps, "training.max_steps")
        require_positive_int(
            self.gradient_accumulation_steps,
            "training.gradient_accumulation_steps",
        )
        if self.gradient_clip_norm is not None:
            value = require_number(self.gradient_clip_norm, "training.gradient_clip_norm")
            if value <= 0.0:
                raise ValueError("training.gradient_clip_norm must be positive")


__all__ = ["TrainingConfig"]
