"""GenesisVLA 的窄 OmegaConf 兼容桥。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any, cast

from omegaconf import DictConfig, OmegaConf


def load_omegaconf(path: str | Path) -> DictConfig:
    """从 YAML 路径加载 OmegaConf 配置。

    Args:
        path: GenesisVLA YAML 配置路径。

    Returns:
        OmegaConf 字典配置对象。
    """
    loaded = OmegaConf.load(Path(path))
    if not isinstance(loaded, DictConfig):
        raise ValueError(f"config must be a mapping: {path}")
    return loaded


def merge_dotlist(config: DictConfig, overrides: Sequence[str]) -> DictConfig:
    """应用 OmegaConf dotlist 覆盖并返回新配置对象。

    Args:
        config: 原始 OmegaConf 字典配置。
        overrides: 形如 ``runner.backend=ddp`` 的覆盖列表。

    Returns:
        合并后的 OmegaConf 字典配置。
    """
    if not overrides:
        return OmegaConf.create(config)
    merged = OmegaConf.merge(config, OmegaConf.from_dotlist(list(overrides)))
    if not isinstance(merged, DictConfig):
        raise ValueError("merged config must be a mapping")
    return merged


def to_plain_container(config: DictConfig) -> dict[str, Any]:
    """解析 OmegaConf 配置并转换为普通字典。

    Args:
        config: OmegaConf 字典配置。

    Returns:
        解析后的普通 ``dict``。
    """
    plain = OmegaConf.to_container(config, resolve=True)
    if not isinstance(plain, dict):
        raise ValueError("resolved config must be a mapping")
    return cast(dict[str, Any], plain)
