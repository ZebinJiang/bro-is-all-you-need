"""GenesisVLA 模型配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from genesisvla.config.schema.base import BaseConfig


@dataclass(frozen=True, slots=True)
class ModelConfig(BaseConfig):
    """描述模型身份与注册键,不负责实例化模型。

    Args:
        schema_version: 模型配置段版本。M1 仅接受 ``"1.0"``。
        name: 人类可读模型名称,不能为空。
        registry_key: 后续注册表查找使用的模型键,不能为空。
    """

    name: str = "debug-model"
    registry_key: str = "debug-model"
