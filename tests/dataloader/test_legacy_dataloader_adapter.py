"""M2 legacy dataloader adapter 契约测试。"""

from __future__ import annotations

import warnings

import numpy as np
import pytest
from genesisvla.dataloader.legacy import LegacyDataloaderAdapter


def test_should_convert_legacy_sample_with_explicit_robot_tag() -> None:
    """验证 legacy 样本通过显式 robot_tag 注入转换为 RawSample。"""
    adapter = LegacyDataloaderAdapter(robot_tag="tiny-arm")

    sample = adapter.to_raw_sample(
        {
            "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
            "language": "pick up the block",
            "actions": np.zeros((2, 3), dtype=np.float32),
            "state": np.zeros((3,), dtype=np.float32),
        }
    )

    assert sample.robot_tag == "tiny-arm"
    assert sample.actions is not None
    assert sample.actions.shape == (2, 3)


def test_should_reject_invalid_legacy_action_shape() -> None:
    """验证 legacy adapter 拒绝错误 action shape。"""
    adapter = LegacyDataloaderAdapter(robot_tag="tiny-arm", action_dim=3)

    with pytest.raises(ValueError, match="action"):
        adapter.to_raw_sample(
            {
                "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
                "language": "pick up the block",
                "actions": np.zeros((2, 2), dtype=np.float32),
                "state": np.zeros((3,), dtype=np.float32),
            }
        )


def test_should_warn_for_unsupported_legacy_fields() -> None:
    """验证 unsupported 字段不会静默丢失。"""
    adapter = LegacyDataloaderAdapter(robot_tag="tiny-arm")

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        sample = adapter.to_raw_sample(
            {
                "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
                "language": "pick up the block",
                "actions": np.zeros((1, 2), dtype=np.float32),
                "state": np.zeros((2,), dtype=np.float32),
                "legacy_extra": "kept-for-review",
            }
        )

    assert any("legacy_extra" in str(warning.message) for warning in caught)
    assert sample.metadata["unsupported_fields"]["legacy_extra"] == "kept-for-review"
