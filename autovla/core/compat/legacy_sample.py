"""AutoVLA 旧样本字典兼容适配器。"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any, cast

import numpy as np

from autovla.core.types.action import ImageLike, NumericArray
from autovla.core.types.modality import validate_required_modalities
from autovla.core.types.sample import RawSample


def _array(value: Any) -> NumericArray:
    """将未知输入转换为 numpy 数组。"""
    return np.asarray(value)


def _collect_images(payload: Mapping[str, Any]) -> dict[str, ImageLike]:
    """从直接映射或扁平 observation 键中收集图像数组。"""
    direct_images = payload.get("images")
    if isinstance(direct_images, Mapping):
        image_mapping = cast(Mapping[Any, Any], direct_images)
        return {str(name): _array(value) for name, value in image_mapping.items()}

    prefix = "observation.images."
    return {
        key.removeprefix(prefix): _array(value)
        for key, value in payload.items()
        if key.startswith(prefix)
    }


def _first_present(payload: Mapping[str, Any], keys: tuple[str, ...]) -> Any | None:
    """按优先级返回第一个存在的键值。"""
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _optional_array(value: Any | None) -> NumericArray | None:
    """将可选值转换为 numpy 数组。"""
    if value is None:
        return None
    return _array(value)


def from_legacy_dict(
    payload: Mapping[str, Any],
    *,
    required_modalities: Iterable[str] = (),
    require_robot_tag: bool = False,
) -> RawSample:
    """将旧式样本字典转换为 ``RawSample``。

    Args:
        payload: 旧式样本映射,支持直接 ``images`` 与扁平 ``observation.images.*`` 键。
        required_modalities: 转换后必须存在的图像模态。
        require_robot_tag: 是否要求旧样本显式提供机器人标识。

    Returns:
        满足 M1 核心契约的 ``RawSample``。

    Raises:
        ValueError: 当动作形状、语言、图像或必需模态不满足契约时抛出。
    """
    images = _collect_images(payload)
    language_value = _first_present(payload, ("language", "instruction", "task"))
    language = "" if language_value is None else str(language_value)

    actions = _optional_array(_first_present(payload, ("actions", "action")))
    state = _optional_array(_first_present(payload, ("state", "proprio", "observation.state")))

    raw_metadata = payload.get("metadata")
    metadata: dict[str, Any]
    if isinstance(raw_metadata, Mapping):
        metadata = dict(cast(Mapping[str, Any], raw_metadata))
    else:
        metadata = {}
    metadata_robot_tag = metadata.get("robot_tag")
    payload_robot_tag = payload.get("robot_tag")
    robot_value = payload_robot_tag if payload_robot_tag else metadata_robot_tag
    if not robot_value:
        if require_robot_tag:
            raise ValueError("robot_tag is required in strict legacy sample mode")
        robot_value = "unknown"
    robot_tag = str(robot_value)
    metadata["robot_tag"] = robot_tag
    if "episode_id" in payload and "episode_id" not in metadata:
        metadata["episode_id"] = payload["episode_id"]

    sample = RawSample(
        images=images,
        language=language,
        actions=actions,
        state=state,
        robot_tag=robot_tag,
        metadata=metadata,
    )
    validate_required_modalities(sample, required_modalities)
    return sample
