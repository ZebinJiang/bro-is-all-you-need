"""M12 生产后端到物理绑定运行时的统一收据适配器。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePath, PureWindowsPath
from typing import TYPE_CHECKING, cast
from urllib.parse import urlsplit

from autovla.data.binding.contracts import canonical_data, sha256_fingerprint
from autovla.data.binding.receipts import (
    BACKEND_READER_RECEIPT_SCHEMA,
    ROW_VALIDATION_RECEIPT_SCHEMA,
    BackendReaderReceipt,
    ReaderEvidenceClass,
    RowValidationReceipt,
)
from autovla.data.binding.semantic_manifest import BACKEND_DECISION, SemanticManifestReceipt

if TYPE_CHECKING:
    from autovla.config.schema import DatasetConfig
    from autovla.data.binding.runtime import BackendBatchContext

_BACKENDS = frozenset({"lerobot_local", "webdataset", "robodm_container"})
_CREDENTIAL_MARKERS = (
    "api_key=",
    "apikey=",
    "authorization=",
    "password=",
    "secret=",
    "token=",
)


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


def _public_identity(value: object, name: str) -> str:
    """拒绝凭据、绝对路径和 home 缩写进入公开收据身份。"""
    result = _text(value, name)
    lowered = result.lower()
    if any(marker in lowered for marker in _CREDENTIAL_MARKERS):
        raise ValueError(f"{name} must not contain credential material")
    parsed = urlsplit(result)
    if (
        result.startswith("~")
        or PurePath(result).is_absolute()
        or PureWindowsPath(result).is_absolute()
        or (parsed.scheme == "file" and PurePath(parsed.path).is_absolute())
    ):
        raise ValueError(f"{name} must not contain an absolute user path")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError(f"{name} must not contain URI credentials")
    return result


def _public_identities(values: tuple[str, ...], name: str) -> tuple[str, ...]:
    """冻结有序公开身份并允许 replay/resample 重复。"""
    result = tuple(
        _public_identity(value, f"{name}[{index}]") for index, value in enumerate(values)
    )
    if not result:
        raise ValueError(f"{name} must not be empty")
    return result


@dataclass(frozen=True, slots=True)
class BackendBatchReceiptInput:
    """保存后端统一生成的 reader 收据与有序逻辑样本身份。"""

    reader_receipt: BackendReaderReceipt
    ordered_sample_identities: tuple[str, ...]
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """校验 reader、记录顺序和公开身份严格一致。"""
        if not isinstance(cast(object, self.reader_receipt), BackendReaderReceipt):
            raise TypeError("reader_receipt must be BackendReaderReceipt")
        identities = _public_identities(
            tuple(self.ordered_sample_identities),
            "ordered_sample_identities",
        )
        object.__setattr__(self, "ordered_sample_identities", identities)
        if len(identities) != len(self.reader_receipt.record_provenance):
            raise ValueError("ordered sample identities must match reader record count")
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("backend receipt input must preserve NO_BACKEND_WINNER")

    @property
    def backend_context(self) -> "BackendBatchContext":
        """从 reader 收据生成经过同一契约校验的批上下文。"""
        return self.reader_receipt.to_batch_context()

    @property
    def fingerprint(self) -> str:
        """返回不含数组或路径的确定性输入指纹。"""
        return sha256_fingerprint(self)

    def to_dict(self) -> dict[str, object]:
        """返回 JSON 安全的稳定普通字典。"""
        value = canonical_data(self)
        if not isinstance(value, dict):
            raise AssertionError("canonical backend receipt input must be a dictionary")
        return cast(dict[str, object], value)


@dataclass(frozen=True, slots=True)
class DataBackendBindingAdapter:
    """为三个平权生产后端生成同构 reader/context 收据输入。"""

    backend_key: str
    reader_id: str
    reader_version: str
    validator_id: str
    validator_version: str
    backend_decision: str = BACKEND_DECISION

    def __post_init__(self) -> None:
        """限制受支持后端并拒绝路径或凭据型实现身份。"""
        backend = _text(self.backend_key, "backend_key")
        if backend not in _BACKENDS:
            raise ValueError(f"unsupported physical backend: {backend!r}")
        object.__setattr__(self, "backend_key", backend)
        for name in ("reader_id", "reader_version", "validator_id", "validator_version"):
            object.__setattr__(
                self,
                name,
                _public_identity(getattr(self, name), name),
            )
        if self.backend_decision != BACKEND_DECISION:
            raise ValueError("backend binding adapter must preserve NO_BACKEND_WINNER")

    @classmethod
    def for_backend(cls, backend_key: str) -> "DataBackendBindingAdapter":
        """返回固定身份的后端适配器,不表达选择或排名。"""
        backend = _text(backend_key, "backend_key")
        if backend not in _BACKENDS:
            raise ValueError(f"unsupported physical backend: {backend!r}")
        return cls(
            backend_key=backend,
            reader_id=f"autovla.data.{backend}.reader",
            reader_version="1",
            validator_id="autovla.data.semantic-row-validator",
            validator_version="1",
        )

    def mint(
        self,
        *,
        config: "DatasetConfig",
        semantic_manifest_receipt: SemanticManifestReceipt,
        ordered_sample_identities: tuple[str, ...],
        ordered_record_provenance: tuple[str, ...],
        cursor: tuple[tuple[str, str | int], ...],
        resume_state: tuple[tuple[str, str | int], ...],
        resume_mode: str,
    ) -> BackendBatchReceiptInput:
        """从已观察行身份生成统一 reader/context 输入,不接触数据 payload。"""
        from autovla.data.backends.base import dataset_config_fingerprint

        semantic = cast(object, semantic_manifest_receipt)
        if not isinstance(semantic, SemanticManifestReceipt):
            raise TypeError("semantic_manifest_receipt must be SemanticManifestReceipt")
        if config.backend != self.backend_key:
            raise ValueError("dataset config backend differs from binding adapter")
        if semantic_manifest_receipt.backend_key != self.backend_key:
            raise ValueError("semantic manifest backend differs from binding adapter")
        if semantic_manifest_receipt.dataset_id != config.name:
            raise ValueError("semantic manifest dataset differs from dataset config")
        _public_identity(semantic_manifest_receipt.source_revision, "source_revision")
        _public_identity(semantic_manifest_receipt.store_revision, "store_revision")
        identities = _public_identities(
            tuple(ordered_sample_identities),
            "ordered_sample_identities",
        )
        provenance = tuple(
            _sha256(value, f"ordered_record_provenance[{index}]")
            for index, value in enumerate(ordered_record_provenance)
        )
        if len(identities) != len(provenance):
            raise ValueError("ordered sample identities and record provenance must align")
        row = RowValidationReceipt(
            receipt_schema=ROW_VALIDATION_RECEIPT_SCHEMA,
            evidence_class=ReaderEvidenceClass.REAL_DATA,
            semantic_manifest_receipt_fingerprint=semantic_manifest_receipt.fingerprint,
            dataset_schema_fingerprint=semantic_manifest_receipt.dataset_schema_fingerprint,
            dataset_id=semantic_manifest_receipt.dataset_id,
            backend_key=self.backend_key,
            source_revision=semantic_manifest_receipt.source_revision,
            store_revision=semantic_manifest_receipt.store_revision,
            validator_id=self.validator_id,
            validator_version=self.validator_version,
            record_provenance=provenance,
            records_observed=len(provenance),
            validation_status="observed_real_data",
        )
        reader = BackendReaderReceipt(
            receipt_schema=BACKEND_READER_RECEIPT_SCHEMA,
            reader_id=self.reader_id,
            reader_version=self.reader_version,
            dataset_config_fingerprint=dataset_config_fingerprint(config),
            semantic_manifest_receipt=semantic_manifest_receipt,
            row_validation_receipt=row,
            cursor=cursor,
            resume_state=resume_state,
            resume_mode=resume_mode,
        )
        return BackendBatchReceiptInput(
            reader_receipt=reader,
            ordered_sample_identities=identities,
        )


__all__ = ["BackendBatchReceiptInput", "DataBackendBindingAdapter"]
