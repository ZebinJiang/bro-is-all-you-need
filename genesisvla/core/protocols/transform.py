"""GenesisVLA 样本转换协议。"""

from __future__ import annotations

from typing import Protocol

from genesisvla.core.types import RawSample


class TransformProtocol(Protocol):
    """定义单条 RawSample 转换需要满足的最小调用形状。"""

    def __call__(self, sample: RawSample) -> RawSample:
        """转换单条原始样本并返回新的或复用的原始样本。"""
        ...
