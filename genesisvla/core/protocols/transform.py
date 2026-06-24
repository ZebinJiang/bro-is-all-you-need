"""GenesisVLA 转换协议。"""

from __future__ import annotations

from typing import Protocol

from genesisvla.core.types import RawSample


class TransformProtocol(Protocol):
    """定义 RawSample 到 RawSample 的通用转换协议。"""

    def __call__(self, sample: RawSample) -> RawSample:
        """转换单条 RawSample 并返回新的 RawSample。"""
        ...
