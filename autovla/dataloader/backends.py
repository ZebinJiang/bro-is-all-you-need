"""历史双后端测试接口的轻量懒兼容位置。"""

from __future__ import annotations

from importlib import import_module
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, cast

NO_BACKEND_WINNER = "NO_BACKEND_WINNER"
WEB_DATASET_BACKEND = "webdataset_tar"
ROBODM_BACKEND = "robodm_container_v1"

if TYPE_CHECKING:
    from autovla.testing.data.backends import (
        DataBackendCapabilities,
        DataBackendSpec,
        TrainingBatchSource,
    )


class _CompatibilityBackendModule(Protocol):
    """描述历史测试后端模块的静态懒调用表面。"""

    def build_data_backend_registry(self) -> object: ...

    def resolve_backend_key(self, value: str) -> str: ...

    def get_backend_spec(self, value: str) -> DataBackendSpec: ...

    def list_backend_keys(self) -> tuple[str, ...]: ...

    def create_training_batch_source(
        self,
        value: str,
        *,
        root: Path,
        seed: int,
        action_horizon: int,
        action_dim: int,
        dataset_fingerprint: str,
        transform_fingerprint: str,
        statistics_fingerprint: str,
    ) -> TrainingBatchSource: ...


def _compatibility_module() -> _CompatibilityBackendModule:
    """仅在调用历史接口时导入测试后端实现。"""
    return cast(
        _CompatibilityBackendModule,
        import_module("autovla.testing.data.backends"),
    )


def build_data_backend_registry() -> object:
    """懒构造历史双后端测试注册表。"""
    return _compatibility_module().build_data_backend_registry()


def resolve_backend_key(value: str) -> str:
    """懒解析历史规范键或显式别名。"""
    return _compatibility_module().resolve_backend_key(value)


def get_backend_spec(value: str) -> DataBackendSpec:
    """懒返回历史测试后端规格。"""
    return _compatibility_module().get_backend_spec(value)


def list_backend_keys() -> tuple[str, ...]:
    """懒返回历史双后端键,不表达默认或胜者。"""
    return _compatibility_module().list_backend_keys()


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
    """懒委托历史 TrainingBatchSource 工厂。"""
    return _compatibility_module().create_training_batch_source(
        value,
        root=root,
        seed=seed,
        action_horizon=action_horizon,
        action_dim=action_dim,
        dataset_fingerprint=dataset_fingerprint,
        transform_fingerprint=transform_fingerprint,
        statistics_fingerprint=statistics_fingerprint,
    )


def __getattr__(name: str) -> object:
    """仅在请求历史协议或规格类型时解析测试命名空间。"""
    if name not in {"DataBackendCapabilities", "DataBackendSpec", "TrainingBatchSource"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(_compatibility_module(), name)
    globals()[name] = value
    return value


__all__ = [
    "NO_BACKEND_WINNER",
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
