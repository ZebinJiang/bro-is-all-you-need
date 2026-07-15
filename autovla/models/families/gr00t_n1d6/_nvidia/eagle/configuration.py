# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# Licensed under the NVIDIA License; see licenses/NVIDIA-ISAAC-GROOT-N1D6.txt.
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a:
# gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/configuration_eagle3_vl.py.
"""无需 auto_map 的本地 Eagle 配置。"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import cast


@dataclass(frozen=True, slots=True)
class LocalEagleConfig:
    """保存直接构造 Qwen3 与 SigLIP2 所需的本地配置。"""

    text_config: Mapping[str, object]
    vision_config: Mapping[str, object]
    image_token_id: int
    downsample_ratio: float
    select_layer: int
    projector_hidden_size: int
    output_size: int

    def __post_init__(self) -> None:
        """校验支持的本地架构和投影尺寸。"""
        raw_text_config = cast(object, self.text_config)
        raw_vision_config = cast(object, self.vision_config)
        if not isinstance(raw_text_config, Mapping) or not isinstance(raw_vision_config, Mapping):
            raise TypeError("local Eagle text_config and vision_config must be mappings")
        text_config = cast(Mapping[str, object], raw_text_config)
        vision_config = cast(Mapping[str, object], raw_vision_config)
        if text_config.get("model_type") != "qwen3":
            raise ValueError("local Eagle requires Qwen3 text_config")
        if vision_config.get("model_type") != "siglip2_vision_model":
            raise ValueError("local Eagle requires SigLIP2 vision_config")
        if type(self.image_token_id) is not int or self.image_token_id < 0:
            raise ValueError("Eagle image_token_id must be a non-negative integer")
        if type(self.select_layer) is not int:
            raise TypeError("Eagle select_layer must be an integer")
        raw_downsample_ratio = cast(object, self.downsample_ratio)
        if isinstance(raw_downsample_ratio, bool) or not isinstance(
            raw_downsample_ratio, (int, float)
        ):
            raise ValueError("Eagle downsample_ratio must be finite and in (0, 1]")
        downsample_ratio = float(raw_downsample_ratio)
        if not math.isfinite(downsample_ratio) or not 0 < downsample_ratio <= 1:
            raise ValueError("Eagle downsample_ratio must be finite and in (0, 1]")
        if (
            type(self.projector_hidden_size) is not int
            or type(self.output_size) is not int
            or self.projector_hidden_size <= 0
            or self.output_size <= 0
        ):
            raise ValueError("projector dimensions must be positive")
        object.__setattr__(self, "text_config", MappingProxyType(dict(text_config)))
        object.__setattr__(self, "vision_config", MappingProxyType(dict(vision_config)))
        object.__setattr__(self, "downsample_ratio", downsample_ratio)
        # 在任何神经网络模块构造前关闭 metadata 类型和几何冲突。
        _visual_tokens(vision_config, downsample_ratio)

    @property
    def visual_tokens_per_image(self) -> int:
        """返回 metadata 声明或由完整图像几何验证得到的视觉 token 数。"""
        return _visual_tokens(self.vision_config, float(self.downsample_ratio))

    def with_family_image_size(self, image_size: int) -> "LocalEagleConfig":
        """在 GR00T family 边界投影图像尺寸并拒绝 metadata 冲突。"""
        if type(image_size) is not int or image_size <= 0:
            raise ValueError("family image_size must be a positive integer")
        declared = self.vision_config.get("image_size")
        if declared is not None and declared != image_size:
            raise ValueError("family image_size conflicts with Eagle vision metadata")
        vision = dict(self.vision_config)
        vision["image_size"] = image_size
        return type(self)(
            text_config=self.text_config,
            vision_config=vision,
            image_token_id=self.image_token_id,
            downsample_ratio=float(self.downsample_ratio),
            select_layer=self.select_layer,
            projector_hidden_size=self.projector_hidden_size,
            output_size=self.output_size,
        )

    @classmethod
    def from_local_json(cls, path: str | Path) -> "LocalEagleConfig":
        """从现有本地 JSON 构造配置,忽略 auto_map 而不执行其内容。"""
        resolved = Path(path).expanduser().resolve(strict=True)
        if not resolved.is_file():
            raise ValueError("Eagle config path must be a local file")
        raw_payload: object = json.loads(resolved.read_text(encoding="utf-8"))
        if not isinstance(raw_payload, dict):
            raise ValueError("Eagle config must contain a JSON object")
        payload = cast(dict[str, object], raw_payload)
        raw_text = payload.get("text_config")
        raw_vision = payload.get("vision_config")
        if not isinstance(raw_text, dict) or not isinstance(raw_vision, dict):
            raise ValueError("Eagle config lacks text_config or vision_config")
        text = cast(dict[str, object], raw_text)
        vision = cast(dict[str, object], raw_vision)
        output_size = _integer(text, "hidden_size", 2048)
        return cls(
            text_config=text,
            vision_config=vision,
            image_token_id=_integer(payload, "image_token_index", 151669),
            downsample_ratio=_number(payload, "downsample_ratio", 0.5),
            select_layer=_integer(payload, "select_layer", -1),
            projector_hidden_size=output_size,
            output_size=output_size,
        )


def _integer(payload: Mapping[str, object], key: str, default: int) -> int:
    """读取严格整数 JSON 字段。"""
    value = payload.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Eagle config field {key!r} must be an integer")
    return value


def _number(payload: Mapping[str, object], key: str, default: float) -> float:
    """读取严格有限数值 JSON 字段。"""
    value = payload.get(key, default)
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"Eagle config field {key!r} must be numeric")
    result = float(value)
    if not result == result or result in {float("inf"), float("-inf")}:
        raise ValueError(f"Eagle config field {key!r} must be finite")
    return result


def _optional_positive_integer(payload: Mapping[str, object], key: str) -> int | None:
    """读取可选严格正整数几何字段。"""
    value = payload.get(key)
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise ValueError(f"Eagle vision {key} must be a positive integer")
    return value


def _visual_tokens(vision: Mapping[str, object], downsample_ratio: float) -> int:
    """统一验证 num_patches 与可选 image/patch/downsample 几何。"""
    num_patches = _optional_positive_integer(vision, "num_patches")
    image_size = _optional_positive_integer(vision, "image_size")
    patch_size = _optional_positive_integer(vision, "patch_size")
    factor = round(1.0 / downsample_ratio)
    if factor <= 0 or not math.isclose(downsample_ratio * factor, 1.0):
        raise ValueError("Eagle downsample_ratio reciprocal must be an integer")
    if image_size is None:
        if num_patches is None:
            raise ValueError("Eagle vision metadata requires num_patches or image_size")
        return num_patches
    if patch_size is None:
        raise ValueError("Eagle vision patch_size is required with image_size")
    if image_size % patch_size:
        raise ValueError("Eagle vision image_size must be divisible by patch_size")
    patch_grid = image_size // patch_size
    if patch_grid % factor:
        raise ValueError("Eagle vision patch grid is incompatible with downsample_ratio")
    projected_grid = patch_grid // factor
    derived = projected_grid * projected_grid
    if num_patches is not None and num_patches != derived:
        raise ValueError("Eagle vision num_patches conflicts with projected image geometry")
    return derived


__all__ = ["LocalEagleConfig"]
