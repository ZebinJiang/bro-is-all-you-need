"""GenesisVLA 数据配置结构。"""

from __future__ import annotations

from dataclasses import dataclass

from genesisvla.config.schema.base import BaseConfig


@dataclass(frozen=True, slots=True)
class DataConfig(BaseConfig):
    """描述数据源身份与样本必需模态。

    Args:
        schema_version: 数据配置段版本。M1 仅接受 ``"1.0"``。
        name: 数据配置名称,不能为空。
        root: 数据根目录字符串,不能为空;M1 不要求该目录真实存在。
        required_modalities: 样本必须包含的图像模态名称。
    """

    name: str = "local-debug-data"
    root: str = "datasets/working/local_debug"
    required_modalities: tuple[str, ...] = ("front",)
