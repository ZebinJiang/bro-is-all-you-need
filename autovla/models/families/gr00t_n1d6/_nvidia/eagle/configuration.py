# Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# Licensed under the NVIDIA License; see licenses/NVIDIA-ISAAC-GROOT-N1D6.txt.
# Adapted from NVIDIA/Isaac-GR00T@5dc80c4a:
# gr00t/model/modules/nvidia/Eagle-Block2A-2B-v2/configuration_eagle3_vl.py.
"""无需 auto_map 的本地 Eagle 配置。"""

from __future__ import annotations

import json
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
        if self.text_config.get("model_type") != "qwen3":
            raise ValueError("local Eagle requires Qwen3 text_config")
        if self.vision_config.get("model_type") != "siglip2_vision_model":
            raise ValueError("local Eagle requires SigLIP2 vision_config")
        if self.image_token_id < 0 or not 0 < self.downsample_ratio <= 1:
            raise ValueError("invalid image token or downsample ratio")
        if self.projector_hidden_size <= 0 or self.output_size <= 0:
            raise ValueError("projector dimensions must be positive")
        object.__setattr__(self, "text_config", MappingProxyType(dict(self.text_config)))
        object.__setattr__(self, "vision_config", MappingProxyType(dict(self.vision_config)))

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


__all__ = ["LocalEagleConfig"]
