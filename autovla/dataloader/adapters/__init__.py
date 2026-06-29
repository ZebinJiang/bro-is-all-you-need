"""AutoVLA 数据集元数据适配器导出。"""

from autovla.core.registry import Registry
from autovla.dataloader.adapters.zjh import (
    DEFAULT_ZJH_ADAPTER,
    ZJH_ADAPTER_NAME,
    ZJH_ADAPTER_VERSION,
    ZJH_SOURCE_FORMAT,
    ZjhAdapter,
    ZjhMetadataPreview,
    build_zjh_artifact_from_root,
    build_zjh_artifact_preview,
    read_zjh_metadata,
    validate_zjh_statistics_request,
    write_zjh_artifact_preview,
)

_DATASET_ADAPTER_REGISTRY = Registry[ZjhAdapter]("autovla-dataset-adapters")
_DATASET_ADAPTER_REGISTRY.register(DEFAULT_ZJH_ADAPTER.adapter_name, DEFAULT_ZJH_ADAPTER)


def get_dataset_adapter(adapter_name: str) -> ZjhAdapter:
    """按名称返回 metadata-only 数据集适配器。"""
    return _DATASET_ADAPTER_REGISTRY.get(adapter_name)


def list_dataset_adapter_names() -> tuple[str, ...]:
    """返回已注册数据集适配器名称。"""
    return _DATASET_ADAPTER_REGISTRY.names()


__all__ = [
    "DEFAULT_ZJH_ADAPTER",
    "ZJH_ADAPTER_NAME",
    "ZJH_ADAPTER_VERSION",
    "ZJH_SOURCE_FORMAT",
    "ZjhAdapter",
    "ZjhMetadataPreview",
    "build_zjh_artifact_from_root",
    "build_zjh_artifact_preview",
    "get_dataset_adapter",
    "list_dataset_adapter_names",
    "read_zjh_metadata",
    "validate_zjh_statistics_request",
    "write_zjh_artifact_preview",
]
