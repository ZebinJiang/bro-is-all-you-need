"""把真实后端批经显式绑定交给现有模型族处理器。"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Protocol, TypeAlias, TypeGuard, cast

from autovla.core.types.training import TrainingBatch, TrainingSample
from autovla.data.binding.compatibility import evaluate_compatibility
from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    DatasetCompatibilityReport,
    DatasetModelBinding,
)

if TYPE_CHECKING:
    from autovla.config.schema import DatasetConfig

BACKEND_DECISION = "NO_BACKEND_WINNER"
_BACKENDS = frozenset({"lerobot_local", "webdataset", "robodm_container"})
CursorScalar: TypeAlias = str | int


def _is_object_tuple(value: object) -> TypeGuard[tuple[object, ...]]:
    """把动态边界值收窄为未知元素元组。"""
    return isinstance(value, tuple)


def _is_object_pair(value: object) -> TypeGuard[tuple[object, object]]:
    """把 cursor 条目收窄为二元组。"""
    return _is_object_tuple(value) and len(value) == 2


def _text(value: object, name: str) -> str:
    """校验并返回非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _cursor_items(values: object, name: str) -> tuple[tuple[str, CursorScalar], ...]:
    """校验后端中立 cursor/resume 项并保持调用方顺序。"""
    if not _is_object_tuple(values):
        raise TypeError(f"{name} must be a tuple")
    result: list[tuple[str, CursorScalar]] = []
    for index, item in enumerate(values):
        if not _is_object_pair(item):
            raise TypeError(f"{name}[{index}] must be a key/value tuple")
        key = _text(item[0], f"{name}[{index}].key")
        value = item[1]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise TypeError(f"{name}[{index}].value must be str or int")
        if isinstance(value, str):
            value = _text(value, f"{name}[{index}].value")
        result.append((key, value))
    if len({key for key, _ in result}) != len(result):
        raise ValueError(f"{name} keys must be unique")
    return tuple(result)


def _training_batch(value: object, name: str) -> TrainingBatch:
    """在动态边界校验并收窄规范训练批。"""
    if not isinstance(value, TrainingBatch):
        raise TypeError(f"{name} must be canonical TrainingBatch")
    return value


def _binding(value: object) -> DatasetModelBinding:
    """在构造边界校验并收窄数据集模型绑定。"""
    if not isinstance(value, DatasetModelBinding):
        raise TypeError("binding must be DatasetModelBinding")
    return value


def _compatibility_report(value: object) -> DatasetCompatibilityReport:
    """在构造边界校验并收窄兼容性报告。"""
    if not isinstance(value, DatasetCompatibilityReport):
        raise TypeError("compatibility_report must be DatasetCompatibilityReport")
    return value


@dataclass(frozen=True, slots=True)
class BackendBatchContext:
    """保存物理读取位置、恢复状态和来源,不把后端排序为赢家。"""

    backend_key: str
    source_revision: str
    provenance_fingerprint: str
    cursor: tuple[tuple[str, CursorScalar], ...]
    resume_state: tuple[tuple[str, CursorScalar], ...]
    resume_mode: str
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """限制后端集合并校验不可变 cursor/resume 载荷。"""
        backend = _text(self.backend_key, "backend_key")
        if backend not in _BACKENDS:
            raise ValueError(f"unsupported physical backend: {backend!r}")
        object.__setattr__(self, "backend_key", backend)
        for name in ("source_revision", "provenance_fingerprint"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(self, "cursor", _cursor_items(self.cursor, "cursor"))
        object.__setattr__(self, "resume_state", _cursor_items(self.resume_state, "resume_state"))
        if self.resume_mode not in {"none", "replay", "exact"}:
            raise ValueError("resume_mode must be none, replay, or exact")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("backend context must preserve NO_BACKEND_WINNER")


class PhysicalBatchProjector(Protocol):
    """描述由绑定明确命名、不得隐式补零的物理投影。"""

    def __call__(self, batch: TrainingBatch, binding: DatasetModelBinding, /) -> TrainingBatch:
        """返回仍为物理量的模型输入侧规范批。"""
        ...


class FamilyBatchProcessor(Protocol):
    """描述三个现有 family processor 共用的最小入口。"""

    def prepare_batch(
        self,
        batch: TrainingBatch,
        *,
        device: object,
        dtype: object | None,
        training: bool,
    ) -> object:
        """把已绑定规范批转换为 family-owned 模型输入。"""
        ...


@dataclass(frozen=True, slots=True)
class BoundTrainingBatch:
    """把规范批与绑定、静态报告和物理读取 sidecar 关联起来。"""

    batch: TrainingBatch
    binding_fingerprint: str
    compatibility_report_fingerprint: str
    compatibility_level: DatasetCompatibilityLevel
    backend_context: BackendBatchContext

    def __post_init__(self) -> None:
        """拒绝 fixture-only/incompatible 真实数据交接。"""
        _training_batch(cast(object, self.batch), "batch")
        if self.compatibility_level not in {
            DatasetCompatibilityLevel.EXACT,
            DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        }:
            raise ValueError("physical batch requires exact or explicit_projection")


@dataclass(frozen=True, slots=True)
class DatasetModelRuntime:
    """验证真实物理批并把它交给现有 family processor,不拥有模型运行时。"""

    binding: DatasetModelBinding
    compatibility_report: DatasetCompatibilityReport

    def __post_init__(self) -> None:
        """要求报告与当前绑定的确定性重算结果完全一致。"""
        _binding(cast(object, self.binding))
        _compatibility_report(cast(object, self.compatibility_report))
        expected = evaluate_compatibility(self.binding)
        if expected.fingerprint != self.compatibility_report.fingerprint:
            raise ValueError("compatibility report is stale or belongs to another binding")

    def bind(
        self,
        batch: TrainingBatch,
        context: BackendBatchContext,
        *,
        projector: PhysicalBatchProjector | None = None,
    ) -> BoundTrainingBatch:
        """验证数据侧语义,执行显式投影并再次验证模型输入侧物理形状。"""
        canonical_batch = _training_batch(cast(object, batch), "batch")
        level = self.compatibility_report.level
        if level not in {
            DatasetCompatibilityLevel.EXACT,
            DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        }:
            raise ValueError(f"{level.value} cannot enter the physical data runtime")
        self._validate_dataset_batch(canonical_batch, context)
        if level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION:
            if projector is None:
                raise ValueError("explicit_projection requires an explicit physical projector")
            projected = _training_batch(
                cast(object, projector(canonical_batch, self.binding)),
                "physical projector result",
            )
        else:
            if projector is not None:
                raise ValueError("exact binding must not execute a projector")
            projected = canonical_batch
        self._validate_model_batch(projected)
        return BoundTrainingBatch(
            batch=projected,
            binding_fingerprint=self.binding.fingerprint,
            compatibility_report_fingerprint=self.compatibility_report.fingerprint,
            compatibility_level=level,
            backend_context=context,
        )

    def bind_records(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        config: DatasetConfig,
        context: BackendBatchContext,
        projector: PhysicalBatchProjector | None = None,
    ) -> BoundTrainingBatch:
        """经现有记录转换器和唯一 collator 连接 LeRobot/WebDataset/RoboDM 记录。"""
        if not records:
            raise ValueError("records must not be empty")
        if config.backend != context.backend_key:
            raise ValueError("dataset config backend differs from physical backend context")
        from autovla.data.backends.base import record_to_training_sample
        from autovla.data.collators.padded import PaddedBatchCollator

        samples: list[TrainingSample] = []
        for index, record in enumerate(records):
            payload_value = record.get("payload", record)
            if not isinstance(payload_value, Mapping):
                raise ValueError(f"records[{index}] payload must be a mapping")
            payload = cast(Mapping[str, object], payload_value)
            for key in (config.action_key, config.action_mask_key, config.state_key):
                if key not in payload:
                    raise ValueError(f"records[{index}] lacks required physical field {key!r}")
            source = record_to_training_sample(
                record,
                config=config,
                transform_fingerprint=self.binding.fingerprint,
                statistics_fingerprint=self.binding.normalization_binding.statistics_fingerprint,
            )
            samples.append(
                replace(
                    source,
                    dataset_fingerprint=self.binding.immutable_dataset_fingerprint,
                    dataset_manifest_fingerprint=self.binding.immutable_dataset_fingerprint,
                    source_fingerprint=context.provenance_fingerprint,
                    schema_fingerprint=self.binding.dataset_schema.fingerprint,
                    store_fingerprint=context.source_revision,
                )
            )
        return self.bind(PaddedBatchCollator()(samples), context, projector=projector)

    def prepare_for_family(
        self,
        bound: BoundTrainingBatch,
        processor: FamilyBatchProcessor,
        *,
        device: object,
        dtype: object | None,
        training: bool,
    ) -> object:
        """在指纹复核后调用现有 family-owned ``prepare_batch``。"""
        if bound.binding_fingerprint != self.binding.fingerprint:
            raise ValueError("bound batch belongs to another dataset-model binding")
        if bound.compatibility_report_fingerprint != self.compatibility_report.fingerprint:
            raise ValueError("bound batch compatibility report changed")
        return processor.prepare_batch(
            bound.batch,
            device=device,
            dtype=dtype,
            training=training,
        )

    def _validate_dataset_batch(self, batch: TrainingBatch, context: BackendBatchContext) -> None:
        """验证读取侧相机、维度、时序、归一化、具身和来源身份。"""
        schema = self.binding.dataset_schema
        if batch.dataset_manifest_fingerprint != schema.immutable_dataset_fingerprint:
            raise ValueError("batch immutable dataset fingerprint differs from binding")
        if batch.statistics_fingerprint != schema.normalization_stats_fingerprint:
            raise ValueError("batch normalization fingerprint differs from binding")
        self._validate_shape_side(batch, dataset_side=True)
        if batch.embodiment is None or any(
            value != schema.embodiment.embodiment_id for value in batch.embodiment
        ):
            raise ValueError("batch embodiment is missing or differs from binding")
        for index, source in enumerate(batch.sample_source):
            if source.get("backend") != context.backend_key:
                raise ValueError(f"sample_source[{index}] backend differs from context")
        for name, values in (
            ("store_fingerprints", batch.store_fingerprints),
            ("source_fingerprints", batch.source_fingerprints),
            ("schema_fingerprints", batch.schema_fingerprints),
        ):
            if len(values) != batch.batch_size:
                raise ValueError(f"physical batch must preserve ordered {name}")

    def _validate_model_batch(self, batch: TrainingBatch) -> None:
        """验证投影后批仍是物理量,且不依赖补零冒充兼容。"""
        schema = self.binding.model_schema
        self._validate_shape_side(batch, dataset_side=False)
        if batch.embodiment is None or any(
            value != schema.embodiment_id for value in batch.embodiment
        ):
            raise ValueError("projected batch embodiment differs from model schema")
        if batch.statistics_fingerprint != schema.normalization_stats_fingerprint:
            raise ValueError("projected batch normalization fingerprint differs from model schema")
        if self.compatibility_report.level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION and (
            batch.transform_fingerprint != self.binding.fingerprint
        ):
            raise ValueError("explicit projector must stamp the binding fingerprint")

    def _validate_shape_side(self, batch: TrainingBatch, *, dataset_side: bool) -> None:
        """按 schema 侧验证有序相机、物理宽度、history、horizon 和时间戳。"""
        if dataset_side:
            schema = self.binding.dataset_schema
            state_features = tuple(item for item in schema.features if item.modality == "state")
            action_features = tuple(item for item in schema.features if item.modality == "action")
        else:
            schema = self.binding.model_schema
            state_features = schema.state_features
            action_features = schema.action_features
        if tuple(batch.images) != schema.camera_names:
            raise ValueError("batch camera identity or order differs from schema")
        state_width = sum(item.dimension for item in state_features)
        action_width = sum(item.dimension for item in action_features)
        if batch.state is None:
            raise ValueError("physical batch requires state")
        if schema.history == 1:
            if batch.state.shape != (batch.batch_size, state_width):
                raise ValueError("batch state shape differs from explicit history and dimensions")
        elif batch.state.shape != (batch.batch_size, schema.history, state_width):
            raise ValueError("batch state history or dimensions differ from schema")
        if batch.actions.shape != (batch.batch_size, schema.horizon, action_width):
            raise ValueError("batch action horizon or dimensions differ from schema")
        if batch.timestamps is None or batch.timestamps.shape != (batch.batch_size, schema.horizon):
            raise ValueError("batch timestamps must explicitly cover the action horizon")


__all__ = [
    "BACKEND_DECISION",
    "BackendBatchContext",
    "BoundTrainingBatch",
    "DatasetModelRuntime",
    "FamilyBatchProcessor",
    "PhysicalBatchProjector",
]
