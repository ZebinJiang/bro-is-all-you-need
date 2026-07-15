"""本地可选遥测配置。"""

from dataclasses import dataclass, field

from autovla.config.schema.base import require_bool
from autovla.config.schema.logging import LoggingConfig


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """配置本地 logger 和 rank reduction, 不要求远程服务。"""

    logging: LoggingConfig = field(default_factory=LoggingConfig)
    reduce_across_ranks: bool = True
    remote_logging: bool = False

    def __post_init__(self) -> None:
        """禁止把远程日志变成生产依赖。"""
        require_bool(self.reduce_across_ranks, "telemetry.reduce_across_ranks")
        require_bool(self.remote_logging, "telemetry.remote_logging")
        if self.remote_logging:
            raise ValueError("telemetry.remote_logging is unsupported; local logging only")


__all__ = ["TelemetryConfig"]
