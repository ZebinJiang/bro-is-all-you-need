"""GenesisVLA 模态校验工具。"""

from __future__ import annotations

from collections.abc import Iterable

from genesisvla.core.types.sample import RawSample


def validate_required_modalities(sample: RawSample, required: Iterable[str]) -> None:
    """确认样本包含所有必需模态。

    Args:
        sample: 待校验的原始样本。
        required: 必须存在于 ``sample.images`` 的模态名。

    Raises:
        ValueError: 当任何必需模态缺失时抛出,并在消息中列出缺失模态。
    """
    missing = tuple(name for name in required if name not in sample.images)
    if missing:
        joined = ", ".join(missing)
        raise ValueError(f"missing required modalities: {joined}")
