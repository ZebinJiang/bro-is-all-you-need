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
    sha256_fingerprint,
)
from autovla.data.binding.receipts import (
    BOUND_BATCH_PROVENANCE_SCHEMA,
    BackendReaderReceipt,
    BoundBatchProvenance,
    PhysicalProjectionReceipt,
)

if TYPE_CHECKING:
    from autovla.config.schema import DatasetConfig

BACKEND_DECISION = "NO_BACKEND_WINNER"
_BACKENDS = frozenset({"lerobot_local", "webdataset", "robodm_container"})
CursorScalar: TypeAlias = str | int
_RECORD_SOURCE_KEYS = ("episode_id", "frame_index", "sample_id", "timestamp", "window_id")


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


def _sha256(value: object, name: str) -> str:
    """校验小写 SHA-256 十六进制摘要。"""
    result = _text(value, name)
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return result


def _mapping(value: object, name: str) -> Mapping[str, object]:
    """校验动态值为字符串键映射。"""
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be a mapping")
    result = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) for key in result):
        raise TypeError(f"{name} keys must be strings")
    return cast(Mapping[str, object], result)


def _record_source_fingerprint(source: Mapping[str, object]) -> str:
    """计算有序记录来源映射的规范 SHA-256 指纹。"""
    return sha256_fingerprint(dict(source))


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
    """保存读取位置和一份不可变 reader/manifest 来源收据。

    收据同时绑定后端、数据集配置、manifest、schema、source/store revision
    以及按批顺序排列的记录来源指纹,cursor/resume 只描述消费位置。
    """

    backend_key: str
    dataset_id: str
    dataset_config_fingerprint: str
    manifest_fingerprint: str
    schema_fingerprint: str
    source_revision: str
    store_revision: str
    record_provenance: tuple[str, ...]
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
        for name in ("dataset_id", "source_revision", "store_revision"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        for name in (
            "dataset_config_fingerprint",
            "manifest_fingerprint",
            "schema_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        provenance = tuple(self.record_provenance)
        if not provenance:
            raise ValueError("record_provenance must not be empty")
        object.__setattr__(
            self,
            "record_provenance",
            tuple(
                _sha256(value, f"record_provenance[{index}]")
                for index, value in enumerate(provenance)
            ),
        )
        object.__setattr__(self, "cursor", _cursor_items(self.cursor, "cursor"))
        object.__setattr__(self, "resume_state", _cursor_items(self.resume_state, "resume_state"))
        if self.resume_mode not in {"none", "replay", "exact"}:
            raise ValueError("resume_mode must be none, replay, or exact")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("backend context must preserve NO_BACKEND_WINNER")

    @property
    def provenance_fingerprint(self) -> str:
        """返回覆盖完整来源收据、但不包含消费 cursor 的确定性指纹。"""
        return sha256_fingerprint(
            {
                "backend_key": self.backend_key,
                "dataset_config_fingerprint": self.dataset_config_fingerprint,
                "dataset_id": self.dataset_id,
                "manifest_fingerprint": self.manifest_fingerprint,
                "record_provenance": self.record_provenance,
                "schema_fingerprint": self.schema_fingerprint,
                "source_revision": self.source_revision,
                "store_revision": self.store_revision,
            }
        )


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
    """把规范批与绑定、静态报告、reader 收据和物理来源关联起来。"""

    batch: TrainingBatch
    binding_fingerprint: str
    compatibility_report_fingerprint: str
    compatibility_level: DatasetCompatibilityLevel
    backend_context: BackendBatchContext
    provenance: BoundBatchProvenance | None = None

    def __post_init__(self) -> None:
        """拒绝 fixture-only/incompatible 交接及不一致的 M12 来源。"""
        _training_batch(cast(object, self.batch), "batch")
        if self.compatibility_level not in {
            DatasetCompatibilityLevel.EXACT,
            DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        }:
            raise ValueError("physical batch requires exact or explicit_projection")
        if self.provenance is not None:
            if not isinstance(cast(object, self.provenance), BoundBatchProvenance):
                raise TypeError("provenance must be BoundBatchProvenance")
            if self.provenance.binding_fingerprint != self.binding_fingerprint:
                raise ValueError("bound-batch provenance binding differs from batch")
            if (
                self.provenance.compatibility_report_fingerprint
                != self.compatibility_report_fingerprint
            ):
                raise ValueError("bound-batch provenance report differs from batch")
            if self.provenance.compatibility_level is not self.compatibility_level:
                raise ValueError("bound-batch provenance level differs from batch")
            if (
                self.provenance.backend_context_provenance_fingerprint
                != self.backend_context.provenance_fingerprint
            ):
                raise ValueError("bound-batch provenance backend context differs from batch")
            if self.provenance.backend_key != self.backend_context.backend_key:
                raise ValueError("bound-batch provenance backend differs from batch")
            if self.provenance.record_provenance != self.backend_context.record_provenance:
                raise ValueError("bound-batch provenance record order differs from batch")


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
        from autovla.data.backends.base import dataset_config_fingerprint, record_to_training_sample
        from autovla.data.collators.padded import PaddedBatchCollator

        self._validate_context(context, config_fingerprint=dataset_config_fingerprint(config))
        if config.name != context.dataset_id:
            raise ValueError("dataset config identity differs from provenance receipt")
        if len(records) != len(context.record_provenance):
            raise ValueError("record count differs from ordered provenance receipt")

        samples: list[TrainingSample] = []
        for index, record in enumerate(records):
            payload_value = record.get("payload", record)
            if not isinstance(payload_value, Mapping):
                raise ValueError(f"records[{index}] payload must be a mapping")
            payload = cast(Mapping[str, object], payload_value)
            for key in (config.action_key, config.action_mask_key, config.state_key):
                if key not in payload:
                    raise ValueError(f"records[{index}] lacks required physical field {key!r}")
            expected_source = self._record_source(payload, config, context)
            receipt = _mapping(record.get("provenance"), f"records[{index}].provenance")
            self._validate_record_receipt(receipt, expected_source, context, index=index)
            source = record_to_training_sample(
                record,
                config=config,
                transform_fingerprint=self.binding.fingerprint,
                statistics_fingerprint=self.binding.normalization_binding.statistics_fingerprint,
            )
            converted_source = dict(source.sample_source)
            expected_converted_source = {
                key: value
                for key, value in expected_source.items()
                if key != "dataset_config_fingerprint"
            }
            if converted_source != expected_converted_source:
                raise ValueError(
                    f"records[{index}] converted source differs from validated receipt"
                )
            if source.dataset_fingerprint != context.dataset_config_fingerprint:
                raise ValueError(f"records[{index}] converted config identity differs from receipt")
            samples.append(
                replace(
                    source,
                    sample_source=expected_source,
                    dataset_fingerprint=context.manifest_fingerprint,
                    dataset_manifest_fingerprint=context.manifest_fingerprint,
                    source_fingerprint=context.source_revision,
                    schema_fingerprint=context.schema_fingerprint,
                    store_fingerprint=context.store_revision,
                )
            )
        return self.bind(PaddedBatchCollator()(samples), context, projector=projector)

    def bind_with_reader_receipt(
        self,
        batch: TrainingBatch,
        *,
        reader_receipt: BackendReaderReceipt,
        projector: PhysicalBatchProjector | None = None,
        projection_receipt: PhysicalProjectionReceipt | None = None,
    ) -> BoundTrainingBatch:
        """用精确 reader 收据绑定规范批并产出不可变真实数据 provenance。"""
        context = self._validate_reader_bridge(
            reader_receipt,
            projector=projector,
            projection_receipt=projection_receipt,
        )
        bound = self.bind(batch, context, projector=projector)
        return self._attach_reader_provenance(
            bound,
            reader_receipt,
            projection_receipt=projection_receipt,
        )

    def bind_records_with_reader_receipt(
        self,
        records: Sequence[Mapping[str, object]],
        *,
        config: DatasetConfig,
        reader_receipt: BackendReaderReceipt,
        projector: PhysicalBatchProjector | None = None,
        projection_receipt: PhysicalProjectionReceipt | None = None,
    ) -> BoundTrainingBatch:
        """用同一 reader 收据绑定内存记录并产出批级来源证明。"""
        context = self._validate_reader_bridge(
            reader_receipt,
            projector=projector,
            projection_receipt=projection_receipt,
        )
        bound = self.bind_records(
            records,
            config=config,
            context=context,
            projector=projector,
        )
        return self._attach_reader_provenance(
            bound,
            reader_receipt,
            projection_receipt=projection_receipt,
        )

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
        self._validate_provenance(bound.batch, bound.backend_context)
        self._validate_model_batch(bound.batch)
        return processor.prepare_batch(
            bound.batch,
            device=device,
            dtype=dtype,
            training=training,
        )

    def _validate_dataset_batch(self, batch: TrainingBatch, context: BackendBatchContext) -> None:
        """验证读取侧相机、维度、时序、归一化、具身和来源身份。"""
        schema = self.binding.dataset_schema
        self._validate_provenance(batch, context)
        if batch.statistics_fingerprint != schema.normalization_stats_fingerprint:
            raise ValueError("batch normalization fingerprint differs from binding")
        self._validate_shape_side(batch, dataset_side=True)
        if batch.embodiment is None or any(
            value != schema.embodiment.embodiment_id for value in batch.embodiment
        ):
            raise ValueError("batch embodiment is missing or differs from binding")

    def _validate_reader_bridge(
        self,
        reader_receipt: BackendReaderReceipt,
        *,
        projector: PhysicalBatchProjector | None,
        projection_receipt: PhysicalProjectionReceipt | None,
    ) -> BackendBatchContext:
        """复核语义、reader、行观察及投影收据后生成 M11 兼容上下文。"""
        if not isinstance(cast(object, reader_receipt), BackendReaderReceipt):
            raise TypeError("reader_receipt must be BackendReaderReceipt")
        reader_receipt.semantic_manifest_receipt.validate_binding(self.binding)
        level = self.compatibility_report.level
        if level is DatasetCompatibilityLevel.EXACT:
            if projector is not None or projection_receipt is not None:
                raise ValueError("exact reader bridge must not execute or receipt a projector")
        elif level is DatasetCompatibilityLevel.EXPLICIT_PROJECTION:
            if projector is None:
                raise ValueError("explicit_projection requires an explicit physical projector")
            if projection_receipt is None:
                raise ValueError("explicit_projection requires an exact projection receipt")
            projection_receipt.validate(self.binding, reader_receipt)
        else:
            raise ValueError(f"{level.value} cannot enter the physical data runtime")
        context = reader_receipt.to_batch_context()
        self._validate_context(context)
        return context

    def _attach_reader_provenance(
        self,
        bound: BoundTrainingBatch,
        reader_receipt: BackendReaderReceipt,
        *,
        projection_receipt: PhysicalProjectionReceipt | None,
    ) -> BoundTrainingBatch:
        """把验证后的 reader/行/投影身份固化到绑定批。"""
        provenance = BoundBatchProvenance(
            provenance_schema=BOUND_BATCH_PROVENANCE_SCHEMA,
            binding_fingerprint=self.binding.fingerprint,
            compatibility_report_fingerprint=self.compatibility_report.fingerprint,
            semantic_manifest_receipt_fingerprint=(
                reader_receipt.semantic_manifest_receipt.fingerprint
            ),
            backend_reader_receipt_fingerprint=reader_receipt.fingerprint,
            row_validation_receipt_fingerprint=(reader_receipt.row_validation_receipt.fingerprint),
            backend_context_provenance_fingerprint=(bound.backend_context.provenance_fingerprint),
            compatibility_level=self.compatibility_report.level,
            backend_key=reader_receipt.semantic_manifest_receipt.backend_key,
            record_provenance=reader_receipt.record_provenance,
            projection_receipt_fingerprint=(
                None if projection_receipt is None else projection_receipt.fingerprint
            ),
        )
        return replace(bound, provenance=provenance)

    def _validate_context(
        self,
        context: BackendBatchContext,
        *,
        config_fingerprint: str | None = None,
    ) -> None:
        """把 reader/manifest 收据绑定到当前数据集契约和可选配置。"""
        schema = self.binding.dataset_schema
        if context.dataset_id != schema.dataset_id:
            raise ValueError("provenance receipt dataset differs from binding")
        if context.manifest_fingerprint != schema.immutable_dataset_fingerprint:
            raise ValueError("provenance receipt manifest differs from binding")
        if context.schema_fingerprint != schema.fingerprint:
            raise ValueError("provenance receipt schema differs from binding")
        if (
            config_fingerprint is not None
            and config_fingerprint != context.dataset_config_fingerprint
        ):
            raise ValueError("dataset config identity differs from provenance receipt")

    def _validate_provenance(
        self,
        batch: TrainingBatch,
        context: BackendBatchContext,
    ) -> None:
        """在两个绑定入口和 family 入口复核同一份有序来源收据。"""
        self._validate_context(context)
        if batch.dataset_manifest_fingerprint != context.manifest_fingerprint:
            raise ValueError("batch manifest differs from provenance receipt")
        if batch.batch_size != len(context.record_provenance):
            raise ValueError("batch size differs from ordered provenance receipt")
        expected_values = (
            ("store_fingerprints", batch.store_fingerprints, context.store_revision),
            ("source_fingerprints", batch.source_fingerprints, context.source_revision),
            ("schema_fingerprints", batch.schema_fingerprints, context.schema_fingerprint),
        )
        for name, values, expected in expected_values:
            if tuple(values) != (expected,) * batch.batch_size:
                raise ValueError(f"physical batch {name} differ from provenance receipt")
        observed_provenance: list[str] = []
        for index, source in enumerate(batch.sample_source):
            if source.get("backend") != context.backend_key:
                raise ValueError(f"sample_source[{index}] backend differs from receipt")
            if source.get("dataset") != context.dataset_id:
                raise ValueError(f"sample_source[{index}] dataset differs from receipt")
            if source.get("dataset_config_fingerprint") != context.dataset_config_fingerprint:
                raise ValueError(f"sample_source[{index}] config identity differs from receipt")
            observed_provenance.append(_record_source_fingerprint(source))
        if tuple(observed_provenance) != context.record_provenance:
            raise ValueError("ordered record provenance differs from receipt")

    @staticmethod
    def _record_source(
        payload: Mapping[str, object],
        config: DatasetConfig,
        context: BackendBatchContext,
    ) -> dict[str, object]:
        """从轻量记录元数据构造可在物化前核验的规范来源映射。"""
        source = {key: payload[key] for key in _RECORD_SOURCE_KEYS if key in payload}
        source.update(
            {
                "backend": config.backend,
                "dataset": config.name,
                "dataset_config_fingerprint": context.dataset_config_fingerprint,
                "split": config.split,
            }
        )
        return source

    @staticmethod
    def _validate_record_receipt(
        receipt: Mapping[str, object],
        source: Mapping[str, object],
        context: BackendBatchContext,
        *,
        index: int,
    ) -> None:
        """在数组物化前拒绝记录 envelope 与批级收据的任何漂移。"""
        expected = {
            "backend_key": context.backend_key,
            "dataset_config_fingerprint": context.dataset_config_fingerprint,
            "dataset_id": context.dataset_id,
            "manifest_fingerprint": context.manifest_fingerprint,
            "record_provenance": context.record_provenance[index],
            "schema_fingerprint": context.schema_fingerprint,
            "source_revision": context.source_revision,
            "store_revision": context.store_revision,
        }
        for name, value in expected.items():
            if receipt.get(name) != value:
                raise ValueError(f"records[{index}] provenance {name} differs from receipt")
        if _record_source_fingerprint(source) != context.record_provenance[index]:
            raise ValueError(f"records[{index}] source differs from ordered provenance receipt")

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
