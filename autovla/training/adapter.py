"""M2 typed batch 到 M3 模型输入的适配器。"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

import numpy as np

from autovla.core.types import ActionMask, BatchSample, ModelInput, NumericArray, RawSample
from autovla.dataloader import CollatedBatch
from autovla.training.losses import validate_action_mask


def _numeric_array(value: object, *, name: str) -> NumericArray:
    """复制数值数组并返回只读视图。"""
    array = np.asarray(value)
    if not np.issubdtype(array.dtype, np.number):
        raise TypeError(f"{name} must be numeric")
    owned: NumericArray = np.array(array, copy=True)
    owned.setflags(write=False)
    return owned


def _plain_json_value(value: object) -> object:
    """递归转换 JSON-like 值, 并校验映射键为字符串。"""
    if isinstance(value, Mapping):
        mapping = cast(Mapping[object, object], value)
        output: dict[str, object] = {}
        for raw_key, raw_value in mapping.items():
            if not isinstance(raw_key, str):
                raise TypeError("metadata mapping keys must be strings")
            output[raw_key] = _plain_json_value(raw_value)
        return output
    if isinstance(value, tuple):
        sequence = cast(tuple[object, ...], value)
        output_items: list[object] = []
        for child in sequence:
            output_items.append(_plain_json_value(child))
        return tuple(output_items)
    if isinstance(value, list):
        sequence = cast(list[object], value)
        return tuple(_plain_json_value(child) for child in sequence)
    return value


def _plain_mapping(value: Mapping[str, object]) -> dict[str, object]:
    """把 JSON-like 映射转换为普通 dict, 供训练侧快照使用。"""
    return {key: _plain_json_value(item) for key, item in value.items()}


def _sample_from_collated(
    batch: CollatedBatch,
    *,
    index: int,
    action_mask: ActionMask | None,
) -> RawSample:
    """从 batch-major 数组恢复单条 RawSample。"""
    images = {
        name: _numeric_array(value[index], name=f"images.{name}")
        for name, value in batch.images.items()
    }
    state = _numeric_array(batch.state[index], name="state") if batch.state is not None else None
    actions: NumericArray | None = None
    sample_mask: ActionMask | None = None
    if batch.actions is not None:
        if batch.action_horizon is None or batch.action_dim is None or action_mask is None:
            raise ValueError("actions require action_horizon, action_dim, and action_mask")
        horizon = int(batch.action_horizon[index])
        action_dim = int(batch.action_dim[index])
        actions = _numeric_array(batch.actions[index, :horizon, :action_dim], name="actions")
        sample_mask = np.array(action_mask[index, :horizon, :action_dim], dtype=np.bool_, copy=True)
        sample_mask.setflags(write=False)

    metadata = _plain_mapping(batch.metadata[index])
    metadata["sample_source"] = _plain_mapping(batch.sample_source[index])
    if sample_mask is not None:
        metadata["action_mask"] = sample_mask
    return RawSample(
        images=images,
        language=batch.language[index],
        actions=actions,
        state=state,
        robot_tag=batch.robot_tag[index],
        metadata=metadata,
    )


def collated_batch_to_model_input(
    batch: CollatedBatch,
    *,
    dataset_fingerprint: str,
    transform_fingerprint: str,
    statistics_fingerprint: str,
    seed: int = 0,
    epoch: int = 0,
    worker_id: int = 0,
    worker_count: int = 1,
    rank: int = 0,
    world_size: int = 1,
) -> ModelInput:
    """把 M2 ``CollatedBatch`` 映射为 M3 本地 runner 的 ``ModelInput``。"""
    action_mask = (
        validate_action_mask(batch.action_mask, batch.actions.shape)
        if batch.actions is not None
        else None
    )
    samples = tuple(
        _sample_from_collated(batch, index=index, action_mask=action_mask)
        for index in range(batch.batch_size)
    )
    tensors: dict[str, NumericArray] = {
        f"image.{name}": _numeric_array(value, name=f"image.{name}")
        for name, value in batch.images.items()
    }
    if batch.actions is not None:
        tensors["actions"] = _numeric_array(batch.actions, name="actions")
    if batch.state is not None:
        tensors["state"] = _numeric_array(batch.state, name="state")
    if batch.action_horizon is not None:
        tensors["action_horizon"] = _numeric_array(batch.action_horizon, name="action_horizon")
    if batch.action_dim is not None:
        tensors["action_dim"] = _numeric_array(batch.action_dim, name="action_dim")

    metadata: dict[str, object] = {
        "dataset_fingerprint": dataset_fingerprint,
        "transform_fingerprint": transform_fingerprint,
        "statistics_fingerprint": statistics_fingerprint,
        "seed": seed,
        "epoch": epoch,
        "worker_id": worker_id,
        "worker_count": worker_count,
        "rank": rank,
        "world_size": world_size,
        "sample_source": tuple(_plain_mapping(item) for item in batch.sample_source),
    }
    if action_mask is not None:
        metadata["action_mask"] = action_mask
    return ModelInput(
        batch=BatchSample(samples=samples, metadata={"source": "collated_batch"}),
        tensors=tensors,
        metadata=metadata,
    )
