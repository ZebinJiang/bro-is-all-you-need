"""定义后端无关的显式张量轴和布局。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Mapping, Sequence, cast


class AxisName(str, Enum):
    """列出 AutoVLA 公共契约中可出现的语义轴。"""

    BATCH = "batch"
    TIME = "time"
    FEATURE = "feature"
    ACTION = "action"
    STATE = "state"
    CAMERA = "camera"
    FRAME = "frame"
    HEIGHT = "height"
    WIDTH = "width"
    CHANNEL = "channel"
    STATISTIC = "statistic"
    TOKEN = "token"
    EMBODIMENT = "embodiment"


@dataclass(frozen=True, slots=True)
class TensorLayout:
    """保存不可变的有序轴; 秩只由显式轴序列决定。"""

    axes: tuple[AxisName, ...]
    sizes: tuple[int | None, ...]

    def __init__(
        self,
        axes: Iterable[AxisName | str] = (),
        sizes: Iterable[int | None] | None = None,
    ) -> None:
        """从显式轴名构造布局, 不根据数组秩猜测含义。"""
        converted = tuple(AxisName(axis) for axis in axes)
        if len(set(converted)) != len(converted):
            raise ValueError("tensor layout axes must be unique")
        converted_sizes = (None,) * len(converted) if sizes is None else tuple(sizes)
        if len(converted_sizes) != len(converted):
            raise ValueError("tensor layout sizes must match axes")
        if any(
            size is not None and (type(size) is not int or size <= 0) for size in converted_sizes
        ):
            raise ValueError("known tensor layout sizes must be positive integers")
        object.__setattr__(self, "axes", converted)
        object.__setattr__(self, "sizes", converted_sizes)

    @property
    def rank(self) -> int:
        """返回布局秩。"""
        return len(self.axes)

    def index(self, axis: AxisName | str) -> int:
        """返回指定语义轴的位置。"""
        return self.axes.index(AxisName(axis))

    def contains(self, axis: AxisName | str) -> bool:
        """判断布局是否包含指定语义轴。"""
        return AxisName(axis) in self.axes

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 表示。"""
        return {"axes": [axis.value for axis in self.axes], "sizes": list(self.sizes)}

    @classmethod
    def from_json_dict(cls, payload: Mapping[str, object]) -> "TensorLayout":
        """从严格 JSON 映射恢复布局。"""
        if set(payload) not in ({"axes"}, {"axes", "sizes"}):
            raise ValueError("tensor layout fields mismatch")
        raw_axes = payload["axes"]
        if not isinstance(raw_axes, (list, tuple)):
            raise TypeError("tensor layout axes must be a JSON string array")
        axis_values = cast(Sequence[object], raw_axes)
        if not all(isinstance(axis, str) for axis in axis_values):
            raise TypeError("tensor layout axes must be a JSON string array")
        raw_sizes = payload.get("sizes")
        if raw_sizes is not None and not isinstance(raw_sizes, (list, tuple)):
            raise TypeError("tensor layout sizes must be a JSON array")
        axes = cast(Sequence[str], raw_axes)
        sizes = None if raw_sizes is None else cast(Sequence[int | None], raw_sizes)
        return cls(axes, sizes)

    def with_sizes(self, sizes: Iterable[int]) -> "TensorLayout":
        """绑定已知尺寸, 并拒绝与已有尺寸冲突。"""
        concrete = tuple(sizes)
        if len(concrete) != self.rank:
            raise ValueError("concrete sizes must match tensor layout rank")
        if any(
            known is not None and known != actual
            for known, actual in zip(self.sizes, concrete, strict=True)
        ):
            raise ValueError("concrete shape conflicts with persisted tensor layout sizes")
        return TensorLayout(self.axes, concrete)

    @classmethod
    def scalar(cls) -> "TensorLayout":
        """返回标量布局。"""
        return cls(())

    @classmethod
    def feature(cls, size: int | None = None) -> "TensorLayout":
        """返回 ``[D]`` 特征布局。"""
        return cls((AxisName.FEATURE,), (size,))

    @classmethod
    def time(cls, size: int | None = None) -> "TensorLayout":
        """返回 ``[T]`` 时间布局。"""
        return cls((AxisName.TIME,), (size,))

    @classmethod
    def time_feature(
        cls, time_size: int | None = None, feature_size: int | None = None
    ) -> "TensorLayout":
        """返回 ``[T,D]`` 时间特征布局。"""
        return cls((AxisName.TIME, AxisName.FEATURE), (time_size, feature_size))


__all__ = ["AxisName", "TensorLayout"]
