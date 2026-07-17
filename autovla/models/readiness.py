"""模型族运行就绪度的正交、证据驱动契约。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping

from autovla.models.families.specification import ModelFamilyDefinition


class DefinitionReadiness(str, Enum):
    """描述定义与可执行源码的完成度。"""

    ABSENT = "absent"
    ARCHITECTURE_DEFINED = "architecture_defined"
    EXECUTABLE_SOURCE_COMPLETE = "executable_source_complete"


class AssetReadiness(str, Enum):
    """描述本地资产清单和完整包的验证度。"""

    UNRESOLVED = "unresolved"
    MANIFEST_VERIFIED = "manifest_verified"
    COMPLETE_LOCAL_BUNDLE = "complete_local_bundle"


class CheckpointReadiness(str, Enum):
    """描述 checkpoint 映射、严格加载和恢复验证度。"""

    UNRESOLVED = "unresolved"
    MAPPED = "mapped"
    STRICT_LOADED = "strict_loaded"
    RESUME_VALIDATED = "resume_validated"


class ConstructionReadiness(str, Enum):
    """描述源码构造和 CUDA 构造验证度。"""

    UNAVAILABLE = "unavailable"
    SOURCE_CONSTRUCTIBLE = "source_constructible"
    CUDA_CONSTRUCTED = "cuda_constructed"


class ForwardReadiness(str, Enum):
    """描述契约批次和真实数据前向验证度。"""

    UNVALIDATED = "unvalidated"
    CONTRACT_BATCH_VALIDATED = "contract_batch_validated"
    REAL_DATA_VALIDATED = "real_data_validated"


class TrainingReadiness(str, Enum):
    """描述反向、优化器和断点恢复验证度。"""

    UNVALIDATED = "unvalidated"
    BACKWARD_VALIDATED = "backward_validated"
    OPTIMIZER_VALIDATED = "optimizer_validated"
    CHECKPOINT_RESUME_VALIDATED = "checkpoint_resume_validated"


class PredictionReadiness(str, Enum):
    """描述确定性输入和物理动作解码验证度。"""

    UNVALIDATED = "unvalidated"
    DETERMINISTIC_INPUT_VALIDATED = "deterministic_input_validated"
    DECODED_ACTION_VALIDATED = "decoded_action_validated"


class DataBindingReadiness(str, Enum):
    """描述模型与数据语义绑定的精确程度。"""

    NONE = "none"
    CONTRACT_FIXTURE_ONLY = "contract_fixture_only"
    EXPLICIT_PROJECTION = "explicit_projection"
    EXACT_REAL_DATASET = "exact_real_dataset"


class DistributedReadiness(str, Enum):
    """描述分布式后端与跨节点验证度。"""

    UNVALIDATED = "unvalidated"
    DDP_VALIDATED = "ddp_validated"
    ZERO1_VALIDATED = "zero1_validated"
    ZERO2_VALIDATED = "zero2_validated"
    ZERO3_VALIDATED = "zero3_validated"
    CROSS_NODE_VALIDATED = "cross_node_validated"


class ReadinessAxis(str, Enum):
    """列出可由证据收据提升的就绪轴。"""

    DEFINITION = "definition"
    ASSETS = "assets"
    CHECKPOINT = "checkpoint"
    CONSTRUCTION = "construction"
    FORWARD = "forward"
    TRAINING = "training"
    PREDICTION = "prediction"
    DATA_BINDING = "data_binding"
    DISTRIBUTED = "distributed"


class EvidenceValidationKind(str, Enum):
    """区分源码、静态工件和真实运行证据。"""

    SOURCE = "source"
    STATIC = "static"
    RUNTIME = "runtime"


ReadinessValue = (
    DefinitionReadiness
    | AssetReadiness
    | CheckpointReadiness
    | ConstructionReadiness
    | ForwardReadiness
    | TrainingReadiness
    | PredictionReadiness
    | DataBindingReadiness
    | DistributedReadiness
)


_AXIS_TYPES: Mapping[ReadinessAxis, type[Enum]] = MappingProxyType(
    {
        ReadinessAxis.DEFINITION: DefinitionReadiness,
        ReadinessAxis.ASSETS: AssetReadiness,
        ReadinessAxis.CHECKPOINT: CheckpointReadiness,
        ReadinessAxis.CONSTRUCTION: ConstructionReadiness,
        ReadinessAxis.FORWARD: ForwardReadiness,
        ReadinessAxis.TRAINING: TrainingReadiness,
        ReadinessAxis.PREDICTION: PredictionReadiness,
        ReadinessAxis.DATA_BINDING: DataBindingReadiness,
        ReadinessAxis.DISTRIBUTED: DistributedReadiness,
    }
)

_DEFAULTS: Mapping[ReadinessAxis, ReadinessValue] = MappingProxyType(
    {
        ReadinessAxis.DEFINITION: DefinitionReadiness.ARCHITECTURE_DEFINED,
        ReadinessAxis.ASSETS: AssetReadiness.UNRESOLVED,
        ReadinessAxis.CHECKPOINT: CheckpointReadiness.UNRESOLVED,
        ReadinessAxis.CONSTRUCTION: ConstructionReadiness.UNAVAILABLE,
        ReadinessAxis.FORWARD: ForwardReadiness.UNVALIDATED,
        ReadinessAxis.TRAINING: TrainingReadiness.UNVALIDATED,
        ReadinessAxis.PREDICTION: PredictionReadiness.UNVALIDATED,
        ReadinessAxis.DATA_BINDING: DataBindingReadiness.NONE,
        ReadinessAxis.DISTRIBUTED: DistributedReadiness.UNVALIDATED,
    }
)

_MINIMUM_VALIDATION: Mapping[tuple[ReadinessAxis, str], EvidenceValidationKind] = MappingProxyType(
    {
        (
            ReadinessAxis.DEFINITION,
            DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE.value,
        ): EvidenceValidationKind.SOURCE,
        (
            ReadinessAxis.ASSETS,
            AssetReadiness.MANIFEST_VERIFIED.value,
        ): EvidenceValidationKind.STATIC,
        (
            ReadinessAxis.ASSETS,
            AssetReadiness.COMPLETE_LOCAL_BUNDLE.value,
        ): EvidenceValidationKind.STATIC,
        (ReadinessAxis.CHECKPOINT, CheckpointReadiness.MAPPED.value): EvidenceValidationKind.STATIC,
        (
            ReadinessAxis.CHECKPOINT,
            CheckpointReadiness.STRICT_LOADED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.CHECKPOINT,
            CheckpointReadiness.RESUME_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.CONSTRUCTION,
            ConstructionReadiness.SOURCE_CONSTRUCTIBLE.value,
        ): EvidenceValidationKind.SOURCE,
        (
            ReadinessAxis.CONSTRUCTION,
            ConstructionReadiness.CUDA_CONSTRUCTED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.FORWARD,
            ForwardReadiness.CONTRACT_BATCH_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.FORWARD,
            ForwardReadiness.REAL_DATA_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.TRAINING,
            TrainingReadiness.BACKWARD_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.TRAINING,
            TrainingReadiness.OPTIMIZER_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.TRAINING,
            TrainingReadiness.CHECKPOINT_RESUME_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.PREDICTION,
            PredictionReadiness.DETERMINISTIC_INPUT_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.PREDICTION,
            PredictionReadiness.DECODED_ACTION_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.DATA_BINDING,
            DataBindingReadiness.CONTRACT_FIXTURE_ONLY.value,
        ): EvidenceValidationKind.STATIC,
        (
            ReadinessAxis.DATA_BINDING,
            DataBindingReadiness.EXPLICIT_PROJECTION.value,
        ): EvidenceValidationKind.STATIC,
        (
            ReadinessAxis.DATA_BINDING,
            DataBindingReadiness.EXACT_REAL_DATASET.value,
        ): EvidenceValidationKind.STATIC,
        (
            ReadinessAxis.DISTRIBUTED,
            DistributedReadiness.DDP_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.DISTRIBUTED,
            DistributedReadiness.ZERO1_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.DISTRIBUTED,
            DistributedReadiness.ZERO2_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.DISTRIBUTED,
            DistributedReadiness.ZERO3_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
        (
            ReadinessAxis.DISTRIBUTED,
            DistributedReadiness.CROSS_NODE_VALIDATED.value,
        ): EvidenceValidationKind.RUNTIME,
    }
)


def _require_sha256(value: str, field_name: str) -> None:
    """校验小写 SHA256 身份。"""

    if len(value) != 64 or any(character not in "0123456789abcdef" for character in value):
        raise ValueError(f"{field_name} must be a lowercase SHA256 fingerprint")


@dataclass(frozen=True, slots=True)
class ReadinessEvidenceReceipt:
    """记录一条明确、可复核且不从配置字符串推断的证据。"""

    evidence_id: str
    family_key: str
    definition_fingerprint: str
    axis: ReadinessAxis
    state: ReadinessValue
    validation_kind: EvidenceValidationKind
    artifact_fingerprint: str

    def __post_init__(self) -> None:
        """拒绝错轴状态、默认状态和身份不完整的收据。"""

        if not self.evidence_id.strip() or not self.family_key.strip():
            raise ValueError("evidence_id and family_key must not be empty")
        _require_sha256(self.definition_fingerprint, "definition_fingerprint")
        _require_sha256(self.artifact_fingerprint, "artifact_fingerprint")
        if type(self.axis) is not ReadinessAxis:
            raise TypeError("axis must use ReadinessAxis")
        expected_type = _AXIS_TYPES[self.axis]
        if type(self.state) is not expected_type:
            raise TypeError("receipt state type must match its readiness axis")
        if self.state == _DEFAULTS[self.axis]:
            raise ValueError("evidence receipts may only promote a readiness axis")
        if type(self.validation_kind) is not EvidenceValidationKind:
            raise TypeError("validation_kind must use EvidenceValidationKind")
        required = _MINIMUM_VALIDATION[(self.axis, self.state.value)]
        if self.validation_kind is not required:
            raise ValueError(
                f"{self.axis.value}={self.state.value} requires {required.value} evidence"
            )

    def to_json_dict(self) -> dict[str, str]:
        """返回用于稳定序列化的收据载荷。"""

        return {
            "artifact_fingerprint": self.artifact_fingerprint,
            "axis": self.axis.value,
            "definition_fingerprint": self.definition_fingerprint,
            "evidence_id": self.evidence_id,
            "family_key": self.family_key,
            "state": self.state.value,
            "validation_kind": self.validation_kind.value,
        }


@dataclass(frozen=True, slots=True)
class ReadinessValidationState:
    """分别保存源码、静态和运行证据身份,避免相互冒充。"""

    source: tuple[str, ...] = ()
    static: tuple[str, ...] = ()
    runtime: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        """要求每组证据稳定、有序且全局唯一。"""

        combined = self.source + self.static + self.runtime
        for values in (self.source, self.static, self.runtime):
            if values != tuple(sorted(values)) or any(not value.strip() for value in values):
                raise ValueError("validation evidence ids must be non-empty and sorted")
        if len(set(combined)) != len(combined):
            raise ValueError("validation evidence ids must be globally unique")

    def to_json_dict(self) -> dict[str, list[str]]:
        """返回按证据种类分离的稳定载荷。"""

        return {
            "runtime": list(self.runtime),
            "source": list(self.source),
            "static": list(self.static),
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyReadiness:
    """保存一个模型族由定义与显式收据导出的不可变就绪快照。"""

    family_key: str
    family_definition: ModelFamilyDefinition | None
    definition: DefinitionReadiness
    assets: AssetReadiness
    checkpoint: CheckpointReadiness
    construction: ConstructionReadiness
    forward: ForwardReadiness
    training: TrainingReadiness
    prediction: PredictionReadiness
    data_binding: DataBindingReadiness
    distributed: DistributedReadiness
    validation: ReadinessValidationState
    receipts: tuple[ReadinessEvidenceReceipt, ...]

    def __post_init__(self) -> None:
        """验证快照类型、收据排序和必要的跨轴先决条件。"""

        if not self.family_key.strip() or self.family_key != self.family_key.strip():
            raise ValueError("family_key must be canonical non-empty text")
        if self.family_definition is not None and not isinstance(
            self.family_definition, ModelFamilyDefinition
        ):
            raise TypeError("family_definition must be ModelFamilyDefinition or None")
        expected_types = {
            "definition": DefinitionReadiness,
            "assets": AssetReadiness,
            "checkpoint": CheckpointReadiness,
            "construction": ConstructionReadiness,
            "forward": ForwardReadiness,
            "training": TrainingReadiness,
            "prediction": PredictionReadiness,
            "data_binding": DataBindingReadiness,
            "distributed": DistributedReadiness,
        }
        if any(
            type(getattr(self, name)) is not expected for name, expected in expected_types.items()
        ):
            raise TypeError("readiness axes must use their exact enum types")
        if type(self.validation) is not ReadinessValidationState:
            raise TypeError("validation must be ReadinessValidationState")
        if type(self.receipts) is not tuple or any(
            type(receipt) is not ReadinessEvidenceReceipt for receipt in self.receipts
        ):
            raise TypeError("receipts must be a tuple of ReadinessEvidenceReceipt")
        identities = tuple(receipt.evidence_id for receipt in self.receipts)
        if identities != tuple(sorted(identities)) or len(set(identities)) != len(identities):
            raise ValueError("readiness receipts must be uniquely sorted by evidence_id")
        if self.family_definition is None:
            if self.definition is not DefinitionReadiness.ABSENT:
                raise ValueError("missing family definition requires definition=absent")
            if self.receipts or any(
                getattr(self, axis.value) != baseline
                for axis, baseline in _DEFAULTS.items()
                if axis is not ReadinessAxis.DEFINITION
            ):
                raise ValueError("absent family definition cannot carry promoted readiness")
            if self.validation != ReadinessValidationState():
                raise ValueError("absent family definition cannot carry validation evidence")
            return
        if self.family_definition.family_key != self.family_key:
            raise ValueError("family definition key does not match readiness family_key")
        if self.definition is DefinitionReadiness.ABSENT:
            raise ValueError("present family definition cannot use definition=absent")
        projected = dict(_DEFAULTS)
        projected_ids: dict[EvidenceValidationKind, list[str]] = {
            kind: [] for kind in EvidenceValidationKind
        }
        seen_axes: set[ReadinessAxis] = set()
        for receipt in self.receipts:
            if receipt.family_key != self.family_key:
                raise ValueError("receipt family_key does not match readiness")
            if receipt.definition_fingerprint != self.family_definition.fingerprint:
                raise ValueError("receipt definition fingerprint does not match readiness")
            if receipt.axis in seen_axes:
                raise ValueError("each readiness axis accepts exactly one promotion receipt")
            seen_axes.add(receipt.axis)
            projected[receipt.axis] = receipt.state
            projected_ids[receipt.validation_kind].append(receipt.evidence_id)
        for axis, expected in projected.items():
            if getattr(self, axis.value) is not expected:
                raise ValueError(f"{axis.value} readiness is not derived from supplied receipts")
        expected_validation = ReadinessValidationState(
            source=tuple(sorted(projected_ids[EvidenceValidationKind.SOURCE])),
            static=tuple(sorted(projected_ids[EvidenceValidationKind.STATIC])),
            runtime=tuple(sorted(projected_ids[EvidenceValidationKind.RUNTIME])),
        )
        if self.validation != expected_validation:
            raise ValueError("validation state is not derived from supplied receipts")
        if self.definition is not DefinitionReadiness.EXECUTABLE_SOURCE_COMPLETE and (
            self.construction is not ConstructionReadiness.UNAVAILABLE
            or self.checkpoint is not CheckpointReadiness.UNRESOLVED
        ):
            raise ValueError("construction and checkpoint readiness require executable source")
        if self.construction is ConstructionReadiness.UNAVAILABLE and any(
            value != baseline
            for value, baseline in (
                (self.forward, ForwardReadiness.UNVALIDATED),
                (self.training, TrainingReadiness.UNVALIDATED),
                (self.prediction, PredictionReadiness.UNVALIDATED),
                (self.distributed, DistributedReadiness.UNVALIDATED),
            )
        ):
            raise ValueError("runtime validation requires a constructible model")
        if self.training is TrainingReadiness.CHECKPOINT_RESUME_VALIDATED and (
            self.checkpoint is not CheckpointReadiness.RESUME_VALIDATED
        ):
            raise ValueError("training checkpoint resume requires checkpoint resume evidence")
        if self.forward is ForwardReadiness.REAL_DATA_VALIDATED and (
            self.data_binding is DataBindingReadiness.NONE
            or self.data_binding is DataBindingReadiness.CONTRACT_FIXTURE_ONLY
        ):
            raise ValueError("real-data forward requires an explicit or exact data binding")

    @classmethod
    def absent(cls, family_key: str) -> ModelFamilyReadiness:
        """构造无规范定义时的全关闭就绪快照。"""

        return cls(
            family_key=family_key,
            family_definition=None,
            definition=DefinitionReadiness.ABSENT,
            assets=AssetReadiness.UNRESOLVED,
            checkpoint=CheckpointReadiness.UNRESOLVED,
            construction=ConstructionReadiness.UNAVAILABLE,
            forward=ForwardReadiness.UNVALIDATED,
            training=TrainingReadiness.UNVALIDATED,
            prediction=PredictionReadiness.UNVALIDATED,
            data_binding=DataBindingReadiness.NONE,
            distributed=DistributedReadiness.UNVALIDATED,
            validation=ReadinessValidationState(),
            receipts=(),
        )

    @classmethod
    def derive(
        cls,
        definition: ModelFamilyDefinition,
        receipts: Iterable[ReadinessEvidenceReceipt] = (),
    ) -> ModelFamilyReadiness:
        """仅从规范定义和显式证据收据导出就绪快照。"""

        if not isinstance(definition, ModelFamilyDefinition):
            raise TypeError("definition must be ModelFamilyDefinition")
        ordered = tuple(sorted(receipts, key=lambda item: item.evidence_id))
        states = dict(_DEFAULTS)
        evidence_by_kind: dict[EvidenceValidationKind, list[str]] = {
            kind: [] for kind in EvidenceValidationKind
        }
        seen_axes: set[ReadinessAxis] = set()
        seen_evidence_ids: set[str] = set()
        for receipt in ordered:
            if type(receipt) is not ReadinessEvidenceReceipt:
                raise TypeError("receipts must contain ReadinessEvidenceReceipt")
            if receipt.evidence_id in seen_evidence_ids:
                raise ValueError("evidence_id must be unique")
            seen_evidence_ids.add(receipt.evidence_id)
            if receipt.family_key != definition.family_key:
                raise ValueError("receipt family_key does not match definition")
            if receipt.definition_fingerprint != definition.fingerprint:
                raise ValueError("receipt definition fingerprint does not match definition")
            if receipt.axis in seen_axes:
                raise ValueError("each readiness axis accepts exactly one promotion receipt")
            seen_axes.add(receipt.axis)
            states[receipt.axis] = receipt.state
            evidence_by_kind[receipt.validation_kind].append(receipt.evidence_id)
        return cls(
            family_key=definition.family_key,
            family_definition=definition,
            definition=states[ReadinessAxis.DEFINITION],
            assets=states[ReadinessAxis.ASSETS],
            checkpoint=states[ReadinessAxis.CHECKPOINT],
            construction=states[ReadinessAxis.CONSTRUCTION],
            forward=states[ReadinessAxis.FORWARD],
            training=states[ReadinessAxis.TRAINING],
            prediction=states[ReadinessAxis.PREDICTION],
            data_binding=states[ReadinessAxis.DATA_BINDING],
            distributed=states[ReadinessAxis.DISTRIBUTED],
            validation=ReadinessValidationState(
                source=tuple(sorted(evidence_by_kind[EvidenceValidationKind.SOURCE])),
                static=tuple(sorted(evidence_by_kind[EvidenceValidationKind.STATIC])),
                runtime=tuple(sorted(evidence_by_kind[EvidenceValidationKind.RUNTIME])),
            ),
            receipts=ordered,
        )

    def to_json_dict(self) -> dict[str, object]:
        """返回不含运行对象且字段顺序稳定的公共载荷。"""

        return {
            "assets": self.assets.value,
            "checkpoint": self.checkpoint.value,
            "construction": self.construction.value,
            "data_binding": self.data_binding.value,
            "definition": self.definition.value,
            "definition_fingerprint": (
                None if self.family_definition is None else self.family_definition.fingerprint
            ),
            "distributed": self.distributed.value,
            "family_key": self.family_key,
            "forward": self.forward.value,
            "prediction": self.prediction.value,
            "receipts": [receipt.to_json_dict() for receipt in self.receipts],
            "training": self.training.value,
            "validation": self.validation.to_json_dict(),
        }

    def to_json(self) -> str:
        """返回确定性的紧凑 JSON。"""

        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def fingerprint(self) -> str:
        """返回覆盖全部就绪字段和证据身份的 SHA256。"""

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


__all__ = [
    "AssetReadiness",
    "CheckpointReadiness",
    "ConstructionReadiness",
    "DataBindingReadiness",
    "DefinitionReadiness",
    "DistributedReadiness",
    "EvidenceValidationKind",
    "ForwardReadiness",
    "ModelFamilyReadiness",
    "PredictionReadiness",
    "ReadinessAxis",
    "ReadinessEvidenceReceipt",
    "ReadinessValidationState",
    "TrainingReadiness",
]
