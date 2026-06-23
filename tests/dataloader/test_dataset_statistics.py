"""M2 数据集统计量 schema/cache 契约测试。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from genesisvla.dataloader.statistics import (
    DatasetStatistics,
    FeatureStatistics,
    load_statistics,
    save_statistics,
)


def _statistics(**overrides: Any) -> DatasetStatistics:
    """构造稳定统计量。"""
    payload: dict[str, Any] = {
        "schema_version": "2.0",
        "dataset_fingerprint": "dataset-a",
        "transform_fingerprint": "transform-a",
        "count": 3,
        "state": FeatureStatistics(
            method="mean_std",
            mean=np.asarray([1.0, 2.0], dtype=np.float32),
            std=np.asarray([0.5, 1.5], dtype=np.float32),
            valid_mask=np.asarray([True, False]),
        ),
        "action": FeatureStatistics(
            method="min_max",
            minimum=np.asarray([0.0, 1.0], dtype=np.float32),
            maximum=np.asarray([4.0, 9.0], dtype=np.float32),
            valid_mask=np.asarray([True, True]),
        ),
        "metadata": {"source": "tiny"},
    }
    payload.update(overrides)
    return DatasetStatistics(**payload)


def test_should_roundtrip_statistics_schema(tmp_path: Path) -> None:
    """验证统计量 JSON schema 往返保持关键字段。"""
    path = tmp_path / "statistics.json"

    save_statistics(path, _statistics())
    loaded = load_statistics(
        path,
        expected_dataset_fingerprint="dataset-a",
        expected_transform_fingerprint="transform-a",
    )

    assert loaded.schema_version == "2.0"
    assert loaded.count == 3
    assert loaded.state is not None
    assert loaded.action is not None
    assert loaded.checksum
    np.testing.assert_array_equal(loaded.state.valid_mask, np.asarray([True, False]))


def test_should_write_statistics_cache_atomically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证缓存写入使用同目录临时文件和 os.replace。"""
    path = tmp_path / "statistics.json"
    captured: dict[str, Path] = {}
    original_replace = os.replace

    def fake_replace(src: str | os.PathLike[str], dst: str | os.PathLike[str]) -> None:
        src_path = Path(src)
        dst_path = Path(dst)
        captured["src"] = src_path
        captured["dst"] = dst_path
        original_replace(src_path, dst_path)

    monkeypatch.setattr(os, "replace", fake_replace)

    save_statistics(path, _statistics())

    assert captured["dst"] == path
    assert captured["src"].parent == path.parent
    assert not list(tmp_path.glob("*.tmp"))


def test_should_reject_stale_dataset_fingerprint(tmp_path: Path) -> None:
    """验证 dataset fingerprint 过期会失败。"""
    path = tmp_path / "statistics.json"
    save_statistics(path, _statistics(dataset_fingerprint="old"))

    with pytest.raises(ValueError, match="dataset_fingerprint"):
        load_statistics(path, expected_dataset_fingerprint="new")


def test_should_reject_stale_transform_fingerprint(tmp_path: Path) -> None:
    """验证 transform fingerprint 过期会失败。"""
    path = tmp_path / "statistics.json"
    save_statistics(path, _statistics(transform_fingerprint="old"))

    with pytest.raises(ValueError, match="transform_fingerprint"):
        load_statistics(path, expected_transform_fingerprint="new")


def test_should_reject_checksum_mismatch(tmp_path: Path) -> None:
    """验证缓存内容被篡改时 checksum 会失败。"""
    path = tmp_path / "statistics.json"
    save_statistics(path, _statistics())
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["count"] = 99
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="checksum"):
        load_statistics(path)


def test_should_reject_non_json_safe_metadata() -> None:
    """验证 metadata 必须可 JSON 序列化。"""
    with pytest.raises(TypeError, match="metadata"):
        _statistics(metadata={"bad": object()}).to_json_dict()
