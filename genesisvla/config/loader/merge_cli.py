"""GenesisVLA 已构造配置的 CLI 覆盖工具。"""

from __future__ import annotations

from collections.abc import Sequence

from omegaconf import OmegaConf

from genesisvla.config.loader.export import to_resolved_dict
from genesisvla.config.loader.legacy_omegaconf import merge_dotlist, to_plain_container
from genesisvla.config.loader.validate import build_experiment_config
from genesisvla.config.schema import ExperimentConfig


def merge_cli(config: ExperimentConfig, overrides: Sequence[str]) -> ExperimentConfig:
    """对已构造配置应用 dotlist 覆盖并返回新对象。

    Args:
        config: 原始实验配置对象。
        overrides: 可选 dotlist 覆盖项。

    Returns:
        覆盖后重新构造并校验的实验配置。
    """
    base = OmegaConf.create(to_resolved_dict(config))
    merged = merge_dotlist(base, overrides)
    return build_experiment_config(to_plain_container(merged))
