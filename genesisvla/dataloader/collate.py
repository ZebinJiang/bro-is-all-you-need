"""M2 RawSample 批处理工具。"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import RawSample


def _stack_optional_array(
    name: str,
    values: Sequence[NDArray[np.generic] | None],
) -> NDArray[np.generic] | None:
    """堆叠可选数组字段, 同一批内必须同时存在或同时缺失。"""
    present = [value is not None for value in values]
    if not any(present):
        return None
    if not all(present):
        raise ValueError(f"{name} must be present for every sample or no sample")
    arrays = [np.asarray(value) for value in values if value is not None]
    return np.stack(arrays, axis=0)


def _collate_images(samples: Sequence[RawSample]) -> dict[str, NDArray[np.generic]]:
    """按模态名堆叠图像, 不隐式补齐缺失模态。"""
    names = tuple(samples[0].images.keys())
    output: dict[str, NDArray[np.generic]] = {}
    for sample in samples[1:]:
        if tuple(sample.images.keys()) != names:
            raise ValueError("image modalities must match across samples")
    for name in names:
        output[name] = np.stack([np.asarray(sample.images[name]) for sample in samples], axis=0)
    return output


def _collate_action_mask(samples: Sequence[RawSample]) -> NDArray[np.bool_] | None:
    """从 metadata.action_mask 堆叠动作有效维度。"""
    masks = [sample.metadata.get("action_mask") for sample in samples]
    present = [mask is not None for mask in masks]
    if not any(present):
        return None
    if not all(present):
        raise ValueError("action_mask must be present for every sample or no sample")
    return np.stack([np.asarray(mask, dtype=np.bool_) for mask in masks], axis=0)


def collate_raw_samples(samples: Sequence[RawSample]) -> dict[str, Any]:
    """把 RawSample 序列合成为 numpy-only mini batch。

    返回值保持简单字典形态, 方便 M2 早期测试和 legacy 适配器复用。
    """
    if not samples:
        raise ValueError("samples must not be empty")
    return {
        "images": _collate_images(samples),
        "language": tuple(sample.language for sample in samples),
        "actions": _stack_optional_array("actions", [sample.actions for sample in samples]),
        "state": _stack_optional_array("state", [sample.state for sample in samples]),
        "robot_tag": tuple(sample.robot_tag for sample in samples),
        "action_mask": _collate_action_mask(samples),
        "metadata": tuple(dict(sample.metadata) for sample in samples),
    }
