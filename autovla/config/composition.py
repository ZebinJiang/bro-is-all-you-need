"""AutoVLA 命名 YAML 预设组合。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import cast

from omegaconf import DictConfig, OmegaConf

from autovla.config.errors import ConfigurationCompositionError
from autovla.config.overrides import apply_dotted_overrides


def _load_mapping(path: Path) -> dict[str, object]:
    """加载单个本地 YAML 并要求顶层是映射。"""
    if not path.is_file():
        raise ConfigurationCompositionError(f"config preset does not exist: {path}")
    loaded = OmegaConf.load(path)
    if not isinstance(loaded, DictConfig):
        raise ConfigurationCompositionError(f"config preset must be a mapping: {path}")
    plain = OmegaConf.to_container(loaded, resolve=True)
    if not isinstance(plain, dict):
        raise ConfigurationCompositionError(f"config preset must resolve to a mapping: {path}")
    return cast(dict[str, object], plain)


def _merge(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    """递归合并映射,右侧标量和序列覆盖左侧。"""
    output = deepcopy(dict(left))
    for key, value in right.items():
        current = output.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            output[key] = _merge(
                cast(Mapping[str, object], current),
                cast(Mapping[str, object], value),
            )
        else:
            output[key] = deepcopy(value)
    return output


def _preset_path(root: Path, group: str, name: str) -> Path:
    """解析受根目录约束的 ``group/name.yaml`` 路径。"""
    if not group.strip() or not name.strip():
        raise ConfigurationCompositionError("preset group and name must not be empty")
    candidate = (root / group / f"{name}.yaml").resolve()
    resolved_root = root.resolve()
    if candidate != resolved_root and resolved_root not in candidate.parents:
        raise ConfigurationCompositionError("preset path escapes composition root")
    return candidate


def compose_mapping(
    path: str | Path,
    *,
    preset_root: str | Path | None = None,
    overrides: Sequence[str] = (),
) -> dict[str, object]:
    """按命名预设、当前文件、dotted override 顺序组合配置。"""
    config_path = Path(path).resolve()
    if preset_root is not None:
        root = Path(preset_root).resolve()
    elif config_path.parent.name == "experiments":
        root = config_path.parent.parent
    else:
        root = config_path.parent
    document = _load_mapping(config_path)
    defaults_value = document.pop("defaults", ())
    if not isinstance(defaults_value, (list, tuple)):
        raise ConfigurationCompositionError("defaults must be a list of named presets")
    defaults = cast(Sequence[object], defaults_value)
    composed: dict[str, object] = {}
    for index, entry in enumerate(defaults):
        if not isinstance(entry, Mapping):
            raise ConfigurationCompositionError(
                f"defaults[{index}] must contain exactly one group-to-name mapping"
            )
        entry_mapping = cast(Mapping[object, object], entry)
        if len(entry_mapping) != 1:
            raise ConfigurationCompositionError(
                f"defaults[{index}] must contain exactly one group-to-name mapping"
            )
        group, name = next(iter(entry_mapping.items()))
        if not isinstance(group, str) or not isinstance(name, str):
            raise ConfigurationCompositionError(f"defaults[{index}] group and name must be strings")
        preset = _load_mapping(_preset_path(root, group, name))
        section_value = preset.get(group, preset)
        if not isinstance(section_value, Mapping):
            raise ConfigurationCompositionError(f"preset {group}/{name} must resolve to a mapping")
        composed = _merge(
            composed,
            {group: dict(cast(Mapping[str, object], section_value))},
        )
    composed = _merge(composed, document)
    return apply_dotted_overrides(composed, overrides)


__all__ = ["compose_mapping"]
