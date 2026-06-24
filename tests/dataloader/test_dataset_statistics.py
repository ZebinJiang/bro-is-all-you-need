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


def test_should_own_statistics_arrays_without_aliasing() -> None:
    """验证统计数组构造后不受调用方数组突变影响。"""
    mean = np.asarray([1.0, 2.0], dtype=np.float64)
    std = np.asarray([0.5, 1.5], dtype=np.float64)
    mask = np.asarray([True, False], dtype=np.bool_)

    stats = FeatureStatistics(method="mean_std", mean=mean, std=std, valid_mask=mask)
    mean[0] = 99.0
    std[1] = 99.0
    mask[0] = False

    assert stats.mean is not None
    assert stats.std is not None
    assert stats.valid_mask is not None
    np.testing.assert_array_equal(stats.mean, np.asarray([1.0, 2.0]))
    np.testing.assert_array_equal(stats.std, np.asarray([0.5, 1.5]))
    np.testing.assert_array_equal(stats.valid_mask, np.asarray([True, False]))


def test_should_store_statistics_arrays_readonly() -> None:
    """验证统计对象内部数组不可原地写入。"""
    stats = FeatureStatistics(
        method="min_max",
        minimum=np.asarray([0.0, 1.0], dtype=np.float64),
        maximum=np.asarray([4.0, 9.0], dtype=np.float64),
        valid_mask=np.asarray([True, True], dtype=np.bool_),
    )

    assert stats.minimum is not None
    assert stats.maximum is not None
    assert stats.valid_mask is not None
    valid_mask = np.asarray(stats.valid_mask)
    with pytest.raises(ValueError, match="read-only"):
        stats.minimum[0] = 1.0
    with pytest.raises(ValueError, match="read-only"):
        stats.maximum[0] = 5.0
    with pytest.raises(ValueError, match="read-only"):
        valid_mask[0] = False


def test_should_fsync_file_and_directory_when_saving_cache(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """验证统计缓存写入 flush/fsync 文件并 fsync 目录。"""
    path = tmp_path / "statistics.json"
    fsync_fds: list[int] = []

    def fake_fsync(fd: int) -> None:
        fsync_fds.append(fd)

    monkeypatch.setattr(os, "fsync", fake_fsync)

    save_statistics(path, _statistics())

    assert path.exists()
    assert len(fsync_fds) >= 2


def test_should_reject_negative_std_values() -> None:
    """验证 mean/std 统计量不接受负 std。"""
    with pytest.raises(ValueError, match="std"):
        FeatureStatistics(
            method="mean_std",
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, -1.0], dtype=np.float32),
        )


def test_should_reject_maximum_lower_than_minimum() -> None:
    """验证 min/max 统计量不接受 maximum 小于 minimum。"""
    with pytest.raises(ValueError, match="maximum"):
        FeatureStatistics(
            method="min_max",
            minimum=np.asarray([0.0, 2.0], dtype=np.float32),
            maximum=np.asarray([1.0, 1.0], dtype=np.float32),
        )


@pytest.mark.parametrize(
    "bad_mask",
    (
        np.asarray([1, 0], dtype=np.int64),
        np.asarray([1.0, 0.0], dtype=np.float32),
        np.asarray(["true", "false"]),
        np.asarray([True, False], dtype=object),
        [True, 1],
    ),
)
def test_should_reject_numeric_valid_mask_coercion(bad_mask: object) -> None:
    """验证 valid_mask 不接受数值、字符串或 object coercion。"""
    with pytest.raises((TypeError, ValueError), match="valid_mask"):
        FeatureStatistics(
            method="mean_std",
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, 1.0], dtype=np.float32),
            valid_mask=bad_mask,
        )


def test_should_accept_bool_only_valid_mask_sequence() -> None:
    """验证纯 bool 序列会复制为只读 np.bool_ mask。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([0.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 1.0], dtype=np.float32),
        valid_mask=[True, False],
    )

    assert stats.valid_mask is not None
    valid_mask = np.asarray(stats.valid_mask)
    assert valid_mask.dtype == np.bool_
    np.testing.assert_array_equal(valid_mask, np.asarray([True, False]))


def test_should_reject_empty_or_duplicate_feature_names() -> None:
    """验证统计量 feature names 不允许空值或重复。"""
    with pytest.raises(ValueError, match="names"):
        FeatureStatistics(
            method="mean_std",
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, 1.0], dtype=np.float32),
            names=("x", ""),
        )
    with pytest.raises(ValueError, match="names"):
        FeatureStatistics(
            method="mean_std",
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, 1.0], dtype=np.float32),
            names=("x", "x"),
        )


def test_should_reject_empty_statistics_fingerprints() -> None:
    """验证 DatasetStatistics 必须绑定非空 dataset/transform fingerprint。"""
    with pytest.raises(ValueError, match="dataset_fingerprint"):
        _statistics(dataset_fingerprint="")
    with pytest.raises(ValueError, match="transform_fingerprint"):
        _statistics(transform_fingerprint="")
