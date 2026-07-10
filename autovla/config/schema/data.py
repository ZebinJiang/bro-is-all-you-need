"""AutoVLA 数据配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.config.schema.base import (
    BaseConfig,
    require_non_empty_str,
    require_schema_version,
    require_str_tuple,
)


@dataclass(frozen=True, slots=True)
class DataConfig(BaseConfig):
    """描述数据源身份与样本必需模态。

    Args:
        schema_version: 数据配置段版本。M1 仅接受 ``"1.0"``。
        name: 数据配置名称,不能为空。
        root: 数据根目录字符串,不能为空;M1 不要求该目录真实存在。
        required_modalities: 样本必须包含的图像模态名称。
        backend: 显式数据后端键;``None`` 表示未选择,不是默认后端。
    """

    name: str = "local-debug-data"
    root: str = "datasets/working/local_debug"
    required_modalities: tuple[str, ...] = ("front",)
    backend: str | None = None

    def __post_init__(self) -> None:
        """校验数据配置构造器不变量。"""
        require_schema_version(self.schema_version, "data.schema_version")
        require_non_empty_str(self.name, "data.name")
        require_non_empty_str(self.root, "data.root")
        require_str_tuple(self.required_modalities, "data.required_modalities")
        if self.backend is not None:
            require_non_empty_str(self.backend, "data.backend")
