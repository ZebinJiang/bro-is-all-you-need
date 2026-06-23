"""GenesisVLA 部署配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from genesisvla.config.schema.base import BaseConfig


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
