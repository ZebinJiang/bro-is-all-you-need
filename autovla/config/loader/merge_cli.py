"""AutoVLA 已构造配置的 CLI 覆盖工具。"""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import asdict
from typing import cast

from autovla.config.loader.export import to_resolved_dict
from autovla.config.loader.validate import build_experiment_config
from autovla.config.overrides import apply_dotted_overrides
from autovla.config.schema import (
    AccelerationConfig,
    ExperimentConfig,
    RunnerConfig,
)

_LEGACY_CANONICAL_PATHS = (
    ("runner.backend", "training.distributed.strategy_key"),
    ("runner.batch_size", "data.loader.batch_size"),
    ("runner.max_steps", "training.max_steps"),
    ("runner.learning_rate", "training.optimization.learning_rate"),
    ("runner.grad_accumulation_steps", "training.gradient_accumulation_steps"),
    ("acceleration", "training.precision.mode"),
)


def _overlaps(left: str, right: str) -> bool:
    """判断两个 dotted path 是否相同或互为父路径。"""
    return left == right or left.startswith(f"{right}.") or right.startswith(f"{left}.")


def _delete_path(data: dict[str, object], dotted_path: str) -> None:
    """删除存在的 dotted path,并保留其他兼容字段。"""
    parts = dotted_path.split(".")
    current = data
    for part in parts[:-1]:
        value = current.get(part)
        if not isinstance(value, dict):
            return
        current = cast(dict[str, object], value)
    current.pop(parts[-1], None)


def _legacy_defaults(root: str) -> dict[str, object]:
    """返回旧兼容段的类型化默认字段。"""
    if root == "runner":
        runner = asdict(RunnerConfig())
        runner["backend"] = RunnerConfig().backend.value
        return cast(dict[str, object], runner)
    return cast(dict[str, object], asdict(AccelerationConfig()))


def _seed_legacy_override(data: dict[str, object], path: str) -> None:
    """仅为显式旧覆盖创建其目标字段,未知字段仍由 override 层拒绝。"""
    root, separator, leaf = path.partition(".")
    if root not in {"runner", "acceleration"}:
        return
    if not separator:
        data.setdefault(root, {})
        return
    defaults = _legacy_defaults(root)
    if leaf not in defaults:
        return
    section = data.get(root)
    if section is None:
        section_mapping: dict[str, object] = {}
        data[root] = section_mapping
    elif isinstance(section, dict):
        section_mapping = cast(dict[str, object], section)
    else:
        return
    section_mapping.setdefault(leaf, defaults[leaf])


def prepare_mapping_for_overrides(
    base: dict[str, object], overrides: Sequence[str]
) -> dict[str, object]:
    """移除被覆盖字段的派生镜像,避免把单一覆盖误判为双输入冲突。"""
    output = deepcopy(base)
    for expression in overrides:
        path, separator, _ = expression.partition("=")
        if not separator:
            continue
        _seed_legacy_override(output, path)
        for legacy_path, canonical_path in _LEGACY_CANONICAL_PATHS:
            if _overlaps(path, legacy_path):
                _delete_path(output, canonical_path)
            elif _overlaps(path, canonical_path):
                _delete_path(output, legacy_path)
    return output


def merge_cli(config: ExperimentConfig, overrides: Sequence[str]) -> ExperimentConfig:
    """严格应用 dotted override 并返回全新不可变配置。"""
    return build_experiment_config(
        apply_dotted_overrides(
            prepare_mapping_for_overrides(to_resolved_dict(config), overrides),
            overrides,
        )
    )


__all__ = ["merge_cli"]
