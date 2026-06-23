"""M2 图像转换契约测试。"""

from __future__ import annotations

from typing import Any

import numpy as np
import pytest
from numpy.typing import NDArray

from genesisvla.core.types import RawSample
from genesisvla.dataloader.transforms import ImageAugment, ImageNormalize, ImageResize


def _raw_sample(image: NDArray[np.generic], **overrides: Any) -> RawSample:
    """构造单图像样本。"""
    payload: dict[str, Any] = {
        "images": {"front": image},
        "language": "pick up the block",
        "actions": np.zeros((1, 2), dtype=np.float32),
        "state": np.zeros((2,), dtype=np.float32),
        "robot_tag": "debug-arm",
        "metadata": {},
    }
    payload.update(overrides)
    return RawSample(**payload)


def test_should_resize_hwc_image_to_target_shape() -> None:
    """验证 HWC 图像 resize 输出目标形状且不依赖外部后端。"""
    image = np.arange(4 * 4 * 3, dtype=np.uint8).reshape(4, 4, 3)

    output = ImageResize(size=(2, 3), channel_order="HWC")(_raw_sample(image))

    assert output.images["front"].shape == (2, 3, 3)
    assert output.images["front"].dtype == np.uint8


def test_should_normalize_hwc_image_with_known_fixture() -> None:
    """验证图像归一化使用明确 dtype/range/channel 语义。"""
    image = np.asarray([[[0, 127, 255]]], dtype=np.uint8)

    output = ImageNormalize(
        mean=(0.0, 0.5, 1.0),
        std=(1.0, 0.5, 1.0),
        channel_order="HWC",
        input_range="0_255",
    )(_raw_sample(image))

    np.testing.assert_allclose(
        output.images["front"],
        np.asarray([[[0.0, -0.00392157, 0.0]]], dtype=np.float32),
        atol=1e-6,
    )


def test_should_apply_deterministic_augmentation() -> None:
    """验证增强在固定 seed 下确定可复现。"""
    image = np.arange(2 * 3 * 1, dtype=np.uint8).reshape(2, 3, 1)
    transform = ImageAugment(mode="horizontal_flip", probability=1.0, seed=7)

    left = transform(_raw_sample(image))
    right = transform(_raw_sample(image))

    np.testing.assert_array_equal(left.images["front"], right.images["front"])
    np.testing.assert_array_equal(left.images["front"], image[:, ::-1, :])


def test_should_reject_invalid_channel_layout() -> None:
    """验证无效 channel layout 会失败, 不猜测格式。"""
    image = np.zeros((2, 2), dtype=np.uint8)

    with pytest.raises(ValueError, match="channel"):
        ImageNormalize(mean=(0.0,), std=(1.0,), channel_order="HWC")(_raw_sample(image))
