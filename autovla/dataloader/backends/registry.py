"""轻量 DataBackend registry, 不导入任何重型运行时。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.dataloader.backends.contracts import DataBackendKey, DataBackendSpec
from autovla.dataloader.backends.errors import DataBackendRegistryError
from autovla.dataloader.backends.manifest import get_backend_specs


@dataclass(frozen=True, slots=True)
class DataBackendRegistry:
    """静态 DataBackend spec 注册表。"""

    entries: tuple[DataBackendSpec, ...]

    def __post_init__(self) -> None:
        """校验 backend key 唯一。"""
        keys = [entry.backend_key for entry in self.entries]
        duplicates = sorted(key for key in set(keys) if keys.count(key) > 1)
        if duplicates:
            raise DataBackendRegistryError(f"duplicate backend: {duplicates[0]}")

    def keys(self) -> tuple[DataBackendKey, ...]:
        """返回稳定排序的 backend key。"""
        return tuple(sorted(entry.backend_key for entry in self.entries))

    def get(self, backend_key: DataBackendKey) -> DataBackendSpec:
        """按 key 返回 backend spec, 未知 key 显式失败。"""
        for entry in self.entries:
            if entry.backend_key == backend_key:
                return entry
        raise DataBackendRegistryError(f"unknown backend: {backend_key}")

    def to_json_rows(self) -> tuple[dict[str, object], ...]:
        """返回 registry 表格/JSON 行。"""
        return tuple(self.get(key).to_json_dict() for key in self.keys())


def default_backend_registry() -> DataBackendRegistry:
    """返回默认 DataBackend registry。"""
    specs = get_backend_specs()
    return DataBackendRegistry(tuple(specs[key] for key in sorted(specs)))
