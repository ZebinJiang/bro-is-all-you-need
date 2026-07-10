"""AutoVLA 数据后端元数据、别名解析与工厂注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from autovla.core.registry import Registry
from autovla.core.types import TrainingBatch

WEB_DATASET_BACKEND = "webdataset_tar"
ROBODM_BACKEND = "robodm_container_v1"


class TrainingBatchSource(Protocol):
    """定义物理存储到规范训练批的有界本地数据源。"""

    def prepare(self) -> dict[str, object]:
        """生成共享逻辑 fixture 的物理存储并返回 fixture manifest。"""
        ...

    def read_batch(self, indices: tuple[int, ...]) -> TrainingBatch:
        """按逻辑索引读取一个规范训练批。"""
        ...

    def close(self) -> None:
        """确定性关闭持久读取资源。"""
        ...


class BackendSourceFactory(Protocol):
    """定义后端工厂的完整关键字参数契约。"""

    def __call__(
        self,
        *,
        root: Path,
        seed: int,
        action_horizon: int,
        action_dim: int,
        dataset_fingerprint: str,
        transform_fingerprint: str,
        statistics_fingerprint: str,
    ) -> TrainingBatchSource:
        """使用显式配置构造后端数据源。"""
        ...


@dataclass(frozen=True, slots=True)
class DataBackendCapabilities:
    """记录后端在打开数据前可检查的不可变能力。"""

    materialized_cameras: bool
    sequential_streaming: bool
    random_access: bool
    persistent_index: bool
    grouped_reads: bool
    deterministic_partition: bool
    prototype_only: bool
    dependency_status: str
    native_compatible: bool


@dataclass(frozen=True, slots=True)
class DataBackendSpec:
    """绑定规范后端键、显式别名、能力和懒工厂。"""

    backend_key: str
    aliases: tuple[str, ...]
    capabilities: DataBackendCapabilities
    source_factory: BackendSourceFactory
    artifact_schema: str


def _webdataset_factory(
    *,
    root: Path,
    seed: int,
    action_horizon: int,
    action_dim: int,
    dataset_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
) -> TrainingBatchSource:
    """仅在选择 WebDataset 路径时导入其本地适配器。"""
    from autovla.dataloader.stores.training_batch_readers import WebDatasetTrainingBatchSource

    return WebDatasetTrainingBatchSource(
        root=root,
        seed=seed,
        action_horizon=action_horizon,
        action_dim=action_dim,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
    )


def _robodm_factory(
    *,
    root: Path,
    seed: int,
    action_horizon: int,
    action_dim: int,
    dataset_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
) -> TrainingBatchSource:
    """仅在选择 RoboDM-style 路径时导入其本地适配器。"""
    from autovla.dataloader.stores.training_batch_readers import RoboDMTrainingBatchSource

    return RoboDMTrainingBatchSource(
        root=root,
        seed=seed,
        action_horizon=action_horizon,
        action_dim=action_dim,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
    )


def build_data_backend_registry() -> Registry[DataBackendSpec]:
    """构造两个无默认、无胜者语义的数据后端注册表。"""
    registry: Registry[DataBackendSpec] = Registry("autovla-data-backends")
    registry.register(
        WEB_DATASET_BACKEND,
        DataBackendSpec(
            backend_key=WEB_DATASET_BACKEND,
            aliases=("webdataset_native", "zjh_webdataset_tar"),
            capabilities=DataBackendCapabilities(
                materialized_cameras=True,
                sequential_streaming=True,
                random_access=False,
                persistent_index=True,
                grouped_reads=False,
                deterministic_partition=True,
                prototype_only=False,
                dependency_status="optional_existing_webdataset_1_0_2",
                native_compatible=True,
            ),
            source_factory=_webdataset_factory,
            artifact_schema="autovla.webdataset_tar.training_fixture.v1",
        ),
    )
    registry.register(
        ROBODM_BACKEND,
        DataBackendSpec(
            backend_key=ROBODM_BACKEND,
            aliases=("robodm_style", "robodm", "zjh_robodm_container_v1"),
            capabilities=DataBackendCapabilities(
                materialized_cameras=True,
                sequential_streaming=False,
                random_access=True,
                persistent_index=True,
                grouped_reads=True,
                deterministic_partition=True,
                prototype_only=True,
                dependency_status="autovla_owned_stdlib",
                native_compatible=False,
            ),
            source_factory=_robodm_factory,
            artifact_schema="autovla.robodm_style.training_fixture.v1",
        ),
    )
    aliases: set[str] = set(registry.names())
    for _, spec in registry.items():
        for alias in spec.aliases:
            if alias in aliases:
                raise ValueError(f"data backend alias collision: {alias}")
            aliases.add(alias)
    return registry


_BACKENDS = build_data_backend_registry()


def resolve_backend_key(value: str) -> str:
    """把规范键或显式别名解析为规范后端键。"""
    if value in _BACKENDS:
        return value
    for _, spec in _BACKENDS.items():
        if value in spec.aliases:
            return spec.backend_key
    allowed = sorted(
        name for _, spec in _BACKENDS.items() for name in (spec.backend_key, *spec.aliases)
    )
    raise ValueError(f"unknown data.backend {value!r}; allowed values: {', '.join(allowed)}")


def get_backend_spec(value: str) -> DataBackendSpec:
    """返回别名规范化后的后端规格。"""
    return _BACKENDS.get(resolve_backend_key(value))


def create_training_batch_source(
    value: str,
    *,
    root: Path,
    seed: int,
    action_horizon: int,
    action_dim: int,
    dataset_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
) -> TrainingBatchSource:
    """通过通用注册表创建新的后端数据源实例。"""
    spec = get_backend_spec(value)
    if not spec.capabilities.materialized_cameras:
        raise ValueError(f"backend {spec.backend_key} lacks materialized camera support")
    if not spec.capabilities.deterministic_partition:
        raise ValueError(f"backend {spec.backend_key} lacks deterministic partition support")
    return spec.source_factory(
        root=root,
        seed=seed,
        action_horizon=action_horizon,
        action_dim=action_dim,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
    )


def list_backend_keys() -> tuple[str, ...]:
    """返回两个规范后端键,不表达默认值或胜者。"""
    return _BACKENDS.names()


__all__ = [
    "ROBODM_BACKEND",
    "WEB_DATASET_BACKEND",
    "DataBackendCapabilities",
    "DataBackendSpec",
    "TrainingBatchSource",
    "build_data_backend_registry",
    "create_training_batch_source",
    "get_backend_spec",
    "list_backend_keys",
    "resolve_backend_key",
]
