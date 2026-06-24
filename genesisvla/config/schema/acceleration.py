"""GenesisVLA 加速配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from genesisvla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_non_empty_str,
    require_schema_version,
)


@dataclass(frozen=True, slots=True)
class AccelerationConfig(BaseConfig):
    """描述 M1-lite 加速占位配置, 不导入加速后端。

    Args:
        schema_version: 加速配置段版本。M1 仅接受 ``"1.0"``。
        enabled: 是否启用加速路径。M1 默认关闭且不执行后端初始化。
        mixed_precision: 声明式混合精度模式名称。
    """

    enabled: bool = False
    mixed_precision: str = "none"

    def __post_init__(self) -> None:
        """校验加速占位配置构造器不变量。"""
        require_schema_version(self.schema_version, "acceleration.schema_version")
        require_bool(self.enabled, "acceleration.enabled")
        require_non_empty_str(self.mixed_precision, "acceleration.mixed_precision")
