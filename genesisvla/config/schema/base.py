"""GenesisVLA 配置基础结构。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BaseConfig:
    """所有 M1 配置段共享的 schema 版本字段。

    Args:
        schema_version: 配置结构版本。M1 仅接受 ``"1.0"``。
    """

    schema_version: str = "1.0"
