"""解析显式、可指纹化且失败关闭的张量对齐策略。"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum

from autovla.core.semantics.axes import AxisName, TensorLayout


class AlignmentMode(str, Enum):
    """定义统计量到数据张量的所有允许对齐选择。"""

    EXACT = "exact"
    BROADCAST_MISSING_AXES = "broadcast_missing_axes"
    # 旧名称是同一枚举成员的身份别名。
    BROADCAST = "broadcast_missing_axes"
    TIME_INDEX = "time_index"
    TRUNCATE_TIME = "truncate_time"
    PAD_TIME = "pad_time"
    REPEAT_TIME = "repeat_time"
    REJECT = "reject"


@dataclass(frozen=True, slots=True)
class AlignmentPolicy:
    """保存明确对齐模式、可选时间索引和 pad 值。"""

    mode: AlignmentMode = AlignmentMode.EXACT
    time_indices: tuple[int, ...] = ()
    pad_value: float = 0.0

    def __post_init__(self) -> None:
        """拒绝模式外参数和非有限 pad 值。"""
        if not math.isfinite(self.pad_value):
            raise ValueError("alignment pad_value must be finite")
        if self.mode is AlignmentMode.TIME_INDEX:
            if not self.time_indices or any(type(index) is not int for index in self.time_indices):
                raise ValueError("time_index alignment requires explicit integer time_indices")
        elif self.time_indices:
            raise ValueError("time_indices are valid only for time_index alignment")
        if self.mode is not AlignmentMode.PAD_TIME and self.pad_value != 0.0:
            raise ValueError("non-zero pad_value is valid only for pad_time alignment")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {
            "mode": self.mode.value,
            "time_indices": list(self.time_indices),
            "pad_value": self.pad_value,
        }

    @property
    def fingerprint(self) -> str:
        """返回对齐选择的稳定指纹。"""
        encoded = json.dumps(self.to_json_dict(), sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class AlignmentPlan:
    """描述源轴置入目标轴以及确定的时间取样/pad 位置。"""

    source_layout: TensorLayout
    target_layout: TensorLayout
    source_shape: tuple[int, ...]
    target_shape: tuple[int, ...]
    reshape: tuple[int, ...]
    time_indices: tuple[int, ...] = ()
    pad_value: float = 0.0
    policy_fingerprint: str = ""


def _validate_shape(layout: TensorLayout, shape: tuple[int, ...], *, name: str) -> None:
    """校验实际形状与布局中持久化的已知尺寸。"""
    if len(shape) != layout.rank or any(size <= 0 for size in shape):
        raise ValueError(f"{name} shape must match layout rank and be positive")
    if any(
        known is not None and known != actual
        for known, actual in zip(layout.sizes, shape, strict=True)
    ):
        raise ValueError(f"{name} shape conflicts with persisted layout sizes")


def _time_indices(
    *,
    policy: AlignmentPolicy,
    source_time: int,
    target_time: int,
) -> tuple[int, ...]:
    """把时间策略解析成唯一目标到源索引, ``-1`` 表示 pad。"""
    if policy.mode is AlignmentMode.TIME_INDEX:
        indices = policy.time_indices
        if len(indices) != target_time or any(
            index < 0 or index >= source_time for index in indices
        ):
            raise ValueError("time_indices must map every target position to a valid source")
        return indices
    if policy.mode is AlignmentMode.TRUNCATE_TIME:
        if target_time > source_time:
            raise ValueError("truncate_time target cannot exceed source time")
        return tuple(range(target_time))
    if policy.mode is AlignmentMode.PAD_TIME:
        if target_time < source_time:
            raise ValueError("pad_time target cannot be shorter than source time")
        return (*range(source_time), *((-1,) * (target_time - source_time)))
    if policy.mode is AlignmentMode.REPEAT_TIME:
        return tuple(index % source_time for index in range(target_time))
    return ()


def resolve_alignment(
    *,
    source_layout: TensorLayout,
    source_shape: tuple[int, ...],
    target_layout: TensorLayout,
    target_shape: tuple[int, ...],
    policy: AlignmentPolicy,
) -> AlignmentPlan:
    """校验布局和尺寸并生成唯一对齐计划。"""
    _validate_shape(source_layout, source_shape, name="source")
    _validate_shape(target_layout, target_shape, name="target")
    if policy.mode is AlignmentMode.REJECT:
        raise ValueError("alignment policy explicitly rejects this alignment")
    if policy.mode is AlignmentMode.EXACT:
        if source_layout.axes != target_layout.axes or source_shape != target_shape:
            raise ValueError("exact alignment requires identical axes and shape")
        return AlignmentPlan(
            source_layout,
            target_layout,
            source_shape,
            target_shape,
            source_shape,
            policy_fingerprint=policy.fingerprint,
        )

    if any(axis not in target_layout.axes for axis in source_layout.axes):
        raise ValueError("source layout axes must be a subset of target layout axes")
    reshape = [1] * target_layout.rank
    temporal_mode = policy.mode in {
        AlignmentMode.TIME_INDEX,
        AlignmentMode.TRUNCATE_TIME,
        AlignmentMode.PAD_TIME,
        AlignmentMode.REPEAT_TIME,
    }
    for source_index, axis in enumerate(source_layout.axes):
        target_index = target_layout.index(axis)
        source_size = source_shape[source_index]
        target_size = target_shape[target_index]
        if axis is AxisName.TIME and temporal_mode:
            continue
        if source_size not in {1, target_size}:
            raise ValueError(f"axis {axis.value!r} cannot broadcast {source_size} to {target_size}")
        reshape[target_index] = source_size

    indices: tuple[int, ...] = ()
    if temporal_mode:
        if not source_layout.contains(AxisName.TIME) or not target_layout.contains(AxisName.TIME):
            raise ValueError("time alignment requires time in source and target layouts")
        source_time = source_shape[source_layout.index(AxisName.TIME)]
        target_time = target_shape[target_layout.index(AxisName.TIME)]
        indices = _time_indices(
            policy=policy,
            source_time=source_time,
            target_time=target_time,
        )
        reshape[target_layout.index(AxisName.TIME)] = target_time
    elif policy.mode is not AlignmentMode.BROADCAST_MISSING_AXES:
        raise ValueError("unsupported or ambiguous alignment policy")

    return AlignmentPlan(
        source_layout,
        target_layout,
        source_shape,
        target_shape,
        tuple(reshape),
        indices,
        policy.pad_value,
        policy.fingerprint,
    )


__all__ = ["AlignmentMode", "AlignmentPlan", "AlignmentPolicy", "resolve_alignment"]
