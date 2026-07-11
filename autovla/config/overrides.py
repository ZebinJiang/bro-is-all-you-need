"""AutoVLA dotted override 解析。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from typing import Any, cast

from omegaconf import OmegaConf

from autovla.config.errors import ConfigurationOverrideError


def _parse_value(text: str) -> object:
    """使用 OmegaConf 标量语义解析单个覆盖值。"""
    parsed = OmegaConf.to_container(OmegaConf.from_dotlist([f"value={text}"]), resolve=True)
    if not isinstance(parsed, dict) or "value" not in parsed:
        raise ConfigurationOverrideError(f"cannot parse override value: {text!r}")
    return cast(dict[str, object], parsed)["value"]


def apply_dotted_overrides(
    config: Mapping[str, object], overrides: Sequence[str]
) -> dict[str, object]:
    """在普通配置映射上应用严格 dotted override。

    覆盖路径必须已经存在,避免命令行拼写错误创建未声明分支。最终类型仍由
    严格 schema 构造器校验。
    """
    output = deepcopy(dict(config))
    for expression in overrides:
        key, separator, raw_value = expression.partition("=")
        if not separator or not key.strip():
            raise ConfigurationOverrideError(
                f"override must use dotted.path=value syntax: {expression!r}"
            )
        parts = key.split(".")
        if any(not part for part in parts):
            raise ConfigurationOverrideError(f"invalid override path: {key!r}")
        cursor: dict[str, Any] = output
        for part in parts[:-1]:
            value = cursor.get(part)
            if not isinstance(value, dict):
                raise ConfigurationOverrideError(f"unknown override path: {key!r}")
            cursor = cast(dict[str, Any], value)
        leaf = parts[-1]
        if leaf not in cursor:
            raise ConfigurationOverrideError(f"unknown override path: {key!r}")
        cursor[leaf] = _parse_value(raw_value)
    return output


__all__ = ["apply_dotted_overrides"]
