"""实现有序、可序列化、可逆的规范变换计划。"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Protocol

from autovla.core.semantics import TensorLayout
from autovla.core.types.training import TrainingSample

SampleTransform = Callable[[TrainingSample], TrainingSample]
FeatureMap = Mapping[str, object]


class ExecutionSide(str, Enum):
    """声明阶段属于数据侧还是模型族 processor 侧。"""

    DATA = "data"
    FAMILY_PROCESSOR = "family_processor"


@dataclass(frozen=True, slots=True)
class FeatureContract:
    """声明一个必需或产出特征及其布局约束。"""

    name: str
    layout: TensorLayout | None
    layout_rule: str = "exact"

    def to_json_dict(self) -> dict[str, object]:
        """返回紧凑 JSON 声明。"""
        if not self.name.strip() or self.layout_rule not in {"exact", "preserve", "derived"}:
            raise ValueError("feature contract requires a name and valid layout_rule")
        return {
            "name": self.name,
            "layout": None if self.layout is None else self.layout.to_json_dict(),
            "layout_rule": self.layout_rule,
        }


@dataclass(frozen=True, slots=True)
class StageDescriptor:
    """统一声明阶段的输入输出、依赖、掩码和执行所有权。"""

    required_inputs: tuple[FeatureContract, ...]
    produced_outputs: tuple[FeatureContract, ...]
    reversible: bool
    state_dependencies: tuple[str, ...] = ()
    statistics_dependencies: tuple[str, ...] = ()
    mask_behavior: tuple[str, ...] = ()
    execution_side: ExecutionSide = ExecutionSide.DATA

    def to_json_dict(self) -> dict[str, object]:
        """返回每个阶段共用的稳定声明结构。"""
        return {
            "required_inputs": [item.to_json_dict() for item in self.required_inputs],
            "produced_outputs": [item.to_json_dict() for item in self.produced_outputs],
            "reversible": self.reversible,
            "state_dependencies": list(self.state_dependencies),
            "statistics_dependencies": list(self.statistics_dependencies),
            "mask_behavior": list(self.mask_behavior),
            "execution_side": self.execution_side.value,
        }


class ReversibleTransformStage(Protocol):
    """定义规范计划中可序列化的双向阶段。"""

    @property
    def name(self) -> str:
        """返回稳定阶段名。"""
        ...

    @property
    def descriptor(self) -> StageDescriptor:
        """返回统一阶段契约声明。"""
        ...

    def forward(self, features: FeatureMap) -> dict[str, object]:
        """执行正向变换。"""
        ...

    def inverse(self, features: FeatureMap) -> dict[str, object]:
        """执行逆向变换。"""
        ...

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 计划项。"""
        ...


@dataclass(frozen=True, slots=True)
class TransformStep:
    """兼容旧 callable 流水线的稳定步骤。"""

    name: str
    transform: SampleTransform

    def __post_init__(self) -> None:
        """校验步骤名和可调用对象。"""
        if not self.name.strip() or not callable(self.transform):
            raise ValueError("transform step requires a non-empty name and callable")


class TransformPipeline:
    """兼容旧 TrainingSample callable 流水线。"""

    def __init__(self, steps: Sequence[TransformStep] = ()) -> None:
        """保存名称唯一的不可变步骤序列。"""
        names = tuple(step.name for step in steps)
        if len(set(names)) != len(names):
            raise ValueError("transform step names must be unique")
        self._steps = tuple(steps)

    @property
    def fingerprint(self) -> str:
        """返回旧步骤名和顺序的稳定兼容指纹。"""
        payload = json.dumps([step.name for step in self._steps], separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def __call__(self, sample: TrainingSample) -> TrainingSample:
        """串行应用旧步骤并保持规范样本类型。"""
        output = sample
        for step in self._steps:
            output = step.transform(output)
        return output


class TransformPlan:
    """按声明顺序执行类型化阶段, 并按逆序执行逆变换。"""

    schema_version = "autovla.transform_plan.v2"

    def __init__(self, stages: Sequence[ReversibleTransformStage] = ()) -> None:
        """冻结阶段并拒绝重复阶段身份。"""
        names = tuple(stage.name for stage in stages)
        if any(not name.strip() for name in names):
            raise ValueError("transform stage names must not be empty")
        self._stages = tuple(stages)

    @property
    def stages(self) -> tuple[ReversibleTransformStage, ...]:
        """返回不可变阶段序列。"""
        return self._stages

    def to_json_dict(self) -> dict[str, object]:
        """返回含顺序、类型、参数和实现版本的计划。"""
        return {
            "schema_version": self.schema_version,
            "stages": [stage.to_json_dict() for stage in self._stages],
        }

    @property
    def fingerprint(self) -> str:
        """返回参数敏感且顺序敏感的稳定 SHA256。"""
        encoded = json.dumps(
            self.to_json_dict(), sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def forward(self, features: FeatureMap) -> Mapping[str, object]:
        """按声明顺序执行并返回独立只读顶层映射。"""
        output: FeatureMap = dict(features)
        for stage in self._stages:
            output = stage.forward(output)
        return MappingProxyType(dict(output))

    def inverse(self, features: FeatureMap) -> Mapping[str, object]:
        """按反序执行逆变换并返回独立只读顶层映射。"""
        output: FeatureMap = dict(features)
        for stage in reversed(self._stages):
            output = stage.inverse(output)
        return MappingProxyType(dict(output))


__all__ = [
    "ExecutionSide",
    "FeatureContract",
    "FeatureMap",
    "ReversibleTransformStage",
    "SampleTransform",
    "StageDescriptor",
    "TransformPipeline",
    "TransformPlan",
    "TransformStep",
]
