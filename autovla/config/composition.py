"""AutoVLA 本地与包内命名 YAML 预设组合。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from pathlib import Path
from typing import cast

from omegaconf import DictConfig, OmegaConf

from autovla.config.errors import ConfigurationCompositionError
from autovla.config.overrides import apply_dotted_overrides
from autovla.config.resources import (
    RESOURCE_SCHEME,
    config_resource,
    config_resource_from_uri,
)


def _mapping_from_text(text: str, identity: str) -> dict[str, object]:
    """解析 YAML 文本并要求顶层为映射。"""
    loaded = OmegaConf.create(text)
    if not isinstance(loaded, DictConfig):
        raise ConfigurationCompositionError(f"config preset must be a mapping: {identity}")
    plain = OmegaConf.to_container(loaded, resolve=True)
    if not isinstance(plain, dict):
        raise ConfigurationCompositionError(f"config preset must resolve to a mapping: {identity}")
    return cast(dict[str, object], plain)


def _load_local_mapping(path: Path) -> dict[str, object]:
    """加载单个本地 YAML。"""
    if not path.is_file():
        raise ConfigurationCompositionError(f"config preset does not exist: {path}")
    return _mapping_from_text(path.read_text(encoding="utf-8"), str(path))


def _load_resource_mapping(group: str, name: str) -> dict[str, object]:
    """直接读取包资源,兼容 zip wheel 且不物化临时路径。"""
    resource = config_resource(group, name)
    return _mapping_from_text(resource.read_text(encoding="utf-8"), f"{group}/{name}")


def _merge(left: Mapping[str, object], right: Mapping[str, object]) -> dict[str, object]:
    """递归合并映射,右侧标量和序列覆盖左侧。"""
    output = deepcopy(dict(left))
    for key, value in right.items():
        current = output.get(key)
        if isinstance(current, dict) and isinstance(value, Mapping):
            output[key] = _merge(
                cast(Mapping[str, object], current), cast(Mapping[str, object], value)
            )
        else:
            output[key] = deepcopy(value)
    return output


def _preset_path(root: Path, group: str, name: str) -> Path:
    """解析受根目录约束的本地 ``group/name.yaml`` 路径。"""
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
    """组合包内或本地命名预设,再应用 dotted override。"""
    packaged = isinstance(path, str) and path.startswith(RESOURCE_SCHEME)
    if packaged:
        if preset_root is not None:
            raise ConfigurationCompositionError("packaged configs cannot use preset_root")
        resource = config_resource_from_uri(cast(str, path))
        document = _mapping_from_text(resource.read_text(encoding="utf-8"), cast(str, path))
        root = None
    else:
        config_path = Path(path).resolve()
        root = (
            Path(preset_root).resolve()
            if preset_root is not None
            else (
                config_path.parent.parent
                if config_path.parent.name == "experiments"
                else config_path.parent
            )
        )
        document = _load_local_mapping(config_path)
    defaults_value = document.pop("defaults", ())
    if not isinstance(defaults_value, (list, tuple)):
        raise ConfigurationCompositionError("defaults must be a list of named presets")
    defaults = cast(Sequence[object], defaults_value)
    composed: dict[str, object] = {}
    for index, entry in enumerate(defaults):
        if not isinstance(entry, Mapping) or len(entry) != 1:
            raise ConfigurationCompositionError(
                f"defaults[{index}] must contain exactly one group-to-name mapping"
            )
        group, name = next(iter(cast(Mapping[object, object], entry).items()))
        if not isinstance(group, str) or not isinstance(name, str):
            raise ConfigurationCompositionError(f"defaults[{index}] group and name must be strings")
        preset = (
            _load_resource_mapping(group, name)
            if packaged
            else _load_local_mapping(_preset_path(cast(Path, root), group, name))
        )
        section_value = preset.get(group, preset)
        if not isinstance(section_value, Mapping):
            raise ConfigurationCompositionError(f"preset {group}/{name} must resolve to a mapping")
        section = dict(cast(Mapping[str, object], section_value))
        target = (
            {"training": {"optimization": section}} if group == "optimization" else {group: section}
        )
        composed = _merge(composed, target)
    return apply_dotted_overrides(_merge(composed, document), overrides)


__all__ = ["compose_mapping"]
