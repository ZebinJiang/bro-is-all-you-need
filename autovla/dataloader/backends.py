"""规范 ``autovla.data`` 后端注册表的兼容委托。"""

from autovla.data.registry import (
    DataBackendRegistration,
    DataBackendRegistry,
    build_data_backend_registry,
)

NO_BACKEND_WINNER = "NO_BACKEND_WINNER"
WEB_DATASET_BACKEND = "webdataset"
ROBODM_BACKEND = "robodm_container"


def resolve_backend_key(value: str) -> str:
    """通过规范数据注册表解析后端键或历史别名。"""
    return build_data_backend_registry().resolve_key(value)


def get_backend_spec(value: str) -> DataBackendRegistration:
    """返回规范后端注册项,不构造后端。"""
    return build_data_backend_registry().get(value)


def list_backend_keys() -> tuple[str, ...]:
    """返回规范后端键,不表达默认值或胜者。"""
    return build_data_backend_registry().names()


__all__ = [
    "NO_BACKEND_WINNER",
    "ROBODM_BACKEND",
    "WEB_DATASET_BACKEND",
    "DataBackendRegistration",
    "DataBackendRegistry",
    "build_data_backend_registry",
    "get_backend_spec",
    "list_backend_keys",
    "resolve_backend_key",
]
