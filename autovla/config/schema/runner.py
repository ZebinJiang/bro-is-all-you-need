"""AutoVLA 运行器配置结构。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import cast

from autovla.config.schema.base import (
    BaseConfig,
    require_int,
    require_non_empty_str,
    require_number,
    require_schema_version,
)


class RunnerBackend(str, Enum):
    """M1 支持声明但不执行的运行后端枚举。"""

    LOCAL = "local"
    ACCELERATE = "accelerate"
    DDP = "ddp"
    FSDP = "fsdp"
    DEEPSPEED = "deepspeed"

    @classmethod
    def from_value(cls, value: str | RunnerBackend) -> RunnerBackend:
        """将字符串或枚举值转换为 ``RunnerBackend``。

        Args:
            value: 后端字符串或已构造的 ``RunnerBackend``。

        Returns:
            规范化后的运行后端枚举值。

        Raises:
            ValueError: 当值不属于 M1 允许后端集合时抛出。
        """
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            allowed = ", ".join(cls.values())
            raise ValueError(
                f"invalid runner.backend {value!r}; allowed values: {allowed}"
            ) from exc

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """返回按声明顺序排列的允许后端字符串。"""
        return tuple(item.value for item in cls)


@dataclass(frozen=True, slots=True)
class RunnerConfig(BaseConfig):
    """描述运行器选择与最小调试参数,不执行任何运行时逻辑。

    Args:
        schema_version: 运行器配置段版本。M1 仅接受 ``"1.0"``。
        backend: 后端枚举,M1 只声明允许值,不导入对应运行库。
        batch_size: 批大小,必须为正整数。
        max_steps: 最大步数,必须为正整数。
        device: 设备字符串,不能为空;M1 不进行设备解析。
        learning_rate: 学习率声明值,必须为正数。
        grad_accumulation_steps: 梯度累积步数,必须为正整数。
        action_horizon: 动作 horizon,必须为正整数。
        action_dim: 动作维度,必须为正整数。
        timeout: 运行器声明式超时秒数,必须为正数。
    """

    backend: RunnerBackend = RunnerBackend.LOCAL
    batch_size: int = 1
    max_steps: int = 1
    device: str = "cpu"
    learning_rate: float = 1e-4
    grad_accumulation_steps: int = 1
    action_horizon: int = 1
    action_dim: int = 1
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """校验运行器配置构造器不变量。"""
        require_schema_version(self.schema_version, "runner.schema_version")
        backend = cast(object, self.backend)
        if not isinstance(backend, RunnerBackend):
            raise ValueError("runner.backend must be a RunnerBackend")
        require_non_empty_str(self.device, "runner.device")
        batch_size = require_int(self.batch_size, "runner.batch_size")
        max_steps = require_int(self.max_steps, "runner.max_steps")
        learning_rate = require_number(self.learning_rate, "runner.learning_rate")
        grad_accumulation_steps = require_int(
            self.grad_accumulation_steps, "runner.grad_accumulation_steps"
        )
        action_horizon = require_int(self.action_horizon, "runner.action_horizon")
        action_dim = require_int(self.action_dim, "runner.action_dim")
        timeout = require_number(self.timeout, "runner.timeout")
        if batch_size <= 0:
            raise ValueError("runner.batch_size must be positive")
        if max_steps <= 0:
            raise ValueError("runner.max_steps must be positive")
        if learning_rate <= 0:
            raise ValueError("runner.learning_rate must be positive")
        if grad_accumulation_steps <= 0:
            raise ValueError("runner.grad_accumulation_steps must be positive")
        if action_horizon <= 0:
            raise ValueError("runner.action_horizon must be positive")
        if action_dim <= 0:
            raise ValueError("runner.action_dim must be positive")
        if timeout <= 0:
            raise ValueError("runner.timeout must be positive")
