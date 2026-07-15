"""模型族定义的历史导入兼容层。"""

from __future__ import annotations

from dataclasses import dataclass
from warnings import warn

from autovla.models.families.specification import (
    LicenseSpec,
    ModelFamilyDefinition,
    ModelFamilySpec,
    OpenSourceReuseSpec,
    RuntimeSupportState,
)


@dataclass(frozen=True, slots=True)
class ModelFamilyRegistry:
    """旧元数据注册表;新代码应使用 ``autovla.models.registry``。"""

    entries: tuple[ModelFamilyDefinition, ...]

    def __post_init__(self) -> None:
        """校验规范键唯一。"""

        keys = tuple(entry.family_key for entry in self.entries)
        if len(keys) != len(set(keys)):
            raise ValueError("model family keys must be unique")

    def get(self, family_key: str) -> ModelFamilyDefinition:
        """按规范键返回同一不可变定义对象。"""

        warn(
            "autovla.models.family.ModelFamilyRegistry is deprecated; use models.registry",
            DeprecationWarning,
            stacklevel=2,
        )
        for entry in self.entries:
            if entry.family_key == family_key:
                return entry
        raise KeyError(f"unknown model family: {family_key}")

    def keys(self) -> tuple[str, ...]:
        """返回旧注册表的键。"""

        return tuple(entry.family_key for entry in self.entries)


__all__ = [
    "LicenseSpec",
    "ModelFamilyDefinition",
    "ModelFamilyRegistry",
    "ModelFamilySpec",
    "OpenSourceReuseSpec",
    "RuntimeSupportState",
]
