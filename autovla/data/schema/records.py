"""后端无关的数据记录、时间窗和能力契约。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import NewType

from autovla.core.semantics import TensorLayout

EpisodeId = NewType("EpisodeId", str)
SampleId = NewType("SampleId", str)
FrameIndex = NewType("FrameIndex", int)
Timestamp = NewType("Timestamp", float)


class FeatureRole(str, Enum):
    """声明 feature 在 VLA 数据流中的语义角色。"""

    IMAGE = "image"
    LANGUAGE = "language"
    STATE = "state"
    ACTION = "action"
    ACTION_MASK = "action_mask"
    TIMESTAMP = "timestamp"
    METADATA = "metadata"


def _is_feature_role(value: object) -> bool:
    """在解码边界校验 feature role 枚举。"""
    return isinstance(value, FeatureRole)


def _is_number(value: object) -> bool:
    """拒绝 bool,并接受整数或浮点时间值。"""
    return not isinstance(value, bool) and isinstance(value, (int, float))


def _is_finite_timestamp(value: object) -> bool:
    """校验未信任时间值为非 bool 的有限数。"""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value)


@dataclass(frozen=True, slots=True)
class FeatureLayout:
    """绑定显式轴布局和 dtype, 不从数组秩猜测含义。"""

    tensor: TensorLayout
    dtype: str

    def __post_init__(self) -> None:
        """校验 dtype 文本。"""
        if not self.dtype.strip():
            raise ValueError("feature dtype must not be empty")


@dataclass(frozen=True, slots=True)
class FeatureSpec:
    """描述一个命名 feature 的角色、布局和必要性。"""

    name: str
    role: FeatureRole
    layout: FeatureLayout
    required: bool = True

    def __post_init__(self) -> None:
        """校验稳定名称和枚举类型。"""
        if not self.name.strip():
            raise ValueError("feature name must not be empty")
        if not _is_feature_role(self.role):
            raise TypeError("feature role must be FeatureRole")
        if type(self.required) is not bool:
            raise TypeError("feature required must be bool")


@dataclass(frozen=True, slots=True)
class EpisodeMetadata:
    """保存 episode 的逻辑身份、帧范围和任务标签。"""

    episode_id: EpisodeId
    frame_count: int
    start_timestamp: Timestamp
    end_timestamp: Timestamp
    tasks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """校验帧数、时间范围和任务标签。"""
        if not str(self.episode_id).strip():
            raise ValueError("episode_id must not be empty")
        if type(self.frame_count) is not int or self.frame_count <= 0:
            raise ValueError("frame_count must be positive")
        if any(not _is_number(value) for value in (self.start_timestamp, self.end_timestamp)):
            raise TypeError("episode timestamps must be numbers")
        if not math.isfinite(self.start_timestamp) or not math.isfinite(self.end_timestamp):
            raise ValueError("episode timestamps must be finite")
        if self.end_timestamp < self.start_timestamp:
            raise ValueError("episode timestamp range is reversed")
        if any(not task.strip() for task in self.tasks):
            raise ValueError("episode tasks must not be empty")


class TemporalPaddingPolicy(str, Enum):
    """声明越过 episode 边界时的确定行为。"""

    PAD = "pad"
    CLIP = "clip"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class TemporalWindow:
    """保存解析后的物理帧和独立 temporal-valid mask。"""

    sample_ids: tuple[SampleId, ...]
    frame_indices: tuple[FrameIndex, ...]
    timestamps: tuple[Timestamp, ...]
    valid: tuple[bool, ...]
    padding_policy: TemporalPaddingPolicy

    def __post_init__(self) -> None:
        """校验所有时间窗向量等长且非空。"""
        size = len(self.sample_ids)
        if size == 0 or any(
            len(values) != size for values in (self.frame_indices, self.timestamps, self.valid)
        ):
            raise ValueError("temporal window fields must have one equal non-zero length")
        if any(type(index) is not int or index < 0 for index in self.frame_indices):
            raise ValueError("frame indices must be non-negative")
        if any(not _is_finite_timestamp(value) for value in self.timestamps):
            raise ValueError("temporal timestamps must be finite")
        if any(type(value) is not bool for value in self.valid):
            raise TypeError("temporal valid values must be bool")


@dataclass(frozen=True, slots=True)
class DataSourceCapabilities:
    """完整描述一个已解析数据源可提供的能力。"""

    finite_map_access: bool
    streaming_access: bool
    random_access: bool
    episode_metadata: bool
    temporal_queries: bool
    local_media_decode: bool
    deterministic_sharding: bool
    resume_mode: str
    statistics_metadata: bool
    batched_reads: bool

    def __post_init__(self) -> None:
        """限制恢复能力为明确的封闭集合。"""
        for name in (
            "finite_map_access",
            "streaming_access",
            "random_access",
            "episode_metadata",
            "temporal_queries",
            "local_media_decode",
            "deterministic_sharding",
            "statistics_metadata",
            "batched_reads",
        ):
            if type(getattr(self, name)) is not bool:
                raise TypeError(f"{name} must be bool")
        if self.resume_mode not in {"none", "replay", "exact"}:
            raise ValueError("resume_mode must be none, replay, or exact")

    @property
    def fingerprint(self) -> str:
        """返回稳定能力身份。"""
        payload = {name: getattr(self, name) for name in self.__dataclass_fields__}
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()
