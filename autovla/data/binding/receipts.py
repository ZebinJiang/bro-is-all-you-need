"""M12 后端读取、行验证、投影和绑定批的不可变收据。"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, TypeAlias, cast

from autovla.data.binding.contracts import (
    DatasetCompatibilityLevel,
    DatasetModelBinding,
    sha256_fingerprint,
)
from autovla.data.binding.semantic_manifest import (
    BACKEND_DECISION,
    ProjectionMode,
    SemanticManifestReceipt,
)

if TYPE_CHECKING:
    from autovla.data.binding.runtime import BackendBatchContext

ROW_VALIDATION_RECEIPT_SCHEMA = "autovla.row_validation_receipt.v1"
BACKEND_READER_RECEIPT_SCHEMA = "autovla.backend_reader_receipt.v1"
PROJECTION_RECEIPT_SCHEMA = "autovla.physical_projection_receipt.v1"
BOUND_BATCH_PROVENANCE_SCHEMA = "autovla.bound_batch_provenance.v1"
CursorScalar: TypeAlias = str | int


def _text(value: object, name: str) -> str:
    """校验并返回非空文本。"""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")
    return value.strip()


def _sha256(value: object, name: str) -> str:
    """校验完整小写 SHA-256。"""
    result = _text(value, name)
    if len(result) != 64 or any(character not in "0123456789abcdef" for character in result):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return result


def _strict_int(value: object, name: str, *, minimum: int = 0) -> int:
    """校验排除 bool 的非负整数。"""
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}")
    return value


def _fingerprints(
    values: tuple[str, ...],
    name: str,
    *,
    allow_empty: bool = False,
) -> tuple[str, ...]:
    """冻结并校验有序指纹序列。"""
    result = tuple(_sha256(value, f"{name}[{index}]") for index, value in enumerate(values))
    if not allow_empty and not result:
        raise ValueError(f"{name} must not be empty")
    return result


def _cursor_items(
    values: tuple[tuple[str, CursorScalar], ...],
    name: str,
) -> tuple[tuple[str, CursorScalar], ...]:
    """校验后端中立 cursor/resume 项。"""
    result: list[tuple[str, CursorScalar]] = []
    for index, item in enumerate(values):
        dynamic_item = cast(object, item)
        if not isinstance(dynamic_item, tuple):
            raise TypeError(f"{name}[{index}] must be a key/value tuple")
        tuple_item = cast(tuple[object, ...], dynamic_item)
        if len(tuple_item) != 2:
            raise TypeError(f"{name}[{index}] must be a key/value tuple")
        key_value = tuple_item
        key = _text(key_value[0], f"{name}[{index}].key")
        value = key_value[1]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise TypeError(f"{name}[{index}].value must be str or int")
        if isinstance(value, str):
            value = _text(value, f"{name}[{index}].value")
        result.append((key, value))
    if len({key for key, _ in result}) != len(result):
        raise ValueError(f"{name} keys must be unique")
    return tuple(result)


class ReaderEvidenceClass(str, Enum):
    """区分真实数据行观察与不可升级契约 fixture。"""

    REAL_DATA = "real_data"
    CONTRACT_FIXTURE_ONLY = "contract_fixture_only"


@dataclass(frozen=True, slots=True)
class RowValidationReceipt:
    """记录有界行观察身份,不由语义清单声明推导。"""

    receipt_schema: str
    evidence_class: ReaderEvidenceClass
    semantic_manifest_receipt_fingerprint: str
    dataset_schema_fingerprint: str
    dataset_id: str
    backend_key: str
    source_revision: str
    store_revision: str
    validator_id: str
    validator_version: str
    record_provenance: tuple[str, ...]
    records_observed: int
    validation_status: str
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """校验真实观察与 fixture 证据类别不能相互升级。"""
        if self.receipt_schema != ROW_VALIDATION_RECEIPT_SCHEMA:
            raise ValueError(f"receipt_schema must equal {ROW_VALIDATION_RECEIPT_SCHEMA!r}")
        evidence_class = cast(object, self.evidence_class)
        if not isinstance(evidence_class, ReaderEvidenceClass):
            raise TypeError("evidence_class must be ReaderEvidenceClass")
        for name in (
            "semantic_manifest_receipt_fingerprint",
            "dataset_schema_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        for name in (
            "dataset_id",
            "backend_key",
            "source_revision",
            "store_revision",
            "validator_id",
            "validator_version",
            "validation_status",
        ):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        provenance = _fingerprints(
            tuple(self.record_provenance),
            "record_provenance",
            allow_empty=self.evidence_class is ReaderEvidenceClass.CONTRACT_FIXTURE_ONLY,
        )
        object.__setattr__(self, "record_provenance", provenance)
        object.__setattr__(
            self,
            "records_observed",
            _strict_int(self.records_observed, "records_observed"),
        )
        if self.evidence_class is ReaderEvidenceClass.REAL_DATA:
            if self.validation_status != "observed_real_data":
                raise ValueError("real-data row receipt requires observed_real_data status")
            if self.records_observed == 0:
                raise ValueError("real-data row receipt must observe at least one record")
            if self.records_observed != len(self.record_provenance):
                raise ValueError("records_observed must equal ordered record provenance count")
        else:
            if self.validation_status != "contract_fixture_only":
                raise ValueError("fixture row receipt must remain contract_fixture_only")
            if self.records_observed != 0 or self.record_provenance:
                raise ValueError("contract fixture cannot claim observed real-data rows")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("row validation receipt must preserve NO_BACKEND_WINNER")

    @property
    def fingerprint(self) -> str:
        """返回行验证收据的确定性指纹。"""
        return sha256_fingerprint(self)


@dataclass(frozen=True, slots=True)
class BackendReaderReceipt:
    """把生产 reader 身份与真实行观察及语义清单精确绑定。"""

    receipt_schema: str
    reader_id: str
    reader_version: str
    dataset_config_fingerprint: str
    semantic_manifest_receipt: SemanticManifestReceipt
    row_validation_receipt: RowValidationReceipt
    cursor: tuple[tuple[str, CursorScalar], ...]
    resume_state: tuple[tuple[str, CursorScalar], ...]
    resume_mode: str
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """拒绝 fixture、陈旧语义、来源漂移和非精确 reader 身份。"""
        if self.receipt_schema != BACKEND_READER_RECEIPT_SCHEMA:
            raise ValueError(f"receipt_schema must equal {BACKEND_READER_RECEIPT_SCHEMA!r}")
        for name in ("reader_id", "reader_version"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        object.__setattr__(
            self,
            "dataset_config_fingerprint",
            _sha256(self.dataset_config_fingerprint, "dataset_config_fingerprint"),
        )
        semantic = cast(object, self.semantic_manifest_receipt)
        if not isinstance(semantic, SemanticManifestReceipt):
            raise TypeError("semantic_manifest_receipt must be SemanticManifestReceipt")
        row = cast(object, self.row_validation_receipt)
        if not isinstance(row, RowValidationReceipt):
            raise TypeError("row_validation_receipt must be RowValidationReceipt")
        if row.evidence_class is not ReaderEvidenceClass.REAL_DATA:
            raise ValueError("backend reader receipt cannot promote a contract fixture")
        expected = (
            (
                "semantic_manifest_receipt_fingerprint",
                row.semantic_manifest_receipt_fingerprint,
                semantic.fingerprint,
            ),
            (
                "dataset_schema_fingerprint",
                row.dataset_schema_fingerprint,
                semantic.dataset_schema_fingerprint,
            ),
            ("dataset_id", row.dataset_id, semantic.dataset_id),
            ("backend_key", row.backend_key, semantic.backend_key),
            ("source_revision", row.source_revision, semantic.source_revision),
            ("store_revision", row.store_revision, semantic.store_revision),
        )
        for name, observed, required in expected:
            if observed != required:
                raise ValueError(f"row validation {name} differs from semantic receipt")
        object.__setattr__(self, "cursor", _cursor_items(tuple(self.cursor), "cursor"))
        object.__setattr__(
            self,
            "resume_state",
            _cursor_items(tuple(self.resume_state), "resume_state"),
        )
        if self.resume_mode not in {"none", "replay", "exact"}:
            raise ValueError("resume_mode must be none, replay, or exact")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("backend reader receipt must preserve NO_BACKEND_WINNER")

    @property
    def fingerprint(self) -> str:
        """返回 reader、语义、行证据和消费位置的完整指纹。"""
        return sha256_fingerprint(self)

    @property
    def record_provenance(self) -> tuple[str, ...]:
        """返回 reader 所验证的有序记录来源。"""
        return self.row_validation_receipt.record_provenance

    def to_batch_context(self) -> "BackendBatchContext":
        """生成与 M11 兼容的批上下文,不导入任何后端实现。"""
        from autovla.data.binding.runtime import BackendBatchContext

        semantic = self.semantic_manifest_receipt
        return BackendBatchContext(
            backend_key=semantic.backend_key,
            dataset_id=semantic.dataset_id,
            dataset_config_fingerprint=self.dataset_config_fingerprint,
            manifest_fingerprint=semantic.immutable_dataset_fingerprint,
            schema_fingerprint=semantic.dataset_schema_fingerprint,
            source_revision=semantic.source_revision,
            store_revision=semantic.store_revision,
            record_provenance=self.record_provenance,
            cursor=self.cursor,
            resume_state=self.resume_state,
            resume_mode=self.resume_mode,
        )


@dataclass(frozen=True, slots=True)
class PhysicalProjectionReceipt:
    """授权一次命名、版本化且精确绑定的物理投影。"""

    receipt_schema: str
    binding_fingerprint: str
    semantic_manifest_receipt_fingerprint: str
    backend_reader_receipt_fingerprint: str
    projector_id: str
    projector_version: str
    projector_fingerprint: str
    projection_mode: ProjectionMode = ProjectionMode.EXPLICIT_PROJECTION

    def __post_init__(self) -> None:
        """校验投影收据不能表示 identity 或漂移实现。"""
        if self.receipt_schema != PROJECTION_RECEIPT_SCHEMA:
            raise ValueError(f"receipt_schema must equal {PROJECTION_RECEIPT_SCHEMA!r}")
        for name in (
            "binding_fingerprint",
            "semantic_manifest_receipt_fingerprint",
            "backend_reader_receipt_fingerprint",
            "projector_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        for name in ("projector_id", "projector_version"):
            object.__setattr__(self, name, _text(getattr(self, name), name))
        if self.projection_mode is not ProjectionMode.EXPLICIT_PROJECTION:
            raise ValueError("physical projection receipt must remain explicit_projection")
        if self.projector_id == "identity":
            raise ValueError("physical projection receipt requires a non-identity projector")

    @property
    def fingerprint(self) -> str:
        """返回物理投影授权收据指纹。"""
        return sha256_fingerprint(self)

    def validate(
        self,
        binding: DatasetModelBinding,
        reader_receipt: BackendReaderReceipt,
    ) -> None:
        """拒绝绑定、reader 或投影器身份漂移。"""
        semantic = reader_receipt.semantic_manifest_receipt
        expected = (
            ("binding_fingerprint", self.binding_fingerprint, binding.fingerprint),
            (
                "semantic_manifest_receipt_fingerprint",
                self.semantic_manifest_receipt_fingerprint,
                semantic.fingerprint,
            ),
            (
                "backend_reader_receipt_fingerprint",
                self.backend_reader_receipt_fingerprint,
                reader_receipt.fingerprint,
            ),
            ("projector_id", self.projector_id, semantic.projector_id),
            ("projector_version", self.projector_version, semantic.projector_version),
            (
                "projector_fingerprint",
                self.projector_fingerprint,
                semantic.projector_fingerprint,
            ),
        )
        for name, observed, required in expected:
            if observed != required:
                raise ValueError(f"projection receipt {name} differs from exact identity")


@dataclass(frozen=True, slots=True)
class BoundBatchProvenance:
    """保存真实绑定批的完整语义、reader、行和投影来源。"""

    provenance_schema: str
    binding_fingerprint: str
    compatibility_report_fingerprint: str
    semantic_manifest_receipt_fingerprint: str
    backend_reader_receipt_fingerprint: str
    row_validation_receipt_fingerprint: str
    backend_context_provenance_fingerprint: str
    compatibility_level: DatasetCompatibilityLevel
    backend_key: str
    record_provenance: tuple[str, ...]
    projection_receipt_fingerprint: str | None
    real_data_evidence: bool = True
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """校验绑定批只能来自真实 reader 且 exact 不携带投影收据。"""
        if self.provenance_schema != BOUND_BATCH_PROVENANCE_SCHEMA:
            raise ValueError(f"provenance_schema must equal {BOUND_BATCH_PROVENANCE_SCHEMA!r}")
        for name in (
            "binding_fingerprint",
            "compatibility_report_fingerprint",
            "semantic_manifest_receipt_fingerprint",
            "backend_reader_receipt_fingerprint",
            "row_validation_receipt_fingerprint",
            "backend_context_provenance_fingerprint",
        ):
            object.__setattr__(self, name, _sha256(getattr(self, name), name))
        if self.compatibility_level not in {
            DatasetCompatibilityLevel.EXACT,
            DatasetCompatibilityLevel.EXPLICIT_PROJECTION,
        }:
            raise ValueError("bound-batch provenance requires exact or explicit_projection")
        object.__setattr__(self, "backend_key", _text(self.backend_key, "backend_key"))
        object.__setattr__(
            self,
            "record_provenance",
            _fingerprints(tuple(self.record_provenance), "record_provenance"),
        )
        if type(self.real_data_evidence) is not bool or not self.real_data_evidence:
            raise ValueError("bound-batch provenance must carry real-data evidence")
        if self.compatibility_level is DatasetCompatibilityLevel.EXACT:
            if self.projection_receipt_fingerprint is not None:
                raise ValueError("exact bound batch must not carry projection receipt")
        else:
            object.__setattr__(
                self,
                "projection_receipt_fingerprint",
                _sha256(
                    self.projection_receipt_fingerprint,
                    "projection_receipt_fingerprint",
                ),
            )
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("bound-batch provenance must preserve NO_BACKEND_WINNER")

    @property
    def fingerprint(self) -> str:
        """返回完整真实绑定批来源指纹。"""
        return sha256_fingerprint(self)


__all__ = [
    "BACKEND_READER_RECEIPT_SCHEMA",
    "BOUND_BATCH_PROVENANCE_SCHEMA",
    "PROJECTION_RECEIPT_SCHEMA",
    "ROW_VALIDATION_RECEIPT_SCHEMA",
    "BackendReaderReceipt",
    "BoundBatchProvenance",
    "PhysicalProjectionReceipt",
    "ReaderEvidenceClass",
    "RowValidationReceipt",
]
