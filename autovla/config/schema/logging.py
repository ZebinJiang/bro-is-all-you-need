"""AutoVLA 本地日志配置。"""

from dataclasses import dataclass

from autovla.config.schema.base import require_bool, require_non_empty_str, require_positive_int


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    """描述标准输出与 JSONL 指标记录。"""

    log_every_steps: int = 10
    stdout: bool = True
    jsonl_path: str | None = None

    def __post_init__(self) -> None:
        """校验日志频率和可选本地文件路径。"""
        require_positive_int(self.log_every_steps, "training.logging.log_every_steps")
        require_bool(self.stdout, "training.logging.stdout")
        if self.jsonl_path is not None:
            require_non_empty_str(self.jsonl_path, "training.logging.jsonl_path")


__all__ = ["LoggingConfig"]
