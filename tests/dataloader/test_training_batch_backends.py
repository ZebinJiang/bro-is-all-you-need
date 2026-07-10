"""M4 双后端规范 TrainingBatch 测试。"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

from autovla.core.types import TrainingBatch
from autovla.dataloader.backends import (
    TrainingBatchSource,
    create_training_batch_source,
    get_backend_spec,
    list_backend_keys,
    resolve_backend_key,
)


def _source(root: Path, backend: str) -> TrainingBatchSource:
    """构造使用同一 fixture 契约的后端数据源。"""
    return create_training_batch_source(
        backend,
        root=root,
        seed=11,
        action_horizon=2,
        action_dim=3,
        dataset_fingerprint="dataset",
        transform_fingerprint="transform",
        statistics_fingerprint="statistics",
    )


def test_backend_registry_should_be_explicit_lazy_and_canonical() -> None:
    """验证规范键、显式别名和 WebDataset 懒导入。"""
    before = set(sys.modules)

    assert list_backend_keys() == ("robodm_container_v1", "webdataset_tar")
    assert resolve_backend_key("robodm_style") == "robodm_container_v1"
    assert resolve_backend_key("webdataset_native") == "webdataset_tar"
    assert get_backend_spec("robodm_container_v1").capabilities.native_compatible is False
    assert "webdataset" not in (set(sys.modules) - before)
    with pytest.raises(ValueError, match=r"unknown data\.backend"):
        resolve_backend_key("fastest")


def test_existing_stores_should_emit_equivalent_canonical_batches(tmp_path: Path) -> None:
    """验证两个物理 store 经共享桥产生完全等价的规范批。"""
    batches: list[TrainingBatch] = []
    manifests: list[dict[str, object]] = []
    for backend in ("webdataset_tar", "robodm_container_v1"):
        source = _source(tmp_path / backend, backend)
        try:
            manifests.append(source.prepare())
            batches.append(source.read_batch((0, 1)))
        finally:
            source.close()

    webdataset_batch, robodm_batch = batches
    assert manifests[0]["sample_count"] == 8
    assert manifests[0]["episode_count"] == 2
    assert manifests[0]["logical_fingerprint"] == manifests[1]["logical_fingerprint"]
    assert (
        webdataset_batch.metadata["logical_batch_fingerprint"]
        == robodm_batch.metadata["logical_batch_fingerprint"]
    )
    assert webdataset_batch.sample_source == robodm_batch.sample_source
    assert webdataset_batch.language == robodm_batch.language
    assert webdataset_batch.action_mask.dtype == np.bool_
    assert webdataset_batch.action_mask.shape == (2, 2, 3)
    assert set(webdataset_batch.images) == {"camera.rgb_0", "camera.rgb_1", "camera.rgb_2"}
    np.testing.assert_array_equal(webdataset_batch.actions, robodm_batch.actions)
    np.testing.assert_array_equal(webdataset_batch.action_mask, robodm_batch.action_mask)
    np.testing.assert_array_equal(webdataset_batch.state, robodm_batch.state)
    for name in webdataset_batch.images:
        np.testing.assert_array_equal(webdataset_batch.images[name], robodm_batch.images[name])
