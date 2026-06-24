"""M2 typed batch 与 action mask 契约测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest

import genesisvla.dataloader as dataloader
import genesisvla.dataloader.collate as collate_module
from genesisvla.core.types import RawSample


def _raw_sample(**overrides: Any) -> RawSample:
    """构造小型 RawSample。"""
    payload: dict[str, Any] = {
        "images": {"front": np.zeros((2, 2, 3), dtype=np.uint8)},
        "language": "pick up the block",
        "actions": np.asarray([[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]], dtype=np.float32),
        "state": np.asarray([0.5, 1.0], dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {"sample_source": {"dataset": "tiny", "sample_key": "a"}},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_return_typed_collated_batch_with_default_action_mask() -> None:
    """验证 typed batch 默认生成 `[B,H,D]` action mask。"""
    batch = collate_module.collate_raw_samples_typed(
        (_raw_sample(), _raw_sample(language="place block"))
    )

    assert isinstance(batch, dataloader.CollatedBatch)
    assert batch.batch_size == 2
    assert batch.actions is not None
    assert batch.action_mask is not None
    assert batch.actions.shape == (2, 2, 3)
    assert batch.action_mask.shape == batch.actions.shape
    assert batch.action_mask.dtype == np.bool_
    assert bool(batch.action_mask.all())
    assert batch.action_horizon is not None
    assert batch.action_dim is not None
    np.testing.assert_array_equal(batch.action_horizon, np.asarray([2, 2]))
    np.testing.assert_array_equal(batch.action_dim, np.asarray([3, 3]))
    assert batch.sample_source[0]["dataset"] == "tiny"


def test_should_broadcast_legacy_dimension_mask_at_collate_boundary() -> None:
    """验证 legacy `[D]` mask 只在 collate 边界广播为 `[H,D]`。"""
    mask = np.asarray([True, False, True], dtype=np.bool_)
    batch = collate_module.collate_raw_samples_typed(
        (
            _raw_sample(metadata={"action_mask": mask}),
            _raw_sample(metadata={"action_mask": mask, "sample_source": {"dataset": "tiny"}}),
        )
    )

    assert batch.action_mask is not None
    assert batch.action_mask.shape == (2, 2, 3)
    np.testing.assert_array_equal(batch.action_mask[0, 0], mask)
    np.testing.assert_array_equal(batch.action_mask[0, 1], mask)


def test_should_preserve_canonical_sample_action_mask() -> None:
    """验证 canonical sample `[H,D]` mask 批处理后为 `[B,H,D]`。"""
    mask = np.asarray([[True, False, True], [False, True, True]], dtype=np.bool_)
    batch = collate_module.collate_raw_samples_typed(
        (
            _raw_sample(metadata={"action_mask": mask}),
            _raw_sample(metadata={"action_mask": mask}),
        )
    )

    assert batch.action_mask is not None
    assert batch.action_mask.shape == (2, 2, 3)
    np.testing.assert_array_equal(batch.action_mask[0], mask)


def test_should_reject_invalid_action_mask_rank() -> None:
    """验证 action mask 只能是 legacy `[D]` 或 canonical `[H,D]`。"""
    with pytest.raises(ValueError, match="action_mask"):
        collate_module.collate_raw_samples_typed(
            (_raw_sample(metadata={"action_mask": np.ones((1, 2, 3), dtype=np.bool_)}),)
        )


def test_should_keep_legacy_dict_collator_compatible() -> None:
    """验证旧 dict collator 仍保留当前调用方式。"""
    batch = collate_module.collate_raw_samples((_raw_sample(),))

    assert batch["actions"].shape == (1, 2, 3)
    assert batch["action_mask"].shape == (1, 2, 3)
    assert batch["language"] == ("pick up the block",)


def test_should_pad_variable_horizon_and_action_dim() -> None:
    """验证 variable horizon/action_dim 被补齐并用 `[B,H,D]` mask 标记。"""
    first = _raw_sample(
        actions=np.asarray([[1.0, 2.0], [3.0, 4.0]], dtype=np.float32),
        metadata={"action_mask": np.asarray([[True, True], [True, False]])},
    )
    second = _raw_sample(
        actions=np.asarray([[5.0, 6.0, 7.0]], dtype=np.float32),
        metadata={"action_mask": np.asarray([True, False, True])},
    )

    batch = collate_module.collate_raw_samples_typed((first, second))

    assert batch.actions is not None
    assert batch.action_mask is not None
    assert batch.action_horizon is not None
    assert batch.action_dim is not None
    assert batch.actions.shape == (2, 2, 3)
    np.testing.assert_array_equal(batch.action_horizon, np.asarray([2, 1]))
    np.testing.assert_array_equal(batch.action_dim, np.asarray([2, 3]))
    np.testing.assert_array_equal(
        batch.action_mask,
        np.asarray(
            [
                [[True, True, False], [True, False, False]],
                [[True, False, True], [False, False, False]],
            ],
            dtype=np.bool_,
        ),
    )
    np.testing.assert_array_equal(batch.actions[0, :, 2], np.asarray([0.0, 0.0]))
    np.testing.assert_array_equal(batch.actions[1, 1], np.asarray([0.0, 0.0, 0.0]))
