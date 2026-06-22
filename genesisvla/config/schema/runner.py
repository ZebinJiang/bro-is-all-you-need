"""GenesisVLA 运行器配置结构。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from genesisvla.config.schema.base import BaseConfig


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
    """

    backend: RunnerBackend = RunnerBackend.LOCAL
    batch_size: int = 1
    max_steps: int = 1
    device: str = "cpu"
