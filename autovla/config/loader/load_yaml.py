"""AutoVLA 命名 YAML 配置加载入口。"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

from autovla.config.composition import compose_mapping
from autovla.config.loader.merge_cli import prepare_mapping_for_overrides
from autovla.config.loader.validate import build_experiment_config
from autovla.config.overrides import apply_dotted_overrides
from autovla.config.schema import ExperimentConfig


def load_yaml(
    path: str | Path,
    *,
    overrides: Sequence[str] = (),
    preset_root: str | Path | None = None,
) -> ExperimentConfig:
    """组合本地命名预设、应用覆盖并构造严格实验配置。"""
    composed = compose_mapping(path, preset_root=preset_root)
    return build_experiment_config(
        apply_dotted_overrides(
            prepare_mapping_for_overrides(composed, overrides),
            overrides,
        )
    )


__all__ = ["load_yaml"]
