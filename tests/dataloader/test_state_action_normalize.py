"""状态与动作归一化测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.statistics import DatasetStatistics, FeatureStatistics
from genesisvla.dataloader.transforms import StateActionNormalize, StateActionUnnormalize


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray([[2.0, 5.0, 9.0], [4.0, 9.0, 17.0]], dtype=np.float32),
        "state": np.asarray([2.0, 4.0, 10.0], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-normalize"},
    }
    payload.update(overrides)
    return RawSample(**payload)


def _statistics() -> DatasetStatistics:
    return DatasetStatistics(
        sample_count=2,
        state=FeatureStatistics(
            mean=np.asarray([1.0, 2.0, 2.0], dtype=np.float32),
            std=np.asarray([1.0, 2.0, 4.0], dtype=np.float32),
            names=("s0", "s1", "s2"),
        ),
        action=FeatureStatistics(
            mean=np.asarray([1.0, 1.0, 1.0], dtype=np.float32),
            std=np.asarray([1.0, 2.0, 4.0], dtype=np.float32),
            names=("a0", "a1", "a2"),
        ),
    )


def test_should_normalize_state_and_action_values_without_mutating_input() -> None:
    """验证状态和动作按统计量归一化且不原地修改输入。"""
    sample = _raw_sample()
    original_state = sample.state.copy()
    original_actions = sample.actions.copy()

    output = StateActionNormalize(_statistics())(sample)

    assert output is not sample
    assert output.images is sample.images
    assert output.metadata is sample.metadata
    assert output.state is not sample.state
    assert output.actions is not sample.actions
    np.testing.assert_allclose(output.state, np.asarray([1.0, 1.0, 2.0], dtype=np.float32))
    np.testing.assert_allclose(
        output.actions,
        np.asarray([[1.0, 2.0, 2.0], [3.0, 4.0, 4.0]], dtype=np.float32),
    )
    np.testing.assert_array_equal(sample.state, original_state)
    np.testing.assert_array_equal(sample.actions, original_actions)


def test_should_unnormalize_state_and_action_values() -> None:
    """验证反归一化能恢复归一化前的状态和动作。"""
    sample = _raw_sample()
    statistics = _statistics()

    normalized = StateActionNormalize(statistics)(sample)
    restored = StateActionUnnormalize(statistics)(normalized)

    np.testing.assert_allclose(restored.state, sample.state)
    np.testing.assert_allclose(restored.actions, sample.actions)


def test_should_reject_missing_state_when_state_normalization_enabled() -> None:
    """验证缺失状态时归一化报出清晰错误。"""
    sample = _raw_sample(state=None)

    with pytest.raises(ValueError, match="state"):
        StateActionNormalize(_statistics())(sample)


def test_should_reject_missing_actions_when_action_normalization_enabled() -> None:
    """验证缺失动作时归一化报出清晰错误。"""
    sample = _raw_sample(actions=None)

    with pytest.raises(ValueError, match="actions"):
        StateActionNormalize(_statistics())(sample)


def test_should_reject_zero_statistics_std() -> None:
    """验证零标准差统计量会被拒绝。"""
    with pytest.raises(ValueError, match="std"):
        FeatureStatistics(
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, 0.0], dtype=np.float32),
        )


def test_should_reject_statistics_shape_mismatch() -> None:
    """验证均值和标准差形状不一致会被拒绝。"""
    with pytest.raises(ValueError, match="shape"):
        FeatureStatistics(
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0], dtype=np.float32),
        )


def test_should_reject_sample_dimension_mismatch() -> None:
    """验证样本维度和统计量维度不一致会被拒绝。"""
    statistics = DatasetStatistics(
        sample_count=1,
        state=FeatureStatistics(
            mean=np.asarray([0.0, 0.0], dtype=np.float32),
            std=np.asarray([1.0, 1.0], dtype=np.float32),
        ),
    )

    with pytest.raises(ValueError, match="state"):
        StateActionNormalize(statistics)(_raw_sample(actions=None))
