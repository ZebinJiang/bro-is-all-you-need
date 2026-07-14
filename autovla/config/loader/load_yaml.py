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
    """组合命名预设、物化 schema 默认值并严格应用覆盖。"""
    composed = compose_mapping(path, preset_root=preset_root)
    materialized = build_experiment_config(composed).to_resolved_dict()
    return build_experiment_config(
        apply_dotted_overrides(
            prepare_mapping_for_overrides(materialized, overrides),
            overrides,
        )
    )


__all__ = ["load_yaml"]
