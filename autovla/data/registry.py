"""AutoVLA 数据领域注册表和工厂。"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

from autovla.config.schema import DataConfig
from autovla.core.registry import ComponentRegistry, ImportStringFactory
from autovla.data.backends.base import (
    DataBackend,
    DataBackendCapabilities,
    DataBackendSpec,
)
from autovla.data.normalization.statistics import NormalizationStatistics
from autovla.data.types import DatasetManifest, DataStage


@dataclass(frozen=True, slots=True)
class DataBackendRegistration:
    """绑定后端能力真值和懒构造元数据。"""

    spec: DataBackendSpec
    factory: ImportStringFactory[DataBackend]


class DataBackendRegistry(ComponentRegistry[DataBackendRegistration]):
    """保存无默认、无胜者语义的数据后端注册项。"""


class DataModuleLike(Protocol):
    """描述 DataModule 工厂的精确返回边界。"""

    @abstractmethod
    def setup(self, stage: DataStage) -> None:
        """准备指定数据阶段。"""
        raise NotImplementedError

    @abstractmethod
    def train_dataloader(self) -> object:
        """返回训练 loader。"""
        raise NotImplementedError

    @abstractmethod
    def validation_dataloader(self) -> object | None:
        """返回可选验证 loader。"""
        raise NotImplementedError

    @abstractmethod
    def normalization_statistics(self) -> NormalizationStatistics | None:
        """返回可选类型化统计量。"""
        raise NotImplementedError

    @abstractmethod
    def dataset_manifest(self) -> DatasetManifest:
        """返回数据集 manifest。"""
        raise NotImplementedError

    @abstractmethod
    def state_dict(self) -> Mapping[str, object]:
        """导出下一条未读数据状态。"""
        raise NotImplementedError

    @abstractmethod
    def load_state_dict(self, state: Mapping[str, object]) -> None:
        """原子恢复下一条未读数据状态。"""
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        """关闭所有数据资源。"""
        raise NotImplementedError


class DataModuleRegistry(ComponentRegistry[ImportStringFactory[DataModuleLike]]):
    """保存 DataModule 懒工厂元数据。"""


class DataModuleFactory(Protocol):
    """定义 DataConfig 到 DataModule 实例的构造边界。"""

    @abstractmethod
    def __call__(self, config: DataConfig, **kwargs: object) -> DataModuleLike:
        """构造一个 DataModule。"""
        raise NotImplementedError


def _registration(spec: DataBackendSpec) -> DataBackendRegistration:
    """从后端规格构造可执行懒注册项。"""
    return DataBackendRegistration(
        spec=spec,
        factory=ImportStringFactory(
            spec.factory_path,
            optional_extra=spec.optional_extra,
            required_modules=spec.required_modules,
            metadata={"backend_key": spec.key},
        ),
    )


def build_data_backend_registry() -> DataBackendRegistry:
    """构造三个显式本地后端,不选择默认项或性能胜者。"""
    registry = DataBackendRegistry("autovla-data-backends")
    webdataset = DataBackendSpec(
        key="webdataset",
        aliases=("webdataset_tar", "webdataset_native", "zjh_webdataset_tar"),
        capabilities=DataBackendCapabilities(
            sequential_streaming=True,
            random_access=False,
            persistent_index=True,
            grouped_reads=False,
            deterministic_partition=True,
            prototype_only=False,
            native_compatible=True,
        ),
        factory_path="autovla.data.backends.webdataset:create_backend",
        optional_extra="data-webdataset",
        required_modules=("webdataset",),
    )
    robodm = DataBackendSpec(
        key="robodm_container",
        aliases=(
            "robodm_container_v1",
            "robodm_style",
            "robodm",
            "zjh_robodm_container_v1",
        ),
        capabilities=DataBackendCapabilities(
            sequential_streaming=False,
            random_access=True,
            persistent_index=True,
            grouped_reads=True,
            deterministic_partition=True,
            prototype_only=True,
            native_compatible=False,
        ),
        factory_path="autovla.data.backends.robodm:create_backend",
    )
    lerobot = DataBackendSpec(
        key="lerobot_local",
        aliases=("lerobot_v3_local", "zjh_lerobot_v3_local"),
        capabilities=DataBackendCapabilities(
            sequential_streaming=False,
            random_access=True,
            persistent_index=True,
            grouped_reads=True,
            deterministic_partition=True,
            prototype_only=False,
            native_compatible=False,
        ),
        factory_path="autovla.data.backends.lerobot:create_backend",
        optional_extra="data-lerobot",
        required_modules=("pyarrow",),
    )
    for spec in (webdataset, robodm, lerobot):
        registry.register(spec.key, _registration(spec), aliases=spec.aliases)
    return registry


def build_data_module_registry() -> DataModuleRegistry:
    """构造规范 DataModule 注册表。"""
    registry = DataModuleRegistry("autovla-data-modules")
    registry.register(
        "standard",
        ImportStringFactory("autovla.data.module:create_data_module"),
    )
    return registry


__all__ = [
    "DataBackendRegistration",
    "DataBackendRegistry",
    "DataModuleFactory",
    "DataModuleLike",
    "DataModuleRegistry",
    "build_data_backend_registry",
    "build_data_module_registry",
]
