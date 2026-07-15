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
    def stage_id(self) -> str:
        """返回稳定阶段实例身份。"""
        ...

    @property
    def name(self) -> str:
        """返回稳定阶段类型名。"""
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

    schema_version = "autovla.transform_plan.v3"

    def __init__(self, stages: Sequence[ReversibleTransformStage] = ()) -> None:
        """冻结阶段并拒绝重复阶段身份。"""
        names = tuple(stage.name for stage in stages)
        stage_ids = tuple(stage.stage_id for stage in stages)
        if any(not name.strip() for name in names):
            raise ValueError("transform stage names must not be empty")
        if any(not stage_id.strip() for stage_id in stage_ids):
            raise ValueError("transform stage identifiers must not be empty")
        if len(set(stage_ids)) != len(stage_ids):
            raise ValueError("transform stage identifiers must be unique")
        self._stages = tuple(stages)
        self._validate_graph()

    @property
    def stages(self) -> tuple[ReversibleTransformStage, ...]:
        """返回不可变阶段序列。"""
        return self._stages

    def to_json_dict(self) -> dict[str, object]:
        """返回含顺序、类型、参数和实现版本的计划。"""
        serialized: list[dict[str, object]] = []
        for order, stage in enumerate(self._stages):
            item = dict(stage.to_json_dict())
            if item.get("name") != stage.name:
                raise ValueError("transform stage serialization must preserve its type name")
            if item.get("stage_id") != stage.stage_id:
                raise ValueError(
                    "transform stage serialization must preserve its instance identity"
                )
            item["order"] = order
            serialized.append(item)
        return {
            "schema_version": self.schema_version,
            "stages": serialized,
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
        blocked = tuple(stage.stage_id for stage in self._stages if not stage.descriptor.reversible)
        if blocked:
            raise ValueError(f"transform plan is not inverse-eligible: {blocked}")
        output: FeatureMap = dict(features)
        for stage in reversed(self._stages):
            output = stage.inverse(output)
        return MappingProxyType(dict(output))

    def _validate_graph(self) -> None:
        """校验语义键顺序、覆盖、布局及 mask/统计依赖声明。"""

        produced_layouts: dict[str, FeatureContract] = {}
        first_producer: dict[str, int] = {}
        for index, stage in enumerate(self._stages):
            for contract in stage.descriptor.produced_outputs:
                first_producer.setdefault(contract.name, index)
        for index, stage in enumerate(self._stages):
            descriptor = stage.descriptor
            required_names = tuple(item.name for item in descriptor.required_inputs)
            produced_names = tuple(item.name for item in descriptor.produced_outputs)
            if len(set(required_names)) != len(required_names):
                raise ValueError(f"stage {stage.stage_id!r} has duplicate required semantic keys")
            if len(set(produced_names)) != len(produced_names):
                raise ValueError(f"stage {stage.stage_id!r} has duplicate produced semantic keys")
            for dependency in (
                descriptor.state_dependencies
                + descriptor.statistics_dependencies
                + descriptor.mask_behavior
            ):
                if not dependency.strip():
                    raise ValueError(f"stage {stage.stage_id!r} has an empty dependency identity")
            for contract in descriptor.required_inputs:
                contract.to_json_dict()
                producer = first_producer.get(contract.name)
                if producer is not None and producer > index:
                    raise ValueError(
                        f"stage {stage.stage_id!r} requires {contract.name!r} before it is produced"
                    )
                previous = produced_layouts.get(contract.name)
                if previous is not None:
                    _validate_layout_edge(previous, contract, stage.stage_id)
            for contract in descriptor.produced_outputs:
                contract.to_json_dict()
                if contract.name in produced_layouts and contract.name not in required_names:
                    raise ValueError(
                        f"stage {stage.stage_id!r} collides with output {contract.name!r} "
                        "without consuming it"
                    )
                produced_layouts[contract.name] = contract


def _validate_layout_edge(
    produced: FeatureContract,
    required: FeatureContract,
    stage_name: str,
) -> None:
    """拒绝相邻语义键的轴和已知尺寸不兼容。"""

    if produced.layout is None or required.layout is None:
        return
    if produced.layout.axes != required.layout.axes:
        raise ValueError(f"stage {stage_name!r} has incompatible semantic-key axes")
    for produced_size, required_size in zip(
        produced.layout.sizes, required.layout.sizes, strict=True
    ):
        if (
            produced_size is not None
            and required_size is not None
            and produced_size != required_size
        ):
            raise ValueError(f"stage {stage_name!r} has incompatible semantic-key sizes")


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
