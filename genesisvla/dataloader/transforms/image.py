"""M2 numpy 图像转换。"""

from __future__ import annotations

from dataclasses import replace
from typing import Literal, Mapping

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import RawSample

ChannelOrder = Literal["HWC", "CHW"]
InputRange = Literal["0_255", "0_1"]


def _validate_image(image: NDArray[np.generic], channel_order: ChannelOrder) -> None:
    """验证图像 layout 包含显式 channel 维。"""
    if image.ndim != 3:
        raise ValueError("image must include channel dimension")
    channel_dim = 2 if channel_order == "HWC" else 0
    if image.shape[channel_dim] not in {1, 3, 4}:
        raise ValueError("image channel dimension must be 1, 3, or 4")


def _resize_nearest(
    image: NDArray[np.generic],
    size: tuple[int, int],
    order: ChannelOrder,
) -> NDArray[np.generic]:
    """使用 nearest-neighbor 实现小型 CPU resize。"""
    if size[0] <= 0 or size[1] <= 0:
        raise ValueError("resize size must be positive")
    if order == "CHW":
        source = np.moveaxis(image, 0, -1)
    else:
        source = image
    height, width = source.shape[:2]
    row_index = np.linspace(0, height - 1, size[0]).round().astype(np.int64)
    col_index = np.linspace(0, width - 1, size[1]).round().astype(np.int64)
    resized = source[row_index][:, col_index]
    if order == "CHW":
        return np.moveaxis(resized, -1, 0)
    return resized


def _copy_images(images: Mapping[str, NDArray[np.generic]]) -> dict[str, NDArray[np.generic]]:
    """复制图像映射为普通 dict。"""
    return {name: np.array(value, copy=True) for name, value in images.items()}


class ImageResize:
    """对所有图像模态执行 deterministic nearest-neighbor resize。"""

    def __init__(self, *, size: tuple[int, int], channel_order: ChannelOrder = "HWC") -> None:
        self.size: tuple[int, int] = size
        self.channel_order: ChannelOrder = channel_order

    def __call__(self, sample: RawSample) -> RawSample:
        """返回 resize 后的新样本。"""
        images = _copy_images(sample.images)
        output: dict[str, NDArray[np.generic]] = {}
        for name, image in images.items():
            _validate_image(image, self.channel_order)
            output[name] = _resize_nearest(image, self.size, self.channel_order)
        return replace(sample, images=output)


class ImageNormalize:
    """按显式 channel order 和输入范围归一化图像。"""

    def __init__(
        self,
        *,
        mean: tuple[float, ...],
        std: tuple[float, ...],
        channel_order: ChannelOrder = "HWC",
        input_range: InputRange = "0_1",
    ) -> None:
        self.mean: NDArray[np.float32] = np.asarray(mean, dtype=np.float32)
        self.std: NDArray[np.float32] = np.asarray(std, dtype=np.float32)
        self.channel_order: ChannelOrder = channel_order
        self.input_range: InputRange = input_range
        if self.mean.shape != self.std.shape:
            raise ValueError("mean and std channel dimensions must match")
        if bool(np.any(self.std == 0.0)):
            raise ValueError("std must be non-zero")

    def __call__(self, sample: RawSample) -> RawSample:
        """返回 float32 归一化图像样本。"""
        output: dict[str, NDArray[np.float32]] = {}
        for name, image in sample.images.items():
            _validate_image(image, self.channel_order)
            array = np.asarray(image, dtype=np.float32)
            if self.input_range == "0_255":
                array = array / np.float32(255.0)
            channels = array.shape[2] if self.channel_order == "HWC" else array.shape[0]
            if channels != self.mean.shape[0]:
                raise ValueError("channel statistics dimension mismatch")
            if self.channel_order == "HWC":
                centered = array - self.mean.reshape(1, 1, -1)
                output[name] = (centered / self.std.reshape(1, 1, -1)).astype(np.float32)
            else:
                centered = array - self.mean.reshape(-1, 1, 1)
                output[name] = (centered / self.std.reshape(-1, 1, 1)).astype(np.float32)
        return replace(sample, images=output)


class ImageAugment:
    """最小 deterministic CPU 图像增强。"""

    def __init__(
        self,
        *,
        mode: Literal["none", "horizontal_flip"] = "none",
        probability: float = 1.0,
        seed: int = 0,
    ) -> None:
        if not 0.0 <= probability <= 1.0:
            raise ValueError("probability must be in [0, 1]")
        self.mode = mode
        self.probability = probability
        self.seed = seed

    def __call__(self, sample: RawSample) -> RawSample:
        """按固定 seed 对所有图像应用同一增强决策。"""
        rng = np.random.default_rng(self.seed)
        should_apply = bool(rng.random() < self.probability)
        output = _copy_images(sample.images)
        if self.mode == "none" or not should_apply:
            return replace(sample, images=output)
        if self.mode != "horizontal_flip":
            raise ValueError(f"unsupported image augment mode: {self.mode}")
        return replace(sample, images={name: image[:, ::-1, ...] for name, image in output.items()})
