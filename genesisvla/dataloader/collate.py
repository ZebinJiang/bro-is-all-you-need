"""M2 RawSample 批处理工具。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, cast

import numpy as np
from numpy.typing import NDArray

from genesisvla.core.types import NumericArray, RawSample
from genesisvla.dataloader.contracts import CollatedBatch


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


def _collate_actions(
    samples: Sequence[RawSample],
) -> tuple[NumericArray | None, NDArray[np.int64] | None, NDArray[np.int64] | None]:
    """补齐 variable horizon/action_dim 的 action batch。"""
    present = [sample.actions is not None for sample in samples]
    if not any(present):
        return None, None, None
    if not all(present):
        raise ValueError("actions must be present for every sample or no sample")

    arrays = [np.asarray(sample.actions) for sample in samples if sample.actions is not None]
    for array in arrays:
        if array.ndim != 2:
            raise ValueError("actions must have shape [H,D]")
    horizons = np.asarray([array.shape[0] for array in arrays], dtype=np.int64)
    dims = np.asarray([array.shape[1] for array in arrays], dtype=np.int64)
    max_horizon = int(horizons.max())
    max_dim = int(dims.max())
    dtype = np.result_type(*(array.dtype for array in arrays))
    output = np.zeros((len(arrays), max_horizon, max_dim), dtype=dtype)
    for index, array in enumerate(arrays):
        horizon, dim = array.shape
        output[index, :horizon, :dim] = array
    return cast(NumericArray, output), horizons, dims


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


def _broadcast_action_mask(
    mask: object,
    *,
    action_shape: tuple[int, int],
) -> NDArray[np.bool_]:
    """把 sample 级 legacy/canonical mask 转为 `[H,D]`。"""
    array = np.asarray(mask, dtype=np.bool_)
    if array.ndim == 1:
        if array.shape[0] != action_shape[1]:
            raise ValueError("action_mask legacy dimension must match action_dim")
        return np.broadcast_to(array, action_shape).copy()
    if array.ndim == 2:
        if array.shape != action_shape:
            raise ValueError("action_mask shape must match sample actions")
        return array.copy()
    raise ValueError("action_mask must have shape [D] or [H,D]")


def _collate_action_mask(
    samples: Sequence[RawSample],
    actions: NumericArray | None,
    action_horizon: NDArray[np.int64] | None,
    action_dim: NDArray[np.int64] | None,
) -> NDArray[np.bool_] | None:
    """从 metadata.action_mask 生成 canonical `[B,H,D]` mask。"""
    if actions is None:
        if any("action_mask" in sample.metadata for sample in samples):
            raise ValueError("action_mask requires actions")
        return None
    if action_horizon is None or action_dim is None:
        raise ValueError("action_horizon/action_dim are required for action masks")

    masks = [sample.metadata.get("action_mask") for sample in samples]
    present = [mask is not None for mask in masks]
    has_explicit_mask = any(present)
    if has_explicit_mask and not all(present):
        raise ValueError("action_mask must be present for every sample or no sample")
    output = np.zeros(actions.shape, dtype=np.bool_)
    for index, (sample, mask) in enumerate(zip(samples, masks, strict=True)):
        if sample.actions is None:
            raise ValueError("action_mask requires actions")
        action_shape = (int(action_horizon[index]), int(action_dim[index]))
        sample_mask = (
            np.ones(action_shape, dtype=np.bool_)
            if not has_explicit_mask
            else _broadcast_action_mask(mask, action_shape=action_shape)
        )
        output[index, : action_shape[0], : action_shape[1]] = sample_mask
    return output


def _metadata_without_action_mask(sample: RawSample) -> Mapping[str, object]:
    """移除 collate 边界消费的 runtime action_mask。"""
    return {str(key): value for key, value in sample.metadata.items() if key != "action_mask"}


def collate_raw_samples_typed(samples: Sequence[RawSample]) -> CollatedBatch:
    """把 RawSample 序列合成为 typed numpy-only mini batch。"""
    if not samples:
        raise ValueError("samples must not be empty")
    actions, action_horizon, action_dim = _collate_actions(samples)
    state = _stack_optional_array("state", [sample.state for sample in samples])
    return CollatedBatch(
        images=cast(Mapping[str, NumericArray], _collate_images(samples)),
        language=tuple(sample.language for sample in samples),
        actions=actions,
        state=cast(NumericArray | None, state),
        robot_tag=tuple(sample.robot_tag for sample in samples),
        action_mask=_collate_action_mask(
            samples,
            actions,
            action_horizon,
            action_dim,
        ),
        metadata=tuple(_metadata_without_action_mask(sample) for sample in samples),
        action_horizon=action_horizon,
        action_dim=action_dim,
    )


def collate_raw_samples(samples: Sequence[RawSample]) -> dict[str, Any]:
    """把 RawSample 序列合成为 legacy dict mini batch。"""
    return collate_raw_samples_typed(samples).to_legacy_dict()
