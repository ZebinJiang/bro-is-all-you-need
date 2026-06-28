"""AutoVLA 部署配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.config.schema.base import (
    BaseConfig,
    require_bool,
    require_number,
    require_schema_version,
)


@dataclass(frozen=True, slots=True)
class DeploymentConfig(BaseConfig):
    """描述 M1-lite 部署占位配置, 不连接任何真实端点。

    Args:
        schema_version: 部署配置段版本。M1 仅接受 ``"1.0"``。
        enabled: 是否启用部署流程。M1 默认关闭且不执行部署。
        timeout: 部署相关操作的声明式超时秒数, 必须为正数。
    """

    enabled: bool = False
    timeout: float = 30.0

    def __post_init__(self) -> None:
        """校验部署占位配置构造器不变量。"""
        require_schema_version(self.schema_version, "deployment.schema_version")
        require_bool(self.enabled, "deployment.enabled")
        timeout = require_number(self.timeout, "deployment.timeout")
        if timeout <= 0:
            raise ValueError("deployment.timeout must be positive")
