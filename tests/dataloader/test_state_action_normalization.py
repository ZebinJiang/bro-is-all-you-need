"""M2 状态/动作归一化契约测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import FeatureStatistics
from genesisvla.dataloader.transforms import StateActionNormalize, StateActionUnnormalize


def _raw_sample(**overrides: Any) -> RawSample:
    """构造包含 padding 维度的小样本。"""
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray([[2.0, 5.0, 99.0], [4.0, 9.0, 99.0]], dtype=np.float32),
        "state": np.asarray([2.0, 4.0, 99.0], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"action_mask": np.asarray([True, True, False])},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_normalize_and_unnormalize_meanstd() -> None:
    """验证 mean/std 模式数值 round-trip。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([1.0, 1.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 2.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )
    sample = _raw_sample()

    normalized = StateActionNormalize(action=stats)(sample)
    restored = StateActionUnnormalize(action=stats)(normalized)

    assert normalized.actions is not None
    assert restored.actions is not None
    assert sample.actions is not None
    np.testing.assert_allclose(normalized.actions[:, :2], np.asarray([[1.0, 2.0], [3.0, 4.0]]))
    np.testing.assert_allclose(restored.actions, sample.actions)


def test_should_normalize_and_unnormalize_minmax() -> None:
    """验证 min/max 模式数值 round-trip。"""
    stats = FeatureStatistics(
        method="min_max",
        minimum=np.asarray([0.0, 1.0, 0.0], dtype=np.float32),
        maximum=np.asarray([4.0, 9.0, 1.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )
    sample = _raw_sample()

    normalized = StateActionNormalize(action=stats)(sample)
    restored = StateActionUnnormalize(action=stats)(normalized)

    assert normalized.actions is not None
    assert restored.actions is not None
    assert sample.actions is not None
    np.testing.assert_allclose(normalized.actions[:, :2], np.asarray([[0.5, 0.5], [1.0, 1.0]]))
    np.testing.assert_allclose(restored.actions, sample.actions)


def test_should_preserve_masked_padding_dims() -> None:
    """验证 padding/invalid 维度保持原值。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([0.0, 0.0, 50.0], dtype=np.float32),
        std=np.asarray([1.0, 1.0, 10.0], dtype=np.float32),
        valid_mask=np.asarray([True, True, False]),
    )

    normalized = StateActionNormalize(state=stats, action=stats)(_raw_sample())

    assert normalized.state is not None
    assert normalized.state[2] == 99.0
    assert normalized.actions is not None
    np.testing.assert_array_equal(normalized.actions[:, 2], np.asarray([99.0, 99.0]))


def test_should_handle_zero_variance_by_policy() -> None:
    """验证零方差使用显式 identity 策略, 不产生 NaN。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([2.0], dtype=np.float32),
        std=np.asarray([0.0], dtype=np.float32),
        zero_variance_policy="identity",
    )
    sample = _raw_sample(state=np.asarray([2.0], dtype=np.float32), actions=None)

    normalized = StateActionNormalize(state=stats)(sample)
    restored = StateActionUnnormalize(state=stats)(normalized)

    assert normalized.state is not None
    assert normalized.state[0] == 2.0
    assert restored.state is not None
    assert sample.state is not None
    np.testing.assert_allclose(restored.state, sample.state)


def test_should_reject_statistics_dimension_mismatch() -> None:
    """验证统计维度和样本维度不匹配会失败。"""
    stats = FeatureStatistics(
        method="mean_std",
        mean=np.asarray([0.0, 0.0], dtype=np.float32),
        std=np.asarray([1.0, 1.0], dtype=np.float32),
    )

    with pytest.raises(ValueError, match="dimension"):
        StateActionNormalize(action=stats)(_raw_sample())
