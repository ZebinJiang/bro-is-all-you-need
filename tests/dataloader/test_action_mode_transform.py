"""M2 动作模式转换契约测试。"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pytest

from genesisvla.core.types import RawSample
from genesisvla.dataloader.transforms import ActionModeTransform


def _raw_sample(**overrides: Any) -> RawSample:
    """构造动作模式测试样本。"""
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray([[1.0, 2.0], [3.0, 5.0], [6.0, 9.0]], dtype=np.float32),
        "state": np.asarray([10.0, 20.0, 30.0], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_roundtrip_absolute_mode() -> None:
    """验证 absolute 模式可逆且不改变数值。"""
    transform = ActionModeTransform(mode="absolute", reference_frame="world")
    sample = _raw_sample()

    output = transform.inverse()(transform(sample))

    assert output.actions is not None
    assert sample.actions is not None
    np.testing.assert_allclose(output.actions, sample.actions)


def test_should_roundtrip_delta_mode() -> None:
    """验证 delta 模式以首步 absolute 策略 round-trip。"""
    transform = ActionModeTransform(
        mode="delta",
        reference_frame="previous_action",
        first_step_policy="absolute",
    )
    sample = _raw_sample()

    delta = transform(sample)
    restored = transform.inverse()(delta)

    assert delta.actions is not None
    assert restored.actions is not None
    assert sample.actions is not None
    np.testing.assert_allclose(delta.actions, np.asarray([[1.0, 2.0], [2.0, 3.0], [3.0, 4.0]]))
    np.testing.assert_allclose(restored.actions, sample.actions)


def test_should_roundtrip_relative_mode_with_explicit_mapping() -> None:
    """验证 relative 模式必须显式声明 state/action 映射。"""
    transform = ActionModeTransform(
        mode="relative",
        reference_frame="state",
        state_to_action_indices=(1, 2),
    )
    sample = _raw_sample()

    relative = transform(sample)
    restored = transform.inverse()(relative)

    assert relative.actions is not None
    assert restored.actions is not None
    assert sample.actions is not None
    np.testing.assert_allclose(relative.actions, sample.actions - np.asarray([20.0, 30.0]))
    np.testing.assert_allclose(restored.actions, sample.actions)


def test_should_reject_empty_horizon() -> None:
    """验证空 horizon 动作显式失败。"""
    with pytest.raises(ValueError, match="horizon"):
        ActionModeTransform(mode="delta", reference_frame="previous_action")(
            _raw_sample(actions=np.zeros((0, 2), dtype=np.float32))
        )


def test_should_reject_invalid_reference_frame() -> None:
    """验证非法 reference frame 会失败。"""
    with pytest.raises(ValueError, match="reference"):
        ActionModeTransform(mode="relative", reference_frame=cast(Any, "camera"))


def test_should_reject_relative_without_explicit_mapping() -> None:
    """验证 relative 模式不隐式假设 state[:action_dim]。"""
    with pytest.raises(ValueError, match="state_to_action_indices"):
        ActionModeTransform(mode="relative", reference_frame="state")
