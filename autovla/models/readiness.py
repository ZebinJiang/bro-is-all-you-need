"""模型族运行就绪度的正交、证据驱动契约。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Iterable, Mapping, TypeVar, cast

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


class RuntimeEvidenceKind(str, Enum):
    """区分源码、静态检查和真实运行收据。"""

    SOURCE = "source"
    STATIC = "static"
    RUNTIME = "runtime"


class RuntimeOperation(str, Enum):
    """列出可由精确运行身份验证的操作。"""

    CONSTRUCTION = "construction"
    CHECKPOINT_LOAD = "checkpoint_load"
    PROCESSOR = "processor"
    FORWARD = "forward"
    BACKWARD = "backward"
    OPTIMIZER_STEP = "optimizer_step"
    PREDICTION = "prediction"
    DECODE = "decode"
    CHECKPOINT_SAVE = "checkpoint_save"
    RESUME = "resume"
    DATA_BINDING = "data_binding"
    PROFILING = "profiling"


class DistributedStrategyKind(str, Enum):
    """描述一次运行收据使用的分布式策略。"""

    SINGLE_GPU = "single_gpu"
    DDP = "ddp"
    DEEPSPEED = "deepspeed"


class DeepSpeedStage(str, Enum):
    """描述 DeepSpeed ZeRO 阶段。"""

    NONE = "none"
    ZERO1 = "1"
    ZERO2 = "2"
    ZERO3 = "3"


class PrecisionMode(str, Enum):
    """描述精确、闭合的运行精度身份。"""

    FP32 = "fp32"
    TF32 = "tf32"
    BF16 = "bf16"
    FP16 = "fp16"


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
ReadinessEnum = TypeVar("ReadinessEnum", bound=Enum)


def _family_definition(value: object) -> ModelFamilyDefinition:
    """在公共边界校验并收窄模型族定义。"""
    if not isinstance(value, ModelFamilyDefinition):
        raise TypeError("definition must be ModelFamilyDefinition")
    return value


def _readiness_state(
    states: Mapping[ReadinessAxis, ReadinessValue],
    axis: ReadinessAxis,
    expected_type: type[ReadinessEnum],
) -> ReadinessEnum:
    """按轴提取精确枚举类型,拒绝内部状态关联漂移。"""
    value = states[axis]
    if not isinstance(value, expected_type) or type(value) is not expected_type:
        raise TypeError(f"{axis.value} readiness uses the wrong enum type")
    return value


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


def readiness_state_type(axis: ReadinessAxis) -> type[Enum]:
    """返回一个 readiness 轴对应的精确枚举类型。"""

    if type(axis) is not ReadinessAxis:
        raise TypeError("axis must use ReadinessAxis")
    return _AXIS_TYPES[axis]


def default_readiness_states() -> dict[ReadinessAxis, ReadinessValue]:
    """返回 M11 兼容投影的独立默认状态映射。"""

    return dict(_DEFAULTS)


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
        if self.family_definition is not None:
            _family_definition(cast(object, self.family_definition))
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

        family_definition = _family_definition(cast(object, definition))
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
            if receipt.family_key != family_definition.family_key:
                raise ValueError("receipt family_key does not match definition")
            if receipt.definition_fingerprint != family_definition.fingerprint:
                raise ValueError("receipt definition fingerprint does not match definition")
            if receipt.axis in seen_axes:
                raise ValueError("each readiness axis accepts exactly one promotion receipt")
            seen_axes.add(receipt.axis)
            states[receipt.axis] = receipt.state
            evidence_by_kind[receipt.validation_kind].append(receipt.evidence_id)
        return cls(
            family_key=family_definition.family_key,
            family_definition=family_definition,
            definition=_readiness_state(states, ReadinessAxis.DEFINITION, DefinitionReadiness),
            assets=_readiness_state(states, ReadinessAxis.ASSETS, AssetReadiness),
            checkpoint=_readiness_state(states, ReadinessAxis.CHECKPOINT, CheckpointReadiness),
            construction=_readiness_state(
                states, ReadinessAxis.CONSTRUCTION, ConstructionReadiness
            ),
            forward=_readiness_state(states, ReadinessAxis.FORWARD, ForwardReadiness),
            training=_readiness_state(states, ReadinessAxis.TRAINING, TrainingReadiness),
            prediction=_readiness_state(states, ReadinessAxis.PREDICTION, PredictionReadiness),
            data_binding=_readiness_state(states, ReadinessAxis.DATA_BINDING, DataBindingReadiness),
            distributed=_readiness_state(states, ReadinessAxis.DISTRIBUTED, DistributedReadiness),
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


def _require_canonical_text(value: str, field_name: str) -> None:
    """要求身份文本非空且没有首尾空白。"""

    if not value or value != value.strip():
        raise ValueError(f"{field_name} must be canonical non-empty text")


def _require_source_sha(value: str, field_name: str) -> None:
    """要求完整的 Git SHA-1 或 SHA-256,拒绝短 SHA。"""

    if len(value) not in {40, 64} or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError(f"{field_name} must be a complete lowercase Git SHA")


@dataclass(frozen=True, slots=True)
class RuntimeTopology:
    """记录节点、进程和 GPU 类型构成的精确拓扑。"""

    node_count: int
    world_size: int
    gpus_per_node: int
    gpu_type: str

    def __post_init__(self) -> None:
        """拒绝布尔整数、非正数量和不闭合拓扑。"""

        for field_name, value in (
            ("node_count", self.node_count),
            ("world_size", self.world_size),
            ("gpus_per_node", self.gpus_per_node),
        ):
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an exact int")
            if value <= 0:
                raise ValueError(f"{field_name} must be positive")
        _require_canonical_text(self.gpu_type, "gpu_type")
        if self.world_size != self.node_count * self.gpus_per_node:
            raise ValueError("world_size must equal node_count * gpus_per_node")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定拓扑载荷。"""

        return {
            "gpu_type": self.gpu_type,
            "gpus_per_node": self.gpus_per_node,
            "node_count": self.node_count,
            "world_size": self.world_size,
        }


@dataclass(frozen=True, slots=True)
class RuntimeValidationKey:
    """绑定一次运行声明所需的全部适用身份。"""

    family_key: str
    definition_fingerprint: str
    operation: RuntimeOperation
    runtime_profile_fingerprint: str | None = None
    runtime_lock_fingerprint: str | None = None
    environment_fingerprint: str | None = None
    asset_fingerprint: str | None = None
    checkpoint_fingerprint: str | None = None
    data_binding_fingerprint: str | None = None
    data_backend: str | None = None
    gradient_accumulation: int | None = None
    source_sha: str | None = None
    command_fingerprint: str | None = None
    evidence_artifact_fingerprint: str | None = None
    strategy: DistributedStrategyKind | None = None
    deepspeed_stage: DeepSpeedStage = DeepSpeedStage.NONE
    topology: RuntimeTopology | None = None
    precision: PrecisionMode | None = None
    checkpoint_mode: str | None = None

    def __post_init__(self) -> None:
        """校验指纹、拓扑和策略组合,但允许历史迁移键缺少 M12 身份。"""

        _require_canonical_text(self.family_key, "family_key")
        _require_sha256(self.definition_fingerprint, "definition_fingerprint")
        if type(self.operation) is not RuntimeOperation:
            raise TypeError("operation must use RuntimeOperation")
        fingerprint_fields = (
            ("runtime_profile_fingerprint", self.runtime_profile_fingerprint),
            ("runtime_lock_fingerprint", self.runtime_lock_fingerprint),
            ("environment_fingerprint", self.environment_fingerprint),
            ("asset_fingerprint", self.asset_fingerprint),
            ("checkpoint_fingerprint", self.checkpoint_fingerprint),
            ("data_binding_fingerprint", self.data_binding_fingerprint),
            ("command_fingerprint", self.command_fingerprint),
            ("evidence_artifact_fingerprint", self.evidence_artifact_fingerprint),
        )
        for field_name, value in fingerprint_fields:
            if value is not None:
                _require_sha256(value, field_name)
        if self.source_sha is not None:
            _require_source_sha(self.source_sha, "source_sha")
        if self.strategy is not None and type(self.strategy) is not DistributedStrategyKind:
            raise TypeError("strategy must use DistributedStrategyKind")
        if type(self.deepspeed_stage) is not DeepSpeedStage:
            raise TypeError("deepspeed_stage must use DeepSpeedStage")
        if self.topology is not None and type(self.topology) is not RuntimeTopology:
            raise TypeError("topology must use RuntimeTopology")
        if self.precision is not None and type(self.precision) is not PrecisionMode:
            raise TypeError("precision must use PrecisionMode")
        if self.data_backend is not None:
            if type(self.data_backend) is not str:
                raise TypeError("data_backend must be an exact str")
            _require_canonical_text(self.data_backend, "data_backend")
            if not self.data_backend.replace("_", "").replace("-", "").isalnum():
                raise ValueError("data_backend must use a canonical token")
        if self.gradient_accumulation is not None:
            if type(self.gradient_accumulation) is not int:
                raise TypeError("gradient_accumulation must be an exact int")
            if self.gradient_accumulation <= 0:
                raise ValueError("gradient_accumulation must be positive")
        if self.checkpoint_mode is not None:
            if type(self.checkpoint_mode) is not str:
                raise TypeError("checkpoint_mode must be an exact str")
            _require_canonical_text(self.checkpoint_mode, "checkpoint_mode")
            if not self.checkpoint_mode.replace("_", "").isalnum():
                raise ValueError("checkpoint_mode must use a canonical token")
        if (self.strategy is None) != (self.topology is None):
            raise ValueError("strategy and topology must be supplied together")
        if self.strategy is DistributedStrategyKind.SINGLE_GPU:
            assert self.topology is not None
            if (
                self.topology.node_count,
                self.topology.world_size,
                self.topology.gpus_per_node,
            ) != (1, 1, 1):
                raise ValueError("single_gpu requires an exact 1x1x1 topology")
        if self.strategy is DistributedStrategyKind.DDP:
            assert self.topology is not None
            if self.topology.world_size < 2:
                raise ValueError("ddp requires world_size >= 2")
        if self.strategy is DistributedStrategyKind.DEEPSPEED:
            if self.deepspeed_stage is DeepSpeedStage.NONE:
                raise ValueError("deepspeed requires a ZeRO stage")
        elif self.deepspeed_stage is not DeepSpeedStage.NONE:
            raise ValueError("a ZeRO stage is valid only for deepspeed")

    @property
    def is_complete_runtime_identity(self) -> bool:
        """返回该键是否具备 M12 运行激活所需的完整身份。"""

        required = (
            self.runtime_profile_fingerprint,
            self.runtime_lock_fingerprint,
            self.environment_fingerprint,
            self.asset_fingerprint,
            self.source_sha,
            self.command_fingerprint,
            self.evidence_artifact_fingerprint,
            self.strategy,
            self.topology,
            self.precision,
        )
        if any(value is None for value in required):
            return False
        checkpoint_operations = {
            RuntimeOperation.CHECKPOINT_LOAD,
            RuntimeOperation.FORWARD,
            RuntimeOperation.BACKWARD,
            RuntimeOperation.OPTIMIZER_STEP,
            RuntimeOperation.PREDICTION,
            RuntimeOperation.DECODE,
            RuntimeOperation.CHECKPOINT_SAVE,
            RuntimeOperation.RESUME,
            RuntimeOperation.PROFILING,
        }
        data_operations = {
            RuntimeOperation.PROCESSOR,
            RuntimeOperation.FORWARD,
            RuntimeOperation.BACKWARD,
            RuntimeOperation.OPTIMIZER_STEP,
            RuntimeOperation.PREDICTION,
            RuntimeOperation.DECODE,
            RuntimeOperation.DATA_BINDING,
            RuntimeOperation.PROFILING,
        }
        accumulation_operations = {
            RuntimeOperation.BACKWARD,
            RuntimeOperation.OPTIMIZER_STEP,
            RuntimeOperation.CHECKPOINT_SAVE,
            RuntimeOperation.RESUME,
            RuntimeOperation.PROFILING,
        }
        checkpoint_mode_operations = {
            RuntimeOperation.CHECKPOINT_LOAD,
            RuntimeOperation.CHECKPOINT_SAVE,
            RuntimeOperation.RESUME,
        }
        if self.operation in checkpoint_operations and self.checkpoint_fingerprint is None:
            return False
        if self.operation in data_operations and (
            self.data_binding_fingerprint is None or self.data_backend is None
        ):
            return False
        if self.operation in accumulation_operations and self.gradient_accumulation is None:
            return False
        if self.operation in checkpoint_mode_operations and self.checkpoint_mode is None:
            return False
        return True

    def to_json_dict(self) -> dict[str, object]:
        """返回包含显式空值的稳定验证键。"""

        return {
            "asset_fingerprint": self.asset_fingerprint,
            "checkpoint_fingerprint": self.checkpoint_fingerprint,
            "checkpoint_mode": self.checkpoint_mode,
            "command_fingerprint": self.command_fingerprint,
            "data_backend": self.data_backend,
            "data_binding_fingerprint": self.data_binding_fingerprint,
            "deepspeed_stage": self.deepspeed_stage.value,
            "definition_fingerprint": self.definition_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "evidence_artifact_fingerprint": self.evidence_artifact_fingerprint,
            "family_key": self.family_key,
            "gradient_accumulation": self.gradient_accumulation,
            "operation": self.operation.value,
            "precision": None if self.precision is None else self.precision.value,
            "runtime_lock_fingerprint": self.runtime_lock_fingerprint,
            "runtime_profile_fingerprint": self.runtime_profile_fingerprint,
            "source_sha": self.source_sha,
            "strategy": None if self.strategy is None else self.strategy.value,
            "topology": None if self.topology is None else self.topology.to_json_dict(),
        }

    def to_json(self) -> str:
        """返回确定性的紧凑 JSON。"""

        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def fingerprint(self) -> str:
        """返回验证键的确定性 SHA256。"""

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceReceipt:
    """记录一个验证键的一次不可变观察。"""

    receipt_id: str
    validation_key: RuntimeValidationKey
    evidence_kind: RuntimeEvidenceKind
    artifact_fingerprint: str
    passed: bool
    historical: bool = False

    def __post_init__(self) -> None:
        """拒绝不完整的新运行收据和伪装成运行结果的静态证据。"""

        _require_canonical_text(self.receipt_id, "receipt_id")
        if type(self.validation_key) is not RuntimeValidationKey:
            raise TypeError("validation_key must use RuntimeValidationKey")
        if type(self.evidence_kind) is not RuntimeEvidenceKind:
            raise TypeError("evidence_kind must use RuntimeEvidenceKind")
        _require_sha256(self.artifact_fingerprint, "artifact_fingerprint")
        if type(self.passed) is not bool or type(self.historical) is not bool:
            raise TypeError("passed and historical must be exact bool values")
        key_artifact = self.validation_key.evidence_artifact_fingerprint
        if key_artifact is not None and key_artifact != self.artifact_fingerprint:
            raise ValueError("receipt artifact does not match its validation key")
        if (
            self.evidence_kind is RuntimeEvidenceKind.RUNTIME
            and not self.historical
            and not self.validation_key.is_complete_runtime_identity
        ):
            raise ValueError("new runtime evidence requires a complete M12 validation identity")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定收据载荷。"""

        return {
            "artifact_fingerprint": self.artifact_fingerprint,
            "evidence_kind": self.evidence_kind.value,
            "historical": self.historical,
            "passed": self.passed,
            "receipt_id": self.receipt_id,
            "validation_key": self.validation_key.to_json_dict(),
        }

    def to_json(self) -> str:
        """返回确定性的紧凑 JSON。"""

        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def fingerprint(self) -> str:
        """返回完整收据载荷的确定性 SHA256。"""

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class RuntimeEvidenceSet:
    """保存可同时覆盖多个操作、策略和拓扑的运行收据集合。"""

    receipts: tuple[RuntimeEvidenceReceipt, ...] = ()

    def __post_init__(self) -> None:
        """要求规范排序并拒绝重复收据或覆盖式验证键。"""

        if type(self.receipts) is not tuple or any(
            type(receipt) is not RuntimeEvidenceReceipt for receipt in self.receipts
        ):
            raise TypeError("receipts must be a tuple of RuntimeEvidenceReceipt")
        ordered = tuple(sorted(self.receipts, key=lambda receipt: receipt.fingerprint))
        if self.receipts != ordered:
            raise ValueError("runtime evidence receipts must use deterministic ordering")
        receipt_ids = tuple(receipt.receipt_id for receipt in self.receipts)
        if len(set(receipt_ids)) != len(receipt_ids):
            raise ValueError("duplicate runtime evidence receipt identity")
        key_fingerprints = tuple(receipt.validation_key.fingerprint for receipt in self.receipts)
        if len(set(key_fingerprints)) != len(key_fingerprints):
            raise ValueError("conflicting receipt payload for one validation key")

    @classmethod
    def derive(cls, receipts: Iterable[RuntimeEvidenceReceipt] = ()) -> RuntimeEvidenceSet:
        """按完整收据指纹排序并构造不可变集合。"""

        supplied = tuple(receipts)
        if any(type(receipt) is not RuntimeEvidenceReceipt for receipt in supplied):
            raise TypeError("receipts must contain RuntimeEvidenceReceipt")
        return cls(tuple(sorted(supplied, key=lambda receipt: receipt.fingerprint)))

    def exact(self, validation_key: RuntimeValidationKey) -> RuntimeEvidenceReceipt | None:
        """返回验证键完全相等的唯一收据。"""

        if type(validation_key) is not RuntimeValidationKey:
            raise TypeError("validation_key must use RuntimeValidationKey")
        return next(
            (receipt for receipt in self.receipts if receipt.validation_key == validation_key),
            None,
        )

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定多收据载荷。"""

        return {"receipts": [receipt.to_json_dict() for receipt in self.receipts]}

    def to_json(self) -> str:
        """返回确定性的紧凑 JSON。"""

        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def fingerprint(self) -> str:
        """返回整个证据集合的确定性 SHA256。"""

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ReadinessProjection:
    """从收据集合导出供 UI 和 CLI 使用的紧凑只读投影。"""

    family_key: str
    definition_fingerprint: str
    source_available: bool
    checkpoint_validated: bool
    forward_validated: bool
    training_validated: bool
    distributed_validated: bool
    runtime_operations: tuple[RuntimeOperation, ...]
    strategies: tuple[DistributedStrategyKind, ...]
    receipt_count: int
    historical_receipt_count: int

    def __post_init__(self) -> None:
        """校验投影仍为规范、有序且不含重复值。"""

        _require_canonical_text(self.family_key, "family_key")
        _require_sha256(self.definition_fingerprint, "definition_fingerprint")
        for field_name, value in (
            ("source_available", self.source_available),
            ("checkpoint_validated", self.checkpoint_validated),
            ("forward_validated", self.forward_validated),
            ("training_validated", self.training_validated),
            ("distributed_validated", self.distributed_validated),
        ):
            if type(value) is not bool:
                raise TypeError(f"{field_name} must be an exact bool")
        for field_name, value in (
            ("receipt_count", self.receipt_count),
            ("historical_receipt_count", self.historical_receipt_count),
        ):
            if type(value) is not int:
                raise TypeError(f"{field_name} must be an exact int")
            if value < 0:
                raise ValueError(f"{field_name} must not be negative")
        if self.runtime_operations != tuple(
            sorted(set(self.runtime_operations), key=lambda item: item.value)
        ):
            raise ValueError("runtime_operations must be unique and sorted")
        if self.strategies != tuple(sorted(set(self.strategies), key=lambda item: item.value)):
            raise ValueError("strategies must be unique and sorted")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 UI/CLI 投影。"""

        return {
            "checkpoint_validated": self.checkpoint_validated,
            "definition_fingerprint": self.definition_fingerprint,
            "distributed_validated": self.distributed_validated,
            "family_key": self.family_key,
            "forward_validated": self.forward_validated,
            "historical_receipt_count": self.historical_receipt_count,
            "receipt_count": self.receipt_count,
            "runtime_operations": [operation.value for operation in self.runtime_operations],
            "source_available": self.source_available,
            "strategies": [strategy.value for strategy in self.strategies],
            "training_validated": self.training_validated,
        }


@dataclass(frozen=True, slots=True)
class ModelFamilyReadinessSnapshot:
    """保存模型族定义身份和完整多收据证据集。"""

    family_key: str
    definition_fingerprint: str
    evidence: RuntimeEvidenceSet

    def __post_init__(self) -> None:
        """拒绝混入其他模型族或过期定义的收据。"""

        _require_canonical_text(self.family_key, "family_key")
        _require_sha256(self.definition_fingerprint, "definition_fingerprint")
        if type(self.evidence) is not RuntimeEvidenceSet:
            raise TypeError("evidence must use RuntimeEvidenceSet")
        for receipt in self.evidence.receipts:
            key = receipt.validation_key
            if key.family_key != self.family_key:
                raise ValueError("receipt family_key does not match readiness snapshot")
            if key.definition_fingerprint != self.definition_fingerprint:
                raise ValueError("receipt definition fingerprint is stale")

    @classmethod
    def derive(
        cls,
        family_key: str,
        definition_fingerprint: str,
        receipts: Iterable[RuntimeEvidenceReceipt] = (),
    ) -> ModelFamilyReadinessSnapshot:
        """只从当前定义身份和显式收据导出快照。"""

        return cls(
            family_key=family_key,
            definition_fingerprint=definition_fingerprint,
            evidence=RuntimeEvidenceSet.derive(receipts),
        )

    @property
    def projection(self) -> ReadinessProjection:
        """从已接受收据实时导出紧凑投影。"""

        passed = tuple(receipt for receipt in self.evidence.receipts if receipt.passed)
        promotable_runtime = tuple(
            receipt
            for receipt in passed
            if receipt.evidence_kind is RuntimeEvidenceKind.RUNTIME
            and not receipt.historical
            and receipt.validation_key.is_complete_runtime_identity
        )
        operations = tuple(
            sorted(
                {receipt.validation_key.operation for receipt in promotable_runtime},
                key=lambda item: item.value,
            )
        )
        strategies = tuple(
            sorted(
                {
                    strategy
                    for receipt in promotable_runtime
                    if (strategy := receipt.validation_key.strategy) is not None
                },
                key=lambda item: item.value,
            )
        )
        source_available = any(
            receipt.evidence_kind is RuntimeEvidenceKind.SOURCE for receipt in passed
        )
        training_operations = {
            RuntimeOperation.OPTIMIZER_STEP,
            RuntimeOperation.RESUME,
        }
        return ReadinessProjection(
            family_key=self.family_key,
            definition_fingerprint=self.definition_fingerprint,
            source_available=source_available,
            checkpoint_validated=RuntimeOperation.CHECKPOINT_LOAD in operations,
            forward_validated=RuntimeOperation.FORWARD in operations,
            training_validated=any(operation in training_operations for operation in operations),
            distributed_validated=any(
                strategy is not DistributedStrategyKind.SINGLE_GPU for strategy in strategies
            ),
            runtime_operations=operations,
            strategies=strategies,
            receipt_count=len(self.evidence.receipts),
            historical_receipt_count=sum(
                1 for receipt in self.evidence.receipts if receipt.historical
            ),
        )

    def to_json_dict(self) -> dict[str, object]:
        """返回 M12 快照本体,不持久化可重新导出的投影。"""

        return {
            "definition_fingerprint": self.definition_fingerprint,
            "evidence": self.evidence.to_json_dict(),
            "family_key": self.family_key,
        }

    def to_json(self) -> str:
        """返回确定性的紧凑 JSON。"""

        return json.dumps(
            self.to_json_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )

    @property
    def fingerprint(self) -> str:
        """返回快照本体的确定性 SHA256。"""

        return hashlib.sha256(self.to_json().encode("utf-8")).hexdigest()


__all__ = [
    "AssetReadiness",
    "CheckpointReadiness",
    "ConstructionReadiness",
    "DataBindingReadiness",
    "DeepSpeedStage",
    "DefinitionReadiness",
    "DistributedReadiness",
    "DistributedStrategyKind",
    "EvidenceValidationKind",
    "ForwardReadiness",
    "ModelFamilyReadiness",
    "ModelFamilyReadinessSnapshot",
    "PrecisionMode",
    "PredictionReadiness",
    "ReadinessAxis",
    "ReadinessEvidenceReceipt",
    "ReadinessProjection",
    "ReadinessValidationState",
    "RuntimeEvidenceKind",
    "RuntimeEvidenceReceipt",
    "RuntimeEvidenceSet",
    "RuntimeOperation",
    "RuntimeTopology",
    "RuntimeValidationKey",
    "TrainingReadiness",
    "default_readiness_states",
    "readiness_state_type",
]
