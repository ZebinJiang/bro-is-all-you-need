"""RawSample 转换组合器。"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import cast

from genesisvla.core.protocols import TransformProtocol
from genesisvla.core.types import RawSample


class ComposeTransform:
    """按声明顺序组合多个单样本转换。

    Args:
        transforms: 单样本转换序列。空序列表示 identity 转换。
    """

    def __init__(self, transforms: Iterable[TransformProtocol] = ()) -> None:
        """保存不可变转换序列并提前拒绝不可调用成员。"""
        self.transforms: tuple[object, ...] = tuple(transforms)
        for index, transform in enumerate(self.transforms):
            if not callable(transform):
                raise TypeError(f"transform step {index} must be callable")

    def __call__(self, sample: object) -> RawSample:
        """从左到右执行转换并校验每一步返回 RawSample。"""
        if not isinstance(sample, RawSample):
            raise TypeError("ComposeTransform input must be a RawSample")

        current = sample
        for index, transform_object in enumerate(self.transforms):
            transform = cast(Callable[[RawSample], object], transform_object)
            output = transform(current)
            if not isinstance(output, RawSample):
                name = transform_object.__class__.__name__
                raise TypeError(f"transform step {index} ({name}) must return RawSample")
            current = output
        return current
