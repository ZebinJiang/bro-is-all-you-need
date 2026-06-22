"""GenesisVLA YAML 配置加载入口。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from genesisvla.config.loader.legacy_omegaconf import (
    load_omegaconf,
    merge_dotlist,
    to_plain_container,
)
from genesisvla.config.loader.validate import build_experiment_config
from genesisvla.config.schema import ExperimentConfig


def load_yaml(
    path: str | Path,
    *,
    overrides: Sequence[str] = (),
) -> ExperimentConfig:
    """加载 GenesisVLA YAML 并应用可选 CLI dotlist 覆盖。

    Args:
        path: GenesisVLA YAML 配置路径。
        overrides: 可选 dotlist 覆盖项。

    Returns:
        校验通过的实验配置对象。
    """
    config = merge_dotlist(load_omegaconf(path), overrides)
    return build_experiment_config(to_plain_container(config))
