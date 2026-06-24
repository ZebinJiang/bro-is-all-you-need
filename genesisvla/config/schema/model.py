"""GenesisVLA 模型配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from genesisvla.config.schema.base import BaseConfig, require_non_empty_str, require_schema_version


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

    def __post_init__(self) -> None:
        """校验模型配置构造器不变量。"""
        require_schema_version(self.schema_version, "model.schema_version")
        require_non_empty_str(self.name, "model.name")
        require_non_empty_str(self.registry_key, "model.registry_key")
