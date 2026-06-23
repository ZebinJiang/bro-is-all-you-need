"""数据集统计量 schema 与缓存测试。"""

from __future__ import annotations

import json

import numpy as np
import pytest

from genesisvla.dataloader.statistics import (
    DatasetStatistics,
    FeatureStatistics,
    load_statistics,
    save_statistics,
)


def _statistics() -> DatasetStatistics:
    return DatasetStatistics(
        sample_count=3,
        state=FeatureStatistics(
            mean=np.asarray([1.0, 2.0], dtype=np.float32),
            std=np.asarray([0.5, 1.5], dtype=np.float32),
            names=("x", "y"),
        ),
        action=FeatureStatistics(
            mean=np.asarray([3.0, 4.0], dtype=np.float32),
            std=np.asarray([2.0, 4.0], dtype=np.float32),
            names=("ax", "ay"),
        ),
        metadata={"dataset": "tiny"},
    )


def test_should_create_dataset_statistics_with_state_and_action_stats() -> None:
    """验证数据集统计量保留状态、动作、样本数和元数据。"""
    statistics = _statistics()

    assert statistics.schema_version == "1.0"
    assert statistics.sample_count == 3
    assert statistics.state is not None
    assert statistics.action is not None
    assert statistics.state.names == ("x", "y")
    assert statistics.metadata["dataset"] == "tiny"


def test_should_save_and_load_statistics_cache_with_tmp_path(tmp_path) -> None:
    """验证统计量缓存只通过显式路径往返。"""
    path = tmp_path / "statistics.json"

    save_statistics(path, _statistics())
    loaded = load_statistics(path)

    assert path.exists()
    assert loaded.sample_count == 3
    assert loaded.metadata["dataset"] == "tiny"
    assert loaded.state is not None
    assert loaded.action is not None
    np.testing.assert_allclose(loaded.state.mean, np.asarray([1.0, 2.0], dtype=np.float32))
    np.testing.assert_allclose(loaded.action.std, np.asarray([2.0, 4.0], dtype=np.float32))


def test_should_write_deterministic_json_keys(tmp_path) -> None:
    """验证缓存 JSON 使用稳定键顺序方便审查。"""
    path = tmp_path / "statistics.json"

    save_statistics(path, _statistics())

    text = path.read_text(encoding="utf-8")
    assert text.index('"action"') < text.index('"metadata"') < text.index('"sample_count"')


def test_should_reject_invalid_statistics_cache_payload(tmp_path) -> None:
    """验证缺少状态和动作统计量的缓存载荷会被拒绝。"""
    path = tmp_path / "bad-statistics.json"
    path.write_text(json.dumps({"schema_version": "1.0", "sample_count": 1}), encoding="utf-8")

    with pytest.raises(ValueError, match=r"state.*action"):
        load_statistics(path)


def test_should_reject_unsupported_statistics_schema_version(tmp_path) -> None:
    """验证未知 schema 版本会被拒绝。"""
    path = tmp_path / "bad-version.json"
    payload = {
        "schema_version": "9.9",
        "sample_count": 1,
        "state": {"mean": [0.0], "std": [1.0], "names": []},
        "action": None,
        "metadata": {},
    }
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="schema_version"):
        load_statistics(path)


def test_should_reject_non_finite_statistics() -> None:
    """验证非有限统计值会被拒绝。"""
    with pytest.raises(ValueError, match="finite"):
        FeatureStatistics(
            mean=np.asarray([0.0, np.nan], dtype=np.float32),
            std=np.asarray([1.0, 1.0], dtype=np.float32),
        )
