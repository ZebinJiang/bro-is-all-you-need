"""AutoVLA 配置基础结构与校验函数。"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import TypeVar, cast

V = TypeVar("V")


def require_schema_version(version: object, field_name: str) -> None:
    """确认 schema 版本符合 M1 配置契约。"""
    if not isinstance(version, str):
        raise ValueError(f"{field_name} must be a string")
    if version != "1.0":
        raise ValueError(f"{field_name} must be '1.0'")


def require_non_empty_str(value: object, field_name: str) -> str:
    """确认字段是非空字符串。"""
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a string")
    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def require_int(value: object, field_name: str) -> int:
    """确认整数字段不接受 bool、float 或字符串等隐式转换。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def require_bool(value: object, field_name: str) -> bool:
    """确认布尔字段不接受其他隐式转换类型。"""
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def require_number(value: object, field_name: str) -> float:
    """确认数字字段不接受 bool、字符串或其他隐式转换类型。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{field_name} must be a number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def require_str_tuple(value: object, field_name: str) -> tuple[str, ...]:
    """确认字段是非空字符串元组或列表。"""
    if not isinstance(value, (list, tuple)):
        raise ValueError(f"{field_name} must be a list of strings")
    values = cast(list[object] | tuple[object, ...], value)
    result: list[str] = []
    for index, item in enumerate(values):
        if not isinstance(item, str):
            raise ValueError(f"{field_name}[{index}] must be a string")
        if not item.strip():
            raise ValueError(f"{field_name}[{index}] must not be empty")
        result.append(item)
    if not result:
        raise ValueError(f"{field_name} must not be empty")
    return tuple(result)


@dataclass(frozen=True, slots=True)
class BaseConfig:
    """所有 M1 配置段共享的 schema 版本字段。

    Args:
        schema_version: 配置结构版本。M1 仅接受 ``"1.0"``。
    """

    schema_version: str = "1.0"

    def __post_init__(self) -> None:
        """校验公共配置构造器共享的不变量。"""
        require_schema_version(self.schema_version, "schema_version")


def require_positive_int(value: object, field_name: str) -> int:
    """校验严格正整数。"""
    result = require_int(value, field_name)
    if result <= 0:
        raise ValueError(f"{field_name} must be positive")
    return result


def require_non_negative_int(value: object, field_name: str) -> int:
    """校验非负整数。"""
    result = require_int(value, field_name)
    if result < 0:
        raise ValueError(f"{field_name} must be non-negative")
    return result


def require_choice(value: object, field_name: str, choices: tuple[str, ...]) -> str:
    """校验字符串属于封闭选项集合。"""
    result = require_non_empty_str(value, field_name)
    if result not in choices:
        raise ValueError(f"{field_name} must be one of {', '.join(choices)}")
    return result


def freeze_mapping(value: Mapping[str, V], field_name: str) -> Mapping[str, V]:
    """复制字符串键映射并返回只读视图。"""
    output: dict[str, V] = {}
    for key, item in value.items():
        output[require_non_empty_str(key, f"{field_name} key")] = item
    return MappingProxyType(output)
