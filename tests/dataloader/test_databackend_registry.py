"""DataBackend registry 行为测试。"""

from __future__ import annotations

import sys

import pytest

from autovla.dataloader.backends import DataBackendRegistry, DataBackendRegistryError
from autovla.dataloader.backends.registry import default_backend_registry


def test_default_backend_registry_is_lightweight_and_complete() -> None:
    """默认 registry 不应导入重型运行时, 并发布四类本地 probe。"""
    before = set(sys.modules)

    registry = default_backend_registry()

    assert isinstance(registry, DataBackendRegistry)
    assert registry.keys() == ("lerobot_local", "raw_zjh", "synthetic", "webdataset_tar")
    assert registry.get("webdataset_tar").supported_layouts == ("tar_shards",)
    assert registry.get("raw_zjh").prohibited_side_effects == (
        "dataset_copy",
        "media_decode",
        "network",
        "training",
    )
    imported = set(sys.modules) - before
    assert not (imported & {"torch", "lerobot", "webdataset", "openpi", "jax", "flax"})


def test_backend_registry_rejects_duplicates_and_unknown_keys() -> None:
    """registry 必须给出显式 factory 错误, 不静默回退。"""
    spec = default_backend_registry().get("synthetic")

    with pytest.raises(DataBackendRegistryError, match="duplicate backend"):
        DataBackendRegistry((spec, spec))
    with pytest.raises(DataBackendRegistryError, match="unknown backend"):
        default_backend_registry().get("missing")
