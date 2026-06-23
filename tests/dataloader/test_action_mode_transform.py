"""动作模式转换测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.transforms import ActionModeTransform


def _raw_sample(**overrides: Any) -> RawSample:
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray(
            [[1.0, 2.0, 4.0], [3.0, 5.0, 9.0], [6.0, 9.0, 15.0]],
            dtype=np.float32,
        ),
        "state": np.asarray([0.5, 1.0, 1.5], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"episode_id": "ep-action-mode"},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_keep_absolute_action_mode_values() -> None:
    """验证 abs 模式保持动作值不变。"""
    sample = _raw_sample()

    output = ActionModeTransform("abs")(sample)

    assert output is sample
    assert output.actions is sample.actions


def test_should_convert_actions_to_delta_mode() -> None:
    """验证 delta 模式保留首行动作并转换后续相邻差分。"""
    sample = _raw_sample()

    output = ActionModeTransform("delta")(sample)

    assert output.actions is not sample.actions
    np.testing.assert_allclose(
        output.actions,
        np.asarray([[1.0, 2.0, 4.0], [2.0, 3.0, 5.0], [3.0, 4.0, 6.0]], dtype=np.float32),
    )


def test_should_convert_actions_to_relative_mode() -> None:
    """验证 relative 模式从每行动作中减去当前状态前缀。"""
    sample = _raw_sample()

    output = ActionModeTransform("relative")(sample)

    np.testing.assert_allclose(
        output.actions,
        np.asarray([[0.5, 1.0, 2.5], [2.5, 4.0, 7.5], [5.5, 8.0, 13.5]], dtype=np.float32),
    )


def test_should_reject_unknown_action_mode() -> None:
    """验证未知动作模式会被拒绝并列出支持值。"""
    with pytest.raises(ValueError, match=r"abs.*delta.*relative"):
        ActionModeTransform("velocity")


def test_should_reject_missing_actions() -> None:
    """验证缺失动作时动作模式转换失败。"""
    with pytest.raises(ValueError, match="actions"):
        ActionModeTransform("delta")(_raw_sample(actions=None))


def test_should_reject_missing_state_for_relative_mode() -> None:
    """验证 relative 模式需要状态。"""
    with pytest.raises(ValueError, match="state"):
        ActionModeTransform("relative")(_raw_sample(state=None))


def test_should_reject_short_state_for_relative_mode() -> None:
    """验证 relative 模式拒绝短于动作维度的状态。"""
    with pytest.raises(ValueError, match="state"):
        ActionModeTransform("relative")(_raw_sample(state=np.asarray([0.5, 1.0], dtype=np.float32)))
