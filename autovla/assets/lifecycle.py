"""模型资产访问、条款、获取、验证与解析授权契约。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from types import MappingProxyType
from typing import TypeVar, cast
from urllib.parse import urlsplit

from autovla.assets.contracts import (
    STRICT_CHECKSUM_POLICY,
    ModelAssetFile,
    ModelAssetManifest,
    ModelAssetSpec,
    ResolvedModelAsset,
)
from autovla.assets.errors import (
    ModelAssetAuthorizationError,
    ModelAssetConfigurationError,
)

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_KEY = re.compile(r"[a-z0-9][a-z0-9_-]*")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z"
)
_BLOCKER = re.compile(r"[A-Z][A-Z0-9_]*")
_EnumT = TypeVar("_EnumT", bound=Enum)


class AssetAccessState(str, Enum):
    """描述资产访问条件及显式证据状态。"""

    PUBLIC = "public"
    GATED_UNCONFIRMED = "gated_unconfirmed"
    GRANTED = "granted"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"


class AssetTermsState(str, Enum):
    """描述一类独立条款的当前证据状态。"""

    UNKNOWN = "unknown"
    REQUIRED = "required"
    ACCEPTED_BY_USER = "accepted_by_user"
    REJECTED = "rejected"
    NOT_APPLICABLE = "not_applicable"


class AssetTermsKind(str, Enum):
    """隔离代码、模型、数据、转换与派生权重的条款身份。"""

    CODE_LICENSE = "code_license"
    MODEL_CHECKPOINT = "model_checkpoint"
    TOKENIZER = "tokenizer"
    DATASET_CONTENT = "dataset_content"
    CONVERSION_INPUT = "conversion_input"
    CONVERSION_OUTPUT = "conversion_output"
    DERIVED_WEIGHT_PROVENANCE = "derived_weight_provenance"


class AssetTermsAcceptanceAuthority(str, Enum):
    """记录明确执行条款接受动作的外部主体类型。"""

    USER = "user"
    AUTHORIZED_USER = "authorized_user"


class AssetVerificationResult(str, Enum):
    """描述验证流程的终态。"""

    VERIFIED = "verified"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class AssetAccessReceipt:
    """记录访问状态,授权态必须携带外部证据身份。"""

    asset_key: str
    spec_identity: str
    revision: str
    state: AssetAccessState
    observed_at_utc: str
    evidence_identity: str | None = None
    evidence_source_url: str | None = None
    superseded_by: str | None = None
    schema_version: str = "autovla.asset_access_receipt.v1"

    def __post_init__(self) -> None:
        """拒绝伪造枚举、可变 revision、凭据 URL 和含糊授权。"""

        _validate_receipt_header(
            self.schema_version,
            "autovla.asset_access_receipt.v1",
            self.asset_key,
            self.spec_identity,
            self.revision,
        )
        if type(self.state) is not AssetAccessState:
            raise ModelAssetConfigurationError("asset access state must use its closed enum")
        _validate_timestamp(self.observed_at_utc)
        _validate_optional_sha256(self.superseded_by, "access supersession identity")
        if self.state is AssetAccessState.GRANTED:
            _validate_sha256(self.evidence_identity, "granted access evidence identity")
            _validate_public_url(self.evidence_source_url, "granted access evidence source")
        elif self.evidence_identity is not None or self.evidence_source_url is not None:
            raise ModelAssetConfigurationError(
                "only granted access may carry external grant evidence"
            )

    @property
    def fingerprint(self) -> str:
        """返回包含 supersession 状态的稳定收据身份。"""

        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """返回字段固定且不包含凭据或本地路径的 JSON 对象。"""

        return {
            "schema_version": self.schema_version,
            "asset_key": self.asset_key,
            "spec_identity": self.spec_identity,
            "revision": self.revision,
            "state": self.state.value,
            "observed_at_utc": self.observed_at_utc,
            "evidence_identity": self.evidence_identity,
            "evidence_source_url": self.evidence_source_url,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "AssetAccessReceipt":
        """严格解析访问收据并拒绝未知字段。"""

        values = _exact_object(
            payload,
            {
                "schema_version",
                "asset_key",
                "spec_identity",
                "revision",
                "state",
                "observed_at_utc",
                "evidence_identity",
                "evidence_source_url",
                "superseded_by",
            },
            "asset access receipt",
        )
        return cls(
            schema_version=_required_string(values, "schema_version"),
            asset_key=_required_string(values, "asset_key"),
            spec_identity=_required_string(values, "spec_identity"),
            revision=_required_string(values, "revision"),
            state=_enum_value(AssetAccessState, values["state"], "asset access state"),
            observed_at_utc=_required_string(values, "observed_at_utc"),
            evidence_identity=_optional_string(values, "evidence_identity"),
            evidence_source_url=_optional_string(values, "evidence_source_url"),
            superseded_by=_optional_string(values, "superseded_by"),
        )


@dataclass(frozen=True, slots=True)
class AssetTermsReceipt:
    """记录一类条款状态,用户接受必须引用外部收据。"""

    asset_key: str
    spec_identity: str
    revision: str
    terms_kind: AssetTermsKind
    terms_identity: str
    terms_source_url: str
    state: AssetTermsState
    scope: str
    external_receipt_identity: str | None = None
    acceptance_authority: AssetTermsAcceptanceAuthority | None = None
    accepted_at_utc: str | None = None
    superseded_by: str | None = None
    schema_version: str = "autovla.asset_terms_receipt.v1"

    def __post_init__(self) -> None:
        """只允许外部用户证据表达 accepted,不代替用户作出接受动作。"""

        _validate_receipt_header(
            self.schema_version,
            "autovla.asset_terms_receipt.v1",
            self.asset_key,
            self.spec_identity,
            self.revision,
        )
        if type(self.terms_kind) is not AssetTermsKind:
            raise ModelAssetConfigurationError("asset terms kind must use its closed enum")
        if type(self.state) is not AssetTermsState:
            raise ModelAssetConfigurationError("asset terms state must use its closed enum")
        _validate_sha256(self.terms_identity, "terms identity")
        _validate_public_url(self.terms_source_url, "terms source")
        _validate_key(self.scope, "terms scope")
        _validate_optional_sha256(self.superseded_by, "terms supersession identity")
        if self.state is AssetTermsState.ACCEPTED_BY_USER:
            _validate_sha256(
                self.external_receipt_identity,
                "accepted terms external receipt identity",
            )
            if type(self.acceptance_authority) is not AssetTermsAcceptanceAuthority:
                raise ModelAssetConfigurationError(
                    "accepted terms require an explicit user authority"
                )
            _validate_timestamp(self.accepted_at_utc)
        elif (
            self.external_receipt_identity is not None
            or self.acceptance_authority is not None
            or self.accepted_at_utc is not None
        ):
            raise ModelAssetConfigurationError(
                "non-accepted terms must not carry acceptance evidence"
            )

    @property
    def fingerprint(self) -> str:
        """返回独立条款类别和外部证据共同绑定的稳定身份。"""

        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """返回稳定且无凭据的条款收据 JSON 对象。"""

        return {
            "schema_version": self.schema_version,
            "asset_key": self.asset_key,
            "spec_identity": self.spec_identity,
            "revision": self.revision,
            "terms_kind": self.terms_kind.value,
            "terms_identity": self.terms_identity,
            "terms_source_url": self.terms_source_url,
            "state": self.state.value,
            "scope": self.scope,
            "external_receipt_identity": self.external_receipt_identity,
            "acceptance_authority": (
                self.acceptance_authority.value if self.acceptance_authority is not None else None
            ),
            "accepted_at_utc": self.accepted_at_utc,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "AssetTermsReceipt":
        """严格解析条款收据并保持各类条款身份独立。"""

        values = _exact_object(
            payload,
            {
                "schema_version",
                "asset_key",
                "spec_identity",
                "revision",
                "terms_kind",
                "terms_identity",
                "terms_source_url",
                "state",
                "scope",
                "external_receipt_identity",
                "acceptance_authority",
                "accepted_at_utc",
                "superseded_by",
            },
            "asset terms receipt",
        )
        raw_authority = values["acceptance_authority"]
        authority = (
            None
            if raw_authority is None
            else _enum_value(
                AssetTermsAcceptanceAuthority,
                raw_authority,
                "asset terms acceptance authority",
            )
        )
        return cls(
            schema_version=_required_string(values, "schema_version"),
            asset_key=_required_string(values, "asset_key"),
            spec_identity=_required_string(values, "spec_identity"),
            revision=_required_string(values, "revision"),
            terms_kind=_enum_value(
                AssetTermsKind,
                values["terms_kind"],
                "asset terms kind",
            ),
            terms_identity=_required_string(values, "terms_identity"),
            terms_source_url=_required_string(values, "terms_source_url"),
            state=_enum_value(AssetTermsState, values["state"], "asset terms state"),
            scope=_required_string(values, "scope"),
            external_receipt_identity=_optional_string(
                values,
                "external_receipt_identity",
            ),
            acceptance_authority=authority,
            accepted_at_utc=_optional_string(values, "accepted_at_utc"),
            superseded_by=_optional_string(values, "superseded_by"),
        )


@dataclass(frozen=True, slots=True)
class AssetAcquisitionReceipt:
    """绑定 provider、revision、完整清单和下载器身份的获取收据。"""

    asset_key: str
    spec_identity: str
    provider: str
    revision: str
    inventory: tuple[ModelAssetFile, ...]
    provider_version: str
    downloader_version: str
    acquired_at_utc: str
    superseded_by: str | None = None
    schema_version: str = "autovla.asset_acquisition_receipt.v1"

    def __post_init__(self) -> None:
        """拒绝不完整清单、可变 provider 身份和非规范版本。"""

        _validate_receipt_header(
            self.schema_version,
            "autovla.asset_acquisition_receipt.v1",
            self.asset_key,
            self.spec_identity,
            self.revision,
        )
        _validate_key(self.provider, "acquisition provider")
        _validate_inventory(self.inventory, "acquisition inventory")
        _validate_version(self.provider_version, "acquisition provider version")
        _validate_version(self.downloader_version, "acquisition downloader version")
        _validate_timestamp(self.acquired_at_utc)
        _validate_optional_sha256(self.superseded_by, "acquisition supersession identity")

    @classmethod
    def from_manifest(cls, manifest: ModelAssetManifest) -> "AssetAcquisitionReceipt":
        """从兼容 v2 完成清单派生独立获取身份。"""

        return cls(
            asset_key=manifest.key,
            spec_identity=manifest.spec_identity,
            provider=manifest.provider,
            revision=manifest.revision,
            inventory=manifest.files,
            provider_version=manifest.provider_version,
            downloader_version=manifest.downloader_version,
            acquired_at_utc=manifest.acquired_at_utc,
        )

    @property
    def fingerprint(self) -> str:
        """返回不依赖本地绝对路径的获取收据身份。"""

        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """返回稳定 JSON 获取收据。"""

        return {
            "schema_version": self.schema_version,
            "asset_key": self.asset_key,
            "spec_identity": self.spec_identity,
            "provider": self.provider,
            "revision": self.revision,
            "inventory": _inventory_to_json(self.inventory),
            "provider_version": self.provider_version,
            "downloader_version": self.downloader_version,
            "acquired_at_utc": self.acquired_at_utc,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "AssetAcquisitionReceipt":
        """严格解析获取收据并拒绝部分清单。"""

        values = _exact_object(
            payload,
            {
                "schema_version",
                "asset_key",
                "spec_identity",
                "provider",
                "revision",
                "inventory",
                "provider_version",
                "downloader_version",
                "acquired_at_utc",
                "superseded_by",
            },
            "asset acquisition receipt",
        )
        return cls(
            schema_version=_required_string(values, "schema_version"),
            asset_key=_required_string(values, "asset_key"),
            spec_identity=_required_string(values, "spec_identity"),
            provider=_required_string(values, "provider"),
            revision=_required_string(values, "revision"),
            inventory=_inventory_from_json(values["inventory"], "acquisition inventory"),
            provider_version=_required_string(values, "provider_version"),
            downloader_version=_required_string(values, "downloader_version"),
            acquired_at_utc=_required_string(values, "acquired_at_utc"),
            superseded_by=_optional_string(values, "superseded_by"),
        )


@dataclass(frozen=True, slots=True)
class AssetVerificationReceipt:
    """记录期望/观测清单、策略决策和验证终态。"""

    asset_key: str
    spec_identity: str
    revision: str
    acquisition_receipt_identity: str
    expected_inventory: tuple[ModelAssetFile, ...]
    observed_inventory: tuple[ModelAssetFile, ...]
    checksum_policy: str
    size_verified: bool
    hashes_verified: bool
    safetensors_only: bool
    remote_code_allowed: bool
    result: AssetVerificationResult
    verified_at_utc: str
    superseded_by: str | None = None
    schema_version: str = "autovla.asset_verification_receipt.v1"

    def __post_init__(self) -> None:
        """验证终态必须满足精确清单、摘要、safetensors 与禁远端代码。"""

        _validate_receipt_header(
            self.schema_version,
            "autovla.asset_verification_receipt.v1",
            self.asset_key,
            self.spec_identity,
            self.revision,
        )
        _validate_sha256(
            self.acquisition_receipt_identity,
            "verification acquisition receipt identity",
        )
        _validate_inventory(self.expected_inventory, "expected inventory")
        _validate_inventory(self.observed_inventory, "observed inventory")
        if self.checksum_policy != STRICT_CHECKSUM_POLICY:
            raise ModelAssetConfigurationError("verification checksum policy is unsupported")
        for name, value in (
            ("size_verified", self.size_verified),
            ("hashes_verified", self.hashes_verified),
            ("safetensors_only", self.safetensors_only),
            ("remote_code_allowed", self.remote_code_allowed),
        ):
            if type(value) is not bool:
                raise ModelAssetConfigurationError(f"{name} must be exact bool")
        if type(self.result) is not AssetVerificationResult:
            raise ModelAssetConfigurationError("asset verification result must use its closed enum")
        _validate_timestamp(self.verified_at_utc)
        _validate_optional_sha256(self.superseded_by, "verification supersession identity")
        safe_inventory = _safetensors_policy_satisfied(self.expected_inventory)
        if self.safetensors_only != safe_inventory:
            raise ModelAssetConfigurationError(
                "verification safetensors decision does not match expected inventory"
            )
        if self.result is AssetVerificationResult.VERIFIED and (
            self.expected_inventory != self.observed_inventory
            or not self.size_verified
            or not self.hashes_verified
            or not self.safetensors_only
            or self.remote_code_allowed
        ):
            raise ModelAssetConfigurationError(
                "verified asset receipt does not satisfy terminal safety policy"
            )

    @classmethod
    def from_manifest(
        cls,
        manifest: ModelAssetManifest,
        acquisition: AssetAcquisitionReceipt,
    ) -> "AssetVerificationReceipt":
        """从已完整验证的兼容清单派生 M12 验证收据。"""

        safe_inventory = _safetensors_policy_satisfied(manifest.files)
        result = (
            AssetVerificationResult.VERIFIED
            if safe_inventory and not manifest.remote_code_required
            else AssetVerificationResult.REJECTED
        )
        return cls(
            asset_key=manifest.key,
            spec_identity=manifest.spec_identity,
            revision=manifest.revision,
            acquisition_receipt_identity=acquisition.fingerprint,
            expected_inventory=manifest.files,
            observed_inventory=manifest.files,
            checksum_policy=manifest.checksum_policy,
            size_verified=True,
            hashes_verified=True,
            safetensors_only=safe_inventory,
            remote_code_allowed=manifest.remote_code_required,
            result=result,
            verified_at_utc=manifest.acquired_at_utc,
        )

    @property
    def fingerprint(self) -> str:
        """返回包含全部策略决策和终态的稳定身份。"""

        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """返回稳定 JSON 验证收据。"""

        return {
            "schema_version": self.schema_version,
            "asset_key": self.asset_key,
            "spec_identity": self.spec_identity,
            "revision": self.revision,
            "acquisition_receipt_identity": self.acquisition_receipt_identity,
            "expected_inventory": _inventory_to_json(self.expected_inventory),
            "observed_inventory": _inventory_to_json(self.observed_inventory),
            "checksum_policy": self.checksum_policy,
            "size_verified": self.size_verified,
            "hashes_verified": self.hashes_verified,
            "safetensors_only": self.safetensors_only,
            "remote_code_allowed": self.remote_code_allowed,
            "result": self.result.value,
            "verified_at_utc": self.verified_at_utc,
            "superseded_by": self.superseded_by,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "AssetVerificationReceipt":
        """严格解析验证收据并保留失败终态证据。"""

        values = _exact_object(
            payload,
            {
                "schema_version",
                "asset_key",
                "spec_identity",
                "revision",
                "acquisition_receipt_identity",
                "expected_inventory",
                "observed_inventory",
                "checksum_policy",
                "size_verified",
                "hashes_verified",
                "safetensors_only",
                "remote_code_allowed",
                "result",
                "verified_at_utc",
                "superseded_by",
            },
            "asset verification receipt",
        )
        return cls(
            schema_version=_required_string(values, "schema_version"),
            asset_key=_required_string(values, "asset_key"),
            spec_identity=_required_string(values, "spec_identity"),
            revision=_required_string(values, "revision"),
            acquisition_receipt_identity=_required_string(
                values,
                "acquisition_receipt_identity",
            ),
            expected_inventory=_inventory_from_json(
                values["expected_inventory"],
                "expected inventory",
            ),
            observed_inventory=_inventory_from_json(
                values["observed_inventory"],
                "observed inventory",
            ),
            checksum_policy=_required_string(values, "checksum_policy"),
            size_verified=_required_bool(values, "size_verified"),
            hashes_verified=_required_bool(values, "hashes_verified"),
            safetensors_only=_required_bool(values, "safetensors_only"),
            remote_code_allowed=_required_bool(values, "remote_code_allowed"),
            result=_enum_value(
                AssetVerificationResult,
                values["result"],
                "asset verification result",
            ),
            verified_at_utc=_required_string(values, "verified_at_utc"),
            superseded_by=_optional_string(values, "superseded_by"),
        )


@dataclass(frozen=True, slots=True)
class AssetTermsRequirement:
    """固定一类条款的权威身份、范围和授权所需终态。"""

    terms_kind: AssetTermsKind
    terms_identity: str
    terms_source_url: str
    scope: str
    required_state: AssetTermsState

    def __post_init__(self) -> None:
        """授权策略只能要求用户接受或明确不适用。"""

        if type(self.terms_kind) is not AssetTermsKind:
            raise ModelAssetConfigurationError("terms requirement kind is invalid")
        _validate_sha256(self.terms_identity, "terms requirement identity")
        _validate_public_url(self.terms_source_url, "terms requirement source")
        _validate_key(self.scope, "terms requirement scope")
        if type(self.required_state) is not AssetTermsState or self.required_state not in (
            AssetTermsState.ACCEPTED_BY_USER,
            AssetTermsState.NOT_APPLICABLE,
        ):
            raise ModelAssetConfigurationError(
                "terms requirement must resolve to user acceptance or not-applicable"
            )

    def to_dict(self) -> dict[str, str]:
        """返回稳定条款要求 JSON 对象。"""

        return {
            "terms_kind": self.terms_kind.value,
            "terms_identity": self.terms_identity,
            "terms_source_url": self.terms_source_url,
            "scope": self.scope,
            "required_state": self.required_state.value,
        }


@dataclass(frozen=True, slots=True)
class AssetAuthorizationPolicy:
    """声明一个规范需要的访问终态和独立条款闭集。"""

    asset_key: str
    spec_identity: str
    revision: str
    required_access_state: AssetAccessState
    terms_requirements: tuple[AssetTermsRequirement, ...]
    schema_version: str = "autovla.asset_authorization_policy.v1"

    def __post_init__(self) -> None:
        """策略必须精确绑定规范且不能把未确认访问当作授权。"""

        _validate_receipt_header(
            self.schema_version,
            "autovla.asset_authorization_policy.v1",
            self.asset_key,
            self.spec_identity,
            self.revision,
        )
        if type(
            self.required_access_state
        ) is not AssetAccessState or self.required_access_state not in (
            AssetAccessState.PUBLIC,
            AssetAccessState.GRANTED,
        ):
            raise ModelAssetConfigurationError(
                "authorization policy access must be public or granted"
            )
        raw_terms = cast(object, self.terms_requirements)
        if type(raw_terms) is not tuple or not raw_terms:
            raise ModelAssetConfigurationError(
                "authorization policy requires explicit terms categories"
            )
        terms = cast(tuple[object, ...], raw_terms)
        if any(not isinstance(item, AssetTermsRequirement) for item in terms):
            raise ModelAssetConfigurationError("authorization policy terms are invalid")
        typed_terms = cast(tuple[AssetTermsRequirement, ...], terms)
        kinds = tuple(item.terms_kind for item in typed_terms)
        if len(kinds) != len(set(kinds)):
            raise ModelAssetConfigurationError(
                "authorization policy terms categories must be unique"
            )

    @property
    def fingerprint(self) -> str:
        """返回不含本地路径的授权策略身份。"""

        return _fingerprint(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        """按条款类别排序返回确定性策略 JSON。"""

        return {
            "schema_version": self.schema_version,
            "asset_key": self.asset_key,
            "spec_identity": self.spec_identity,
            "revision": self.revision,
            "required_access_state": self.required_access_state.value,
            "terms_requirements": [
                item.to_dict()
                for item in sorted(
                    self.terms_requirements,
                    key=lambda requirement: requirement.terms_kind.value,
                )
            ],
        }


@dataclass(frozen=True, slots=True)
class AssetLifecycleEvidence:
    """聚合独立收据,不合并或推断任何法律、访问或完整性状态。"""

    access_receipts: tuple[AssetAccessReceipt, ...]
    terms_receipts: tuple[AssetTermsReceipt, ...]
    acquisition_receipt: AssetAcquisitionReceipt
    verification_receipt: AssetVerificationReceipt

    def __post_init__(self) -> None:
        """冻结边界要求全部字段使用精确收据类型。"""

        raw_access = cast(object, self.access_receipts)
        raw_terms = cast(object, self.terms_receipts)
        if type(raw_access) is not tuple or any(
            not isinstance(item, AssetAccessReceipt)
            for item in cast(tuple[object, ...], raw_access)
        ):
            raise ModelAssetConfigurationError("asset access evidence must be a receipt tuple")
        if type(raw_terms) is not tuple or any(
            not isinstance(item, AssetTermsReceipt) for item in cast(tuple[object, ...], raw_terms)
        ):
            raise ModelAssetConfigurationError("asset terms evidence must be a receipt tuple")
        raw_acquisition = cast(object, self.acquisition_receipt)
        raw_verification = cast(object, self.verification_receipt)
        if not isinstance(raw_acquisition, AssetAcquisitionReceipt):
            raise ModelAssetConfigurationError("asset acquisition evidence is invalid")
        if not isinstance(raw_verification, AssetVerificationReceipt):
            raise ModelAssetConfigurationError("asset verification evidence is invalid")

    def to_dict(self) -> dict[str, object]:
        """返回不含凭据和本地路径的严格生命周期证据对象。"""

        return {
            "schema_version": "autovla.asset_lifecycle_evidence.v1",
            "access_receipts": [item.to_dict() for item in self.access_receipts],
            "terms_receipts": [item.to_dict() for item in self.terms_receipts],
            "acquisition_receipt": self.acquisition_receipt.to_dict(),
            "verification_receipt": self.verification_receipt.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: object) -> "AssetLifecycleEvidence":
        """严格解析调用方提供的收据集合,不推断访问或条款终态。"""

        values = _exact_object(
            payload,
            {
                "schema_version",
                "access_receipts",
                "terms_receipts",
                "acquisition_receipt",
                "verification_receipt",
            },
            "asset lifecycle evidence",
        )
        if values["schema_version"] != "autovla.asset_lifecycle_evidence.v1":
            raise ModelAssetConfigurationError("unsupported asset lifecycle evidence schema")
        raw_access = values["access_receipts"]
        raw_terms = values["terms_receipts"]
        if not isinstance(raw_access, list):
            raise ModelAssetConfigurationError("access_receipts must be a list")
        if not isinstance(raw_terms, list):
            raise ModelAssetConfigurationError("terms_receipts must be a list")
        return cls(
            access_receipts=tuple(
                AssetAccessReceipt.from_dict(item) for item in cast(list[object], raw_access)
            ),
            terms_receipts=tuple(
                AssetTermsReceipt.from_dict(item) for item in cast(list[object], raw_terms)
            ),
            acquisition_receipt=AssetAcquisitionReceipt.from_dict(values["acquisition_receipt"]),
            verification_receipt=AssetVerificationReceipt.from_dict(values["verification_receipt"]),
        )


@dataclass(frozen=True, slots=True)
class AssetAuthorizationDecision:
    """给 CLI 和 resolver 返回确定授权结果及首个稳定 blocker。"""

    authorized: bool
    first_blocker: str | None
    policy_identity: str
    access_receipt_identity: str | None
    terms_receipt_identities: tuple[str, ...]
    acquisition_receipt_identity: str | None
    verification_receipt_identity: str | None

    def __post_init__(self) -> None:
        """授权结果必须与 blocker 是否存在严格一致。"""

        if type(self.authorized) is not bool:
            raise ModelAssetConfigurationError("asset authorization decision must use bool")
        if self.authorized != (self.first_blocker is None):
            raise ModelAssetConfigurationError(
                "asset authorization result and blocker are inconsistent"
            )
        if self.first_blocker is not None and not _BLOCKER.fullmatch(self.first_blocker):
            raise ModelAssetConfigurationError("asset authorization blocker must be canonical")
        _validate_sha256(self.policy_identity, "authorization policy identity")
        for name, value in (
            ("access receipt identity", self.access_receipt_identity),
            ("acquisition receipt identity", self.acquisition_receipt_identity),
            ("verification receipt identity", self.verification_receipt_identity),
        ):
            _validate_optional_sha256(value, name)
        raw_terms = cast(object, self.terms_receipt_identities)
        if type(raw_terms) is not tuple:
            raise ModelAssetConfigurationError("terms receipt identities must be a tuple")
        for value in cast(tuple[object, ...], raw_terms):
            _validate_sha256(value, "terms receipt identity")
        if self.authorized and (
            self.access_receipt_identity is None
            or not self.terms_receipt_identities
            or self.acquisition_receipt_identity is None
            or self.verification_receipt_identity is None
        ):
            raise ModelAssetConfigurationError(
                "authorized decision requires every receipt identity"
            )

    def to_dict(self) -> dict[str, object]:
        """返回稳定且不泄漏本地路径的授权摘要。"""

        return {
            "authorized": self.authorized,
            "first_blocker": self.first_blocker,
            "policy_identity": self.policy_identity,
            "access_receipt_identity": self.access_receipt_identity,
            "terms_receipt_identities": list(self.terms_receipt_identities),
            "acquisition_receipt_identity": self.acquisition_receipt_identity,
            "verification_receipt_identity": self.verification_receipt_identity,
        }


@dataclass(frozen=True, slots=True)
class AuthorizedModelAsset:
    """绑定已验证本地资产与显式 M12 授权决定。"""

    resolved: ResolvedModelAsset
    authorization: AssetAuthorizationDecision

    def __post_init__(self) -> None:
        """拒绝把普通本地验证结果伪装成授权结果。"""

        raw_resolved = cast(object, self.resolved)
        raw_authorization = cast(object, self.authorization)
        if not isinstance(raw_resolved, ResolvedModelAsset):
            raise ModelAssetConfigurationError("authorized model asset requires a resolved asset")
        if not isinstance(raw_authorization, AssetAuthorizationDecision):
            raise ModelAssetConfigurationError(
                "authorized model asset requires an authorization decision"
            )
        if (
            not raw_authorization.authorized
            or raw_authorization.acquisition_receipt_identity
            != raw_resolved.acquisition_receipt.fingerprint
            or raw_authorization.verification_receipt_identity
            != raw_resolved.verification_receipt.fingerprint
        ):
            raise ModelAssetConfigurationError(
                "authorized model asset identities do not match local verification"
            )

    @property
    def fingerprint(self) -> str:
        """返回绑定规范、访问、条款、获取与验证收据的稳定授权身份。"""

        payload = {
            "schema_version": "autovla.authorized_model_asset.v1",
            "asset_key": self.resolved.manifest.key,
            "spec_identity": self.resolved.identity,
            "revision": self.resolved.manifest.revision,
            "authorization": self.authorization.to_dict(),
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def authorizes(self, resolved: ResolvedModelAsset) -> bool:
        """确认授权对象与装配请求中的同一已验证本地资产完全一致。"""

        raw_resolved = cast(object, resolved)
        return (
            isinstance(raw_resolved, ResolvedModelAsset)
            and raw_resolved.manifest.key == self.resolved.manifest.key
            and raw_resolved.manifest.revision == self.resolved.manifest.revision
            and raw_resolved.identity == self.resolved.identity
            and raw_resolved.acquisition_receipt.fingerprint
            == self.resolved.acquisition_receipt.fingerprint
            and raw_resolved.verification_receipt.fingerprint
            == self.resolved.verification_receipt.fingerprint
        )


@dataclass(frozen=True, slots=True, init=False)
class AssetAuthorizationPolicyRegistry:
    """按资产键保存不可变授权策略。"""

    _policies: Mapping[str, AssetAuthorizationPolicy]

    def __init__(self, policies: tuple[AssetAuthorizationPolicy, ...] = ()) -> None:
        """拒绝重复资产策略并保存私有副本。"""

        raw_policies = cast(object, policies)
        if type(raw_policies) is not tuple or any(
            not isinstance(policy, AssetAuthorizationPolicy)
            for policy in cast(tuple[object, ...], raw_policies)
        ):
            raise ModelAssetConfigurationError("asset authorization policies must be a tuple")
        typed_policies = cast(tuple[AssetAuthorizationPolicy, ...], raw_policies)
        mapping = {policy.asset_key: policy for policy in typed_policies}
        if len(mapping) != len(policies):
            raise ModelAssetConfigurationError("duplicate asset authorization policy")
        object.__setattr__(self, "_policies", MappingProxyType(mapping))

    def require(self, asset_key: str) -> AssetAuthorizationPolicy:
        """返回精确策略,缺失时拒绝进入解析流程。"""

        try:
            return self._policies[asset_key]
        except KeyError as exc:
            raise ModelAssetAuthorizationError(
                asset_key,
                "ASSET_AUTHORIZATION_POLICY_MISSING",
            ) from exc


def evaluate_asset_authorization(
    spec: ModelAssetSpec,
    policy: AssetAuthorizationPolicy,
    evidence: AssetLifecycleEvidence,
) -> AssetAuthorizationDecision:
    """按策略顺序验证全部收据,首个不一致立即失败关闭。"""

    policy_identity = policy.fingerprint
    if (
        policy.asset_key != spec.key
        or policy.spec_identity != spec.identity
        or policy.revision != spec.revision
    ):
        return _blocked(policy_identity, "ASSET_AUTHORIZATION_POLICY_SPEC_MISMATCH")

    if len(evidence.access_receipts) != 1:
        blocker = (
            "ASSET_ACCESS_RECEIPT_MISSING"
            if not evidence.access_receipts
            else "ASSET_ACCESS_RECEIPTS_CONTRADICTORY"
        )
        return _blocked(policy_identity, blocker)
    access = evidence.access_receipts[0]
    if not _matches_spec(access.asset_key, access.spec_identity, access.revision, spec):
        return _blocked(policy_identity, "ASSET_ACCESS_RECEIPT_SPEC_MISMATCH")
    if access.superseded_by is not None:
        return _blocked(policy_identity, "ASSET_ACCESS_RECEIPT_SUPERSEDED")
    if access.state is not policy.required_access_state:
        return _blocked(policy_identity, f"ASSET_ACCESS_{access.state.value.upper()}")

    terms_by_kind: dict[AssetTermsKind, AssetTermsReceipt] = {}
    for receipt in evidence.terms_receipts:
        if receipt.terms_kind in terms_by_kind:
            return _blocked(
                policy_identity,
                "ASSET_TERMS_RECEIPTS_CONTRADICTORY",
                access=access,
            )
        terms_by_kind[receipt.terms_kind] = receipt
    required_by_kind = {
        requirement.terms_kind: requirement for requirement in policy.terms_requirements
    }
    if set(terms_by_kind) != set(required_by_kind):
        blocker = (
            "ASSET_TERMS_RECEIPT_MISSING"
            if set(required_by_kind) - set(terms_by_kind)
            else "ASSET_TERMS_RECEIPT_UNEXPECTED"
        )
        return _blocked(policy_identity, blocker, access=access)
    ordered_terms: list[AssetTermsReceipt] = []
    for kind in sorted(required_by_kind, key=lambda item: item.value):
        requirement = required_by_kind[kind]
        receipt = terms_by_kind[kind]
        ordered_terms.append(receipt)
        if not _matches_spec(
            receipt.asset_key,
            receipt.spec_identity,
            receipt.revision,
            spec,
        ):
            return _blocked(
                policy_identity,
                "ASSET_TERMS_RECEIPT_SPEC_MISMATCH",
                access=access,
                terms=tuple(ordered_terms),
            )
        if receipt.superseded_by is not None:
            return _blocked(
                policy_identity,
                "ASSET_TERMS_RECEIPT_SUPERSEDED",
                access=access,
                terms=tuple(ordered_terms),
            )
        if (
            receipt.terms_identity != requirement.terms_identity
            or receipt.terms_source_url != requirement.terms_source_url
            or receipt.scope != requirement.scope
        ):
            return _blocked(
                policy_identity,
                "ASSET_TERMS_IDENTITY_MISMATCH",
                access=access,
                terms=tuple(ordered_terms),
            )
        if receipt.state is not requirement.required_state:
            return _blocked(
                policy_identity,
                f"ASSET_TERMS_{receipt.state.value.upper()}",
                access=access,
                terms=tuple(ordered_terms),
            )

    acquisition = evidence.acquisition_receipt
    if not _matches_spec(
        acquisition.asset_key,
        acquisition.spec_identity,
        acquisition.revision,
        spec,
    ):
        return _blocked(
            policy_identity,
            "ASSET_ACQUISITION_RECEIPT_SPEC_MISMATCH",
            access=access,
            terms=tuple(ordered_terms),
        )
    if acquisition.superseded_by is not None:
        return _blocked(
            policy_identity,
            "ASSET_ACQUISITION_RECEIPT_SUPERSEDED",
            access=access,
            terms=tuple(ordered_terms),
        )
    if acquisition.provider != spec.provider or acquisition.inventory != spec.files:
        return _blocked(
            policy_identity,
            "ASSET_ACQUISITION_RECEIPT_PARTIAL_OR_MISMATCHED",
            access=access,
            terms=tuple(ordered_terms),
        )

    verification = evidence.verification_receipt
    if not _matches_spec(
        verification.asset_key,
        verification.spec_identity,
        verification.revision,
        spec,
    ):
        return _blocked(
            policy_identity,
            "ASSET_VERIFICATION_RECEIPT_SPEC_MISMATCH",
            access=access,
            terms=tuple(ordered_terms),
            acquisition=acquisition,
        )
    if verification.superseded_by is not None:
        return _blocked(
            policy_identity,
            "ASSET_VERIFICATION_RECEIPT_SUPERSEDED",
            access=access,
            terms=tuple(ordered_terms),
            acquisition=acquisition,
        )
    if (
        verification.acquisition_receipt_identity != acquisition.fingerprint
        or verification.expected_inventory != spec.files
        or verification.observed_inventory != spec.files
        or verification.checksum_policy != spec.checksum_policy
        or verification.result is not AssetVerificationResult.VERIFIED
        or not verification.size_verified
        or not verification.hashes_verified
        or not verification.safetensors_only
        or verification.remote_code_allowed
    ):
        return _blocked(
            policy_identity,
            "ASSET_VERIFICATION_RECEIPT_PARTIAL_OR_REJECTED",
            access=access,
            terms=tuple(ordered_terms),
            acquisition=acquisition,
            verification=verification,
        )

    return AssetAuthorizationDecision(
        authorized=True,
        first_blocker=None,
        policy_identity=policy_identity,
        access_receipt_identity=access.fingerprint,
        terms_receipt_identities=tuple(item.fingerprint for item in ordered_terms),
        acquisition_receipt_identity=acquisition.fingerprint,
        verification_receipt_identity=verification.fingerprint,
    )


def require_asset_authorization(
    spec: ModelAssetSpec,
    policy: AssetAuthorizationPolicy,
    evidence: AssetLifecycleEvidence,
) -> AssetAuthorizationDecision:
    """要求精确授权,失败时仅公开稳定 blocker。"""

    decision = evaluate_asset_authorization(spec, policy, evidence)
    if not decision.authorized:
        assert decision.first_blocker is not None
        raise ModelAssetAuthorizationError(spec.key, decision.first_blocker)
    return decision


def lifecycle_status_without_receipts(spec: ModelAssetSpec) -> dict[str, object]:
    """返回不推断公开访问或用户接受的静态失败关闭状态。"""

    return lifecycle_status_from_receipts(spec, (), ())


def lifecycle_status_from_receipts(
    spec: ModelAssetSpec,
    access_receipts: tuple[AssetAccessReceipt, ...],
    terms_receipts: tuple[AssetTermsReceipt, ...],
) -> dict[str, object]:
    """汇总用户拥有的访问/条款收据,但不代替授权策略作决定。"""

    inferred_terms_kinds = _terms_kinds_for_inventory(spec.files)
    access_state = AssetAccessState.GATED_UNCONFIRMED
    terms_state = AssetTermsState.REQUIRED
    blocker = "ASSET_ACCESS_RECEIPT_MISSING"
    access_identity: str | None = None
    terms_identities: tuple[str, ...] = ()
    terms_kinds = inferred_terms_kinds

    if len(access_receipts) > 1:
        blocker = "ASSET_ACCESS_RECEIPTS_CONTRADICTORY"
    elif access_receipts:
        access = access_receipts[0]
        access_state = access.state
        access_identity = access.fingerprint
        if not _matches_spec(
            access.asset_key,
            access.spec_identity,
            access.revision,
            spec,
        ):
            blocker = "ASSET_ACCESS_RECEIPT_SPEC_MISMATCH"
        elif access.superseded_by is not None:
            blocker = "ASSET_ACCESS_RECEIPT_SUPERSEDED"
        elif access.state not in (AssetAccessState.PUBLIC, AssetAccessState.GRANTED):
            blocker = f"ASSET_ACCESS_{access.state.value.upper()}"
        elif not terms_receipts:
            blocker = "ASSET_TERMS_RECEIPT_MISSING"
        else:
            by_kind = {receipt.terms_kind: receipt for receipt in terms_receipts}
            if len(by_kind) != len(terms_receipts):
                blocker = "ASSET_TERMS_RECEIPTS_CONTRADICTORY"
            else:
                ordered = tuple(
                    by_kind[kind] for kind in sorted(by_kind, key=lambda item: item.value)
                )
                terms_kinds = tuple(receipt.terms_kind for receipt in ordered)
                terms_identities = tuple(receipt.fingerprint for receipt in ordered)
                blocker = "ASSET_AUTHORIZATION_POLICY_MISSING"
                for receipt in ordered:
                    if not _matches_spec(
                        receipt.asset_key,
                        receipt.spec_identity,
                        receipt.revision,
                        spec,
                    ):
                        blocker = "ASSET_TERMS_RECEIPT_SPEC_MISMATCH"
                        break
                    if receipt.superseded_by is not None:
                        blocker = "ASSET_TERMS_RECEIPT_SUPERSEDED"
                        break
                    if receipt.state not in (
                        AssetTermsState.ACCEPTED_BY_USER,
                        AssetTermsState.NOT_APPLICABLE,
                    ):
                        blocker = f"ASSET_TERMS_{receipt.state.value.upper()}"
                        break
                states = {receipt.state for receipt in ordered}
                if len(states) == 1:
                    terms_state = next(iter(states))
                elif states <= {
                    AssetTermsState.ACCEPTED_BY_USER,
                    AssetTermsState.NOT_APPLICABLE,
                }:
                    terms_state = AssetTermsState.ACCEPTED_BY_USER
                else:
                    terms_state = AssetTermsState.REQUIRED

    return {
        "key": spec.key,
        "spec_identity": spec.identity,
        "revision": spec.revision,
        "access_state": access_state.value,
        "terms_state": terms_state.value,
        "terms_kinds": [item.value for item in terms_kinds],
        "access_receipt_identity": access_identity,
        "terms_receipt_identities": list(terms_identities),
        "first_blocker": blocker,
        "runtime_authorized": False,
    }


def _blocked(
    policy_identity: str,
    blocker: str,
    *,
    access: AssetAccessReceipt | None = None,
    terms: tuple[AssetTermsReceipt, ...] = (),
    acquisition: AssetAcquisitionReceipt | None = None,
    verification: AssetVerificationReceipt | None = None,
) -> AssetAuthorizationDecision:
    """构造不泄漏原始证据内容的失败摘要。"""

    return AssetAuthorizationDecision(
        authorized=False,
        first_blocker=blocker,
        policy_identity=policy_identity,
        access_receipt_identity=access.fingerprint if access is not None else None,
        terms_receipt_identities=tuple(item.fingerprint for item in terms),
        acquisition_receipt_identity=(acquisition.fingerprint if acquisition is not None else None),
        verification_receipt_identity=(
            verification.fingerprint if verification is not None else None
        ),
    )


def _matches_spec(
    asset_key: str,
    spec_identity: str,
    revision: str,
    spec: ModelAssetSpec,
) -> bool:
    """检查收据头与规范身份完全一致。"""

    return asset_key == spec.key and spec_identity == spec.identity and revision == spec.revision


def _terms_kinds_for_inventory(
    inventory: tuple[ModelAssetFile, ...],
) -> tuple[AssetTermsKind, ...]:
    """仅按角色列出可能适用类别,不把本地许可文本当作接受证据。"""

    kinds: list[AssetTermsKind] = []
    if any(item.role.endswith("_weights") for item in inventory):
        kinds.append(AssetTermsKind.MODEL_CHECKPOINT)
    if any(
        "tokenizer" in item.role or item.role in {"special_tokens", "added_tokens"}
        for item in inventory
    ):
        kinds.append(AssetTermsKind.TOKENIZER)
    if any(item.role == "normalization_statistics" for item in inventory):
        kinds.append(AssetTermsKind.DATASET_CONTENT)
    if not kinds:
        kinds.append(AssetTermsKind.CODE_LICENSE)
    return tuple(kinds)


def _safetensors_policy_satisfied(inventory: tuple[ModelAssetFile, ...]) -> bool:
    """仅要求模型、checkpoint 与派生权重角色使用 safetensors。"""

    for item in inventory:
        if _is_weight_role(item.role) and not item.path.lower().endswith(".safetensors"):
            return False
    return True


def _is_weight_role(role: str) -> bool:
    """识别显式权重或 checkpoint payload 角色,不误伤索引与元数据。"""

    parts = frozenset(role.split("_"))
    return bool(parts.intersection({"weight", "weights"})) or role in {
        "checkpoint",
        "base_checkpoint",
        "derived_checkpoint",
        "model_checkpoint",
    }


def _validate_receipt_header(
    schema_version: str,
    expected_schema: str,
    asset_key: str,
    spec_identity: str,
    revision: str,
) -> None:
    """校验每类收据共同的不可变头字段。"""

    if schema_version != expected_schema:
        raise ModelAssetConfigurationError("unsupported asset lifecycle receipt schema")
    _validate_key(asset_key, "asset key")
    _validate_sha256(spec_identity, "asset spec identity")
    raw_revision = cast(object, revision)
    if not isinstance(raw_revision, str) or not _REVISION.fullmatch(raw_revision):
        raise ModelAssetConfigurationError("asset receipt revision must be an exact Git SHA")


def _validate_key(value: object, name: str) -> None:
    """要求字段使用不会携带路径或凭据的规范键。"""

    if not isinstance(value, str) or not _KEY.fullmatch(value):
        raise ModelAssetConfigurationError(f"{name} must be a canonical key")


def _validate_sha256(value: object, name: str) -> None:
    """要求身份为完整小写 SHA256。"""

    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ModelAssetConfigurationError(f"{name} must be a full SHA256")


def _validate_optional_sha256(value: object, name: str) -> None:
    """校验可选 supersession 或外部证据身份。"""

    if value is not None:
        _validate_sha256(value, name)


def _validate_version(value: object, name: str) -> None:
    """限制实现版本为短规范文本。"""

    if not isinstance(value, str) or not _VERSION.fullmatch(value):
        raise ModelAssetConfigurationError(f"{name} is invalid")


def _validate_timestamp(value: object) -> None:
    """要求 UTC ISO-8601 时间,避免本地时区歧义。"""

    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise ModelAssetConfigurationError("asset receipt timestamp must be UTC ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ModelAssetConfigurationError("asset receipt timestamp is invalid") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ModelAssetConfigurationError("asset receipt timestamp must use UTC")


def _validate_public_url(value: object, name: str) -> None:
    """只接受无凭据、查询和 fragment 的公开 HTTPS 来源。"""

    if not isinstance(value, str):
        raise ModelAssetConfigurationError(f"{name} must be a public HTTPS URL")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ModelAssetConfigurationError(f"{name} must be a public HTTPS URL")


def _validate_inventory(value: object, name: str) -> None:
    """要求非空、类型精确且路径唯一的清单 tuple。"""

    if type(value) is not tuple or not value:
        raise ModelAssetConfigurationError(f"{name} must be a non-empty tuple")
    records = cast(tuple[object, ...], value)
    if any(not isinstance(item, ModelAssetFile) for item in records):
        raise ModelAssetConfigurationError(f"{name} contains an invalid record")
    typed = cast(tuple[ModelAssetFile, ...], records)
    if len({item.path for item in typed}) != len(typed):
        raise ModelAssetConfigurationError(f"{name} paths must be unique")


def _inventory_to_json(inventory: tuple[ModelAssetFile, ...]) -> list[dict[str, object]]:
    """按既有规范顺序序列化完整资产清单。"""

    return [
        {
            "path": item.path,
            "size": item.size,
            "sha256": item.sha256,
            "role": item.role,
        }
        for item in inventory
    ]


def _inventory_from_json(payload: object, name: str) -> tuple[ModelAssetFile, ...]:
    """严格解析完整清单并拒绝未知字段或 bool-as-int。"""

    if not isinstance(payload, list) or not payload:
        raise ModelAssetConfigurationError(f"{name} must be a non-empty list")
    records: list[ModelAssetFile] = []
    for item in cast(list[object], payload):
        values = _exact_object(
            item,
            {"path", "size", "sha256", "role"},
            f"{name} item",
        )
        size = values["size"]
        if type(size) is not int:
            raise ModelAssetConfigurationError(f"{name} size must be exact int")
        records.append(
            ModelAssetFile(
                path=_required_string(values, "path"),
                size=size,
                sha256=_required_string(values, "sha256"),
                role=_required_string(values, "role"),
            )
        )
    return tuple(records)


def _exact_object(
    payload: object,
    fields: set[str],
    name: str,
) -> dict[str, object]:
    """要求 JSON object 字段闭集完全一致。"""

    if not isinstance(payload, dict):
        raise ModelAssetConfigurationError(f"{name} must be a JSON object")
    raw = cast(dict[object, object], payload)
    if any(not isinstance(key, str) for key in raw):
        raise ModelAssetConfigurationError(f"{name} keys must be strings")
    values = cast(dict[str, object], raw)
    if set(values) != fields:
        raise ModelAssetConfigurationError(f"{name} fields are not exact")
    return values


def _required_string(values: dict[str, object], key: str) -> str:
    """读取严格字符串字段。"""

    value = values[key]
    if not isinstance(value, str):
        raise ModelAssetConfigurationError(f"{key} must be a string")
    return value


def _optional_string(values: dict[str, object], key: str) -> str | None:
    """读取严格可选字符串字段。"""

    value = values[key]
    if value is not None and not isinstance(value, str):
        raise ModelAssetConfigurationError(f"{key} must be a string or null")
    return value


def _required_bool(values: dict[str, object], key: str) -> bool:
    """读取严格布尔字段并拒绝整数替代。"""

    value = values[key]
    if type(value) is not bool:
        raise ModelAssetConfigurationError(f"{key} must be exact bool")
    return value


def _enum_value(
    enum_type: type[_EnumT],
    value: object,
    name: str,
) -> _EnumT:
    """从严格字符串构造闭集枚举。"""

    if not isinstance(value, str):
        raise ModelAssetConfigurationError(f"{name} must be a string")
    try:
        return enum_type(value)
    except ValueError as exc:
        raise ModelAssetConfigurationError(f"{name} is unsupported") from exc


def _fingerprint(payload: dict[str, object]) -> str:
    """对确定性 JSON 对象计算稳定 SHA256。"""

    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


__all__ = [
    "AssetAccessReceipt",
    "AssetAccessState",
    "AssetAcquisitionReceipt",
    "AssetAuthorizationDecision",
    "AssetAuthorizationPolicy",
    "AssetAuthorizationPolicyRegistry",
    "AssetLifecycleEvidence",
    "AssetTermsAcceptanceAuthority",
    "AssetTermsKind",
    "AssetTermsReceipt",
    "AssetTermsRequirement",
    "AssetTermsState",
    "AssetVerificationReceipt",
    "AssetVerificationResult",
    "AuthorizedModelAsset",
    "evaluate_asset_authorization",
    "lifecycle_status_from_receipts",
    "lifecycle_status_without_receipts",
    "require_asset_authorization",
]
