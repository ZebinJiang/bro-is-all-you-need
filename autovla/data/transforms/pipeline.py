"""AutoVLA 通用样本变换流水线。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from autovla.data.types import TrainingSample

SampleTransform = Callable[[TrainingSample], TrainingSample]


@dataclass(frozen=True, slots=True)
class TransformStep:
    """绑定稳定步骤名称和纯样本变换。"""

    name: str
    transform: SampleTransform

    def __post_init__(self) -> None:
        """校验步骤名和可调用对象。"""
        if not self.name.strip():
            raise ValueError("transform step name must not be empty")
        if not callable(self.transform):
            raise TypeError("transform must be callable")


class TransformPipeline:
    """按声明顺序执行框架中立样本变换。"""

    def __init__(self, steps: Sequence[TransformStep] = ()) -> None:
        """保存名称唯一的不可变步骤序列。"""
        names = tuple(step.name for step in steps)
        if len(set(names)) != len(names):
            raise ValueError("transform step names must be unique")
        self._steps = tuple(steps)

    @property
    def fingerprint(self) -> str:
        """返回只依赖步骤名和顺序的稳定指纹。"""
        payload = json.dumps([step.name for step in self._steps], separators=(",", ":")).encode(
            "utf-8"
        )
        return hashlib.sha256(payload).hexdigest()

    def __call__(self, sample: TrainingSample) -> TrainingSample:
        """串行应用全部步骤并要求每步保持规范样本类型。"""
        output = sample
        for step in self._steps:
            output = step.transform(output)
        return output


__all__ = ["SampleTransform", "TransformPipeline", "TransformStep"]
