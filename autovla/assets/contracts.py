"""不可变模型资产契约、获取证据与规范清单。"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from types import MappingProxyType
from typing import Protocol, TypeAlias, cast, runtime_checkable
from urllib.parse import urlsplit

from autovla.assets.errors import ModelAssetConfigurationError

JsonScalar: TypeAlias = str | int | float | bool | None
ImmutableJsonValue: TypeAlias = (
    JsonScalar | tuple["ImmutableJsonValue", ...] | Mapping[str, "ImmutableJsonValue"]
)

STRICT_CHECKSUM_POLICY = "sha256-size-v1"
VERIFIED_ASSET_STATE = "verified"

_SHA256 = re.compile(r"[0-9a-f]{64}")
_REVISION = re.compile(r"[0-9a-f]{40}")
_NAME = re.compile(r"[a-z0-9][a-z0-9_-]*")
_ROLE = re.compile(r"[a-z][a-z0-9_]*")
_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,127}")
_UTC_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z"
)


def _empty_json_mapping() -> Mapping[str, ImmutableJsonValue]:
    """返回类型明确的空 JSON 元数据映射。"""

    return {}


def validate_relative_path(value: str) -> str:
    """校验资产成员是规范的 POSIX 相对路径且不含逃逸段。"""

    raw_value = cast(object, value)
    if (
        not isinstance(raw_value, str)
        or "\\" in raw_value
        or any(ord(char) < 32 for char in raw_value)
    ):
        raise ModelAssetConfigurationError(f"unsafe model asset relative path: {value!r}")
    value = raw_value
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "." in path.parts:
        raise ModelAssetConfigurationError(f"unsafe model asset relative path: {value!r}")
    if str(path) != value or any(not part for part in path.parts):
        raise ModelAssetConfigurationError(f"non-canonical model asset path: {value!r}")
    return value


@dataclass(frozen=True, slots=True)
class ModelAssetFile:
    """描述一个具有明确角色且必须精确验证的资产文件。"""

    path: str
    size: int
    sha256: str
    role: str

    def __post_init__(self) -> None:
        """拒绝不安全路径、布尔大小、模糊角色和非小写摘要。"""

        validate_relative_path(self.path)
        if type(self.size) is not int or self.size < 0:
            raise ModelAssetConfigurationError("model asset file size must be non-negative int")
        if not _SHA256.fullmatch(self.sha256):
            raise ModelAssetConfigurationError("model asset sha256 must be 64 lowercase hex chars")
        raw_role = cast(object, self.role)
        if not isinstance(raw_role, str) or not _ROLE.fullmatch(raw_role):
            raise ModelAssetConfigurationError("model asset file role must be a canonical name")


@dataclass(frozen=True, slots=True)
class ModelAssetSpec:
    """描述固定来源、许可、校验策略和本地文件集合。"""

    key: str
    family_key: str
    provider: str
    source_url: str
    public_identifier: str
    repository: str
    revision: str
    license_name: str
    license_file_path: str
    use_limitation: str
    redistribution: str
    checksum_policy: str
    files: tuple[ModelAssetFile, ...]
    remote_code_required: bool = False

    def __post_init__(self) -> None:
        """校验规范身份固定、成员唯一、许可可定位且禁止远端代码。"""

        for name, raw_value in (("key", self.key), ("family_key", self.family_key)):
            value = cast(object, raw_value)
            if not isinstance(value, str) or not _NAME.fullmatch(value):
                raise ModelAssetConfigurationError(f"model asset {name} must be a canonical key")
        for name, raw_value in (
            ("provider", self.provider),
            ("public_identifier", self.public_identifier),
            ("repository", self.repository),
            ("license_name", self.license_name),
            ("use_limitation", self.use_limitation),
            ("redistribution", self.redistribution),
        ):
            value = cast(object, raw_value)
            if not isinstance(value, str) or not value.strip():
                raise ModelAssetConfigurationError(f"model asset {name} must not be empty")
        _validate_public_source_url(self.source_url)
        if not _REVISION.fullmatch(self.revision):
            raise ModelAssetConfigurationError("model asset revision must be an exact Git SHA")
        if self.checksum_policy != STRICT_CHECKSUM_POLICY:
            raise ModelAssetConfigurationError("model asset checksum policy is unsupported")
        if type(self.remote_code_required) is not bool:
            raise ModelAssetConfigurationError("remote_code_required must be exact bool")
        if self.remote_code_required:
            raise ModelAssetConfigurationError("remote model code is forbidden")
        raw_files = cast(object, self.files)
        if type(raw_files) is not tuple or not raw_files:
            raise ModelAssetConfigurationError("model asset files must be a non-empty tuple")
        file_records = cast(tuple[object, ...], raw_files)
        if any(not isinstance(item, ModelAssetFile) for item in file_records):
            raise ModelAssetConfigurationError("model asset files contain an invalid record")
        validated_files = cast(tuple[ModelAssetFile, ...], file_records)
        paths = tuple(item.path for item in validated_files)
        if len(paths) != len(set(paths)):
            raise ModelAssetConfigurationError("model asset files must have unique paths")
        validate_relative_path(self.license_file_path)
        license_records = tuple(
            item
            for item in validated_files
            if item.path == self.license_file_path and item.role == "license"
        )
        if len(license_records) != 1:
            raise ModelAssetConfigurationError(
                "model asset license_file_path must select exactly one license-role file"
            )

    @property
    def asset_roles(self) -> tuple[str, ...]:
        """按首次出现顺序返回规范声明的唯一资产角色。"""

        return tuple(dict.fromkeys(item.role for item in self.files))

    @property
    def identity(self) -> str:
        """返回仅由不可变资产契约构成的稳定 SHA256 身份。"""

        return hashlib.sha256(_canonical_spec_json(self).encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ModelAssetAcquisition:
    """保存 provider 返回的 JSON-safe 获取实现证据。"""

    provider_version: str
    downloader_version: str
    provider_metadata: Mapping[str, ImmutableJsonValue] = field(default_factory=_empty_json_mapping)

    def __post_init__(self) -> None:
        """严格校验版本并递归冻结 provider 元数据。"""

        for name, raw_value in (
            ("provider_version", self.provider_version),
            ("downloader_version", self.downloader_version),
        ):
            value = cast(object, raw_value)
            if not isinstance(value, str) or not _VERSION.fullmatch(value):
                raise ModelAssetConfigurationError(f"model asset {name} is invalid")
        frozen = _freeze_json_mapping(self.provider_metadata, "provider_metadata")
        object.__setattr__(self, "provider_metadata", frozen)


@dataclass(frozen=True, slots=True)
class ModelAssetManifest:
    """保存固定规范及一次完成获取和完整性验证的证据。"""

    schema_version: str
    key: str
    family_key: str
    provider: str
    source_url: str
    public_identifier: str
    repository: str
    revision: str
    license_name: str
    license_file_path: str
    use_limitation: str
    redistribution: str
    checksum_policy: str
    asset_roles: tuple[str, ...]
    remote_code_required: bool
    files: tuple[ModelAssetFile, ...]
    spec_identity: str
    acquired_at_utc: str
    provider_version: str
    downloader_version: str
    provider_metadata: Mapping[str, ImmutableJsonValue]
    verification_state: str

    @classmethod
    def from_spec(
        cls,
        spec: ModelAssetSpec,
        *,
        acquired_at_utc: str,
        acquisition: ModelAssetAcquisition,
    ) -> "ModelAssetManifest":
        """从验证后的规范与获取证据创建完成清单。"""

        return cls(
            schema_version="autovla.model_asset_manifest.v2",
            key=spec.key,
            family_key=spec.family_key,
            provider=spec.provider,
            source_url=spec.source_url,
            public_identifier=spec.public_identifier,
            repository=spec.repository,
            revision=spec.revision,
            license_name=spec.license_name,
            license_file_path=spec.license_file_path,
            use_limitation=spec.use_limitation,
            redistribution=spec.redistribution,
            checksum_policy=spec.checksum_policy,
            asset_roles=spec.asset_roles,
            remote_code_required=spec.remote_code_required,
            files=spec.files,
            spec_identity=spec.identity,
            acquired_at_utc=acquired_at_utc,
            provider_version=acquisition.provider_version,
            downloader_version=acquisition.downloader_version,
            provider_metadata=acquisition.provider_metadata,
            verification_state=VERIFIED_ASSET_STATE,
        )

    def __post_init__(self) -> None:
        """重建规范并严格校验动态 provenance 与不可变身份隔离。"""

        if self.schema_version != "autovla.model_asset_manifest.v2":
            raise ModelAssetConfigurationError("unsupported model asset manifest schema")
        spec = self.to_spec()
        if self.spec_identity != spec.identity:
            raise ModelAssetConfigurationError("model asset manifest identity mismatch")
        if type(self.asset_roles) is not tuple or self.asset_roles != spec.asset_roles:
            raise ModelAssetConfigurationError("model asset manifest roles mismatch")
        _validate_utc_timestamp(self.acquired_at_utc)
        acquisition = ModelAssetAcquisition(
            provider_version=self.provider_version,
            downloader_version=self.downloader_version,
            provider_metadata=self.provider_metadata,
        )
        object.__setattr__(self, "provider_metadata", acquisition.provider_metadata)
        if self.verification_state != VERIFIED_ASSET_STATE:
            raise ModelAssetConfigurationError("model asset manifest is not verified")

    def to_spec(self) -> ModelAssetSpec:
        """恢复清单代表的严格不可变资产规范。"""

        return ModelAssetSpec(
            key=self.key,
            family_key=self.family_key,
            provider=self.provider,
            source_url=self.source_url,
            public_identifier=self.public_identifier,
            repository=self.repository,
            revision=self.revision,
            license_name=self.license_name,
            license_file_path=self.license_file_path,
            use_limitation=self.use_limitation,
            redistribution=self.redistribution,
            checksum_policy=self.checksum_policy,
            files=self.files,
            remote_code_required=self.remote_code_required,
        )

    def to_dict(self) -> dict[str, object]:
        """返回字段与嵌套键顺序稳定的 JSON 对象。"""

        return {
            "schema_version": self.schema_version,
            "key": self.key,
            "family_key": self.family_key,
            "provider": self.provider,
            "source_url": self.source_url,
            "public_identifier": self.public_identifier,
            "repository": self.repository,
            "revision": self.revision,
            "license_name": self.license_name,
            "license_file_path": self.license_file_path,
            "use_limitation": self.use_limitation,
            "redistribution": self.redistribution,
            "checksum_policy": self.checksum_policy,
            "asset_roles": list(self.asset_roles),
            "remote_code_required": self.remote_code_required,
            "files": [
                {
                    "path": item.path,
                    "size": item.size,
                    "sha256": item.sha256,
                    "role": item.role,
                }
                for item in self.files
            ],
            "spec_identity": self.spec_identity,
            "acquired_at_utc": self.acquired_at_utc,
            "provider_version": self.provider_version,
            "downloader_version": self.downloader_version,
            "provider_metadata": _thaw_json_mapping(self.provider_metadata),
            "verification_state": self.verification_state,
        }

    @classmethod
    def from_dict(cls, payload: object) -> "ModelAssetManifest":
        """严格解析 JSON 清单, 不接受缺失、未知字段或宽泛元数据。"""

        if not isinstance(payload, dict):
            raise ModelAssetConfigurationError("model asset manifest must be a JSON object")
        raw_payload = cast(dict[object, object], payload)
        if any(not isinstance(key, str) for key in raw_payload):
            raise ModelAssetConfigurationError("model asset manifest keys must be strings")
        values = cast(dict[str, object], raw_payload)
        required = {
            "schema_version",
            "key",
            "family_key",
            "provider",
            "source_url",
            "public_identifier",
            "repository",
            "revision",
            "license_name",
            "license_file_path",
            "use_limitation",
            "redistribution",
            "checksum_policy",
            "asset_roles",
            "remote_code_required",
            "files",
            "spec_identity",
            "acquired_at_utc",
            "provider_version",
            "downloader_version",
            "provider_metadata",
            "verification_state",
        }
        if set(values) != required:
            raise ModelAssetConfigurationError("model asset manifest fields are not exact")
        scalar_names = required - {
            "asset_roles",
            "remote_code_required",
            "files",
            "provider_metadata",
        }
        if any(not isinstance(values[name], str) for name in scalar_names):
            raise ModelAssetConfigurationError("model asset manifest string field has wrong type")
        raw_roles = values["asset_roles"]
        if not isinstance(raw_roles, list):
            raise ModelAssetConfigurationError("model asset manifest roles must be a string list")
        role_values = cast(list[object], raw_roles)
        if any(not isinstance(role, str) for role in role_values):
            raise ModelAssetConfigurationError("model asset manifest roles must be strings")
        raw_files = values["files"]
        if not isinstance(raw_files, list):
            raise ModelAssetConfigurationError("model asset manifest files must be a list")
        files: list[ModelAssetFile] = []
        for raw in cast(list[object], raw_files):
            if not isinstance(raw, dict):
                raise ModelAssetConfigurationError("invalid model asset file record")
            raw_record = cast(dict[object, object], raw)
            if any(not isinstance(key, str) for key in raw_record):
                raise ModelAssetConfigurationError("invalid model asset file record key")
            record = cast(dict[str, object], raw_record)
            if set(record) != {"path", "size", "sha256", "role"}:
                raise ModelAssetConfigurationError("invalid model asset file record")
            if (
                not isinstance(record["path"], str)
                or type(record["size"]) is not int
                or not isinstance(record["sha256"], str)
                or not isinstance(record["role"], str)
            ):
                raise ModelAssetConfigurationError("model asset file record has wrong types")
            files.append(
                ModelAssetFile(
                    path=record["path"],
                    size=record["size"],
                    sha256=record["sha256"],
                    role=record["role"],
                )
            )
        remote_code = values["remote_code_required"]
        if type(remote_code) is not bool:
            raise ModelAssetConfigurationError("remote_code_required must be boolean")
        metadata = _freeze_json_mapping(values["provider_metadata"], "provider_metadata")
        return cls(
            schema_version=cast(str, values["schema_version"]),
            key=cast(str, values["key"]),
            family_key=cast(str, values["family_key"]),
            provider=cast(str, values["provider"]),
            source_url=cast(str, values["source_url"]),
            public_identifier=cast(str, values["public_identifier"]),
            repository=cast(str, values["repository"]),
            revision=cast(str, values["revision"]),
            license_name=cast(str, values["license_name"]),
            license_file_path=cast(str, values["license_file_path"]),
            use_limitation=cast(str, values["use_limitation"]),
            redistribution=cast(str, values["redistribution"]),
            checksum_policy=cast(str, values["checksum_policy"]),
            asset_roles=tuple(cast(str, role) for role in role_values),
            remote_code_required=remote_code,
            files=tuple(files),
            spec_identity=cast(str, values["spec_identity"]),
            acquired_at_utc=cast(str, values["acquired_at_utc"]),
            provider_version=cast(str, values["provider_version"]),
            downloader_version=cast(str, values["downloader_version"]),
            provider_metadata=metadata,
            verification_state=cast(str, values["verification_state"]),
        )


@dataclass(frozen=True, slots=True, init=False)
class ResolvedModelAsset:
    """由 store 私有构造的已验证资产根、清单及稳定身份。"""

    root: Path
    manifest: ModelAssetManifest

    @classmethod
    def from_verified_store(cls, root: Path, manifest: ModelAssetManifest) -> "ResolvedModelAsset":
        """仅供 store 在完成验证后签发类型化结果。"""

        if not root.is_absolute() or manifest.verification_state != VERIFIED_ASSET_STATE:
            raise ModelAssetConfigurationError(
                "resolved model asset requires verified absolute data"
            )
        instance = object.__new__(cls)
        object.__setattr__(instance, "root", root)
        object.__setattr__(instance, "manifest", manifest)
        return instance

    @property
    def identity(self) -> str:
        """返回可写入训练 checkpoint 的 base asset 规范身份。"""

        return self.manifest.spec_identity


@dataclass(frozen=True, slots=True)
class AssetProvenanceRecord:
    """记录不可变资产来源, 不混入离线转换或运行 checkpoint。"""

    source_url: str
    revision: str
    receipt_identity: str

    def __post_init__(self) -> None:
        """校验公开来源与固定身份。"""

        _validate_public_source_url(self.source_url)
        if not _REVISION.fullmatch(self.revision) or not _SHA256.fullmatch(self.receipt_identity):
            raise ModelAssetConfigurationError("asset provenance requires pinned identities")


@dataclass(frozen=True, slots=True)
class AssetLicenseRecord:
    """记录单项资产许可文件和再分发边界。"""

    asset_key: str
    license_name: str
    license_file_path: str
    redistribution: str

    def __post_init__(self) -> None:
        """要求许可身份完整且路径安全。"""

        for name, value in (
            ("asset_key", self.asset_key),
            ("license_name", self.license_name),
            ("redistribution", self.redistribution),
        ):
            if not value.strip():
                raise ModelAssetConfigurationError(f"{name} must not be empty")
        validate_relative_path(self.license_file_path)


@runtime_checkable
class ModelAssetBundle(Protocol):
    """供通用装配消费的已验证、不可变资产包协议。"""

    @property
    def family_key(self) -> str:
        """返回规范家族键。"""

        ...

    @property
    def revision(self) -> str:
        """返回不可变主 revision。"""

        ...

    @property
    def root(self) -> Path:
        """返回主验证资产根。"""

        ...

    @property
    def manifest(self) -> Mapping[str, ModelAssetManifest]:
        """返回按角色组织的验证清单。"""

        ...

    @property
    def assets_by_role(self) -> Mapping[str, ResolvedModelAsset]:
        """返回按角色组织的验证收据。"""

        ...

    @property
    def checkpoint_candidates(self) -> tuple[Path, ...]:
        """返回不可变基础 checkpoint 候选。"""

        ...

    @property
    def tokenizer_or_processor_assets(self) -> tuple[Path, ...]:
        """返回 tokenizer 或 processor 资产。"""

        ...

    @property
    def backbone_assets(self) -> tuple[Path, ...]:
        """返回 backbone 资产。"""

        ...

    @property
    def provenance(self) -> tuple[AssetProvenanceRecord, ...]:
        """返回不可变来源记录。"""

        ...

    @property
    def license_records(self) -> tuple[AssetLicenseRecord, ...]:
        """返回逐资产许可记录。"""

        ...

    @property
    def fingerprint(self) -> str:
        """返回仅绑定不可变资产身份的摘要。"""

        ...

    def validate(self) -> None:
        """重新校验协议内部身份与本地收据关系。"""

        ...


class ModelAssetProvider(Protocol):
    """显式 fetch provider 的最小协议。"""

    name: str

    def fetch(self, spec: ModelAssetSpec, destination: Path) -> ModelAssetAcquisition:
        """把固定 revision 文件写入空 staging 并返回受控获取证据。"""

        ...


def utc_acquisition_timestamp() -> str:
    """生成稳定可解析的 UTC 获取时间文本。"""

    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_spec_json(spec: ModelAssetSpec) -> str:
    """生成不含动态 acquisition 字段的稳定规范 JSON。"""

    payload = {
        "key": spec.key,
        "family_key": spec.family_key,
        "provider": spec.provider,
        "source_url": spec.source_url,
        "public_identifier": spec.public_identifier,
        "repository": spec.repository,
        "revision": spec.revision,
        "license_name": spec.license_name,
        "license_file_path": spec.license_file_path,
        "use_limitation": spec.use_limitation,
        "redistribution": spec.redistribution,
        "checksum_policy": spec.checksum_policy,
        "asset_roles": spec.asset_roles,
        "remote_code_required": spec.remote_code_required,
        "files": [
            {
                "path": item.path,
                "size": item.size,
                "sha256": item.sha256,
                "role": item.role,
            }
            for item in spec.files
        ],
    }
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _validate_public_source_url(value: object) -> None:
    """只接受无凭据、查询串和 fragment 的公开 HTTPS 来源。"""

    if not isinstance(value, str):
        raise ModelAssetConfigurationError("model asset source_url must be a string")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ModelAssetConfigurationError("model asset source_url must be a public HTTPS URL")


def _validate_utc_timestamp(value: object) -> None:
    """要求 acquisition 时间为规范 UTC ISO-8601 文本。"""

    if not isinstance(value, str) or not _UTC_TIMESTAMP.fullmatch(value):
        raise ModelAssetConfigurationError("model asset acquisition timestamp must be UTC ISO-8601")
    try:
        parsed = datetime.fromisoformat(value.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ModelAssetConfigurationError("model asset acquisition timestamp is invalid") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ModelAssetConfigurationError("model asset acquisition timestamp must use UTC")


def _freeze_json_mapping(value: object, path: str) -> Mapping[str, ImmutableJsonValue]:
    """把严格 JSON object 递归冻结为 mapping proxy 与 tuple。"""

    if not isinstance(value, Mapping):
        raise ModelAssetConfigurationError(f"{path} must be a JSON object")
    raw = cast(Mapping[object, object], value)
    if any(not isinstance(key, str) or not key for key in raw):
        raise ModelAssetConfigurationError(f"{path} keys must be non-empty strings")
    frozen = {
        cast(str, key): _freeze_json_value(item, f"{path}.{key}")
        for key, item in sorted(raw.items(), key=lambda pair: cast(str, pair[0]))
    }
    return MappingProxyType(frozen)


def _freeze_json_value(value: object, path: str) -> ImmutableJsonValue:
    """严格拒绝非 JSON 类型与非有限浮点数。"""

    if value is None or isinstance(value, (str, bool)):
        return value
    if type(value) is int:
        return value
    if type(value) is float:
        number = value
        if not math.isfinite(number):
            raise ModelAssetConfigurationError(f"{path} must contain finite JSON numbers")
        return number
    if isinstance(value, Mapping):
        return _freeze_json_mapping(cast(Mapping[object, object], value), path)
    if isinstance(value, (list, tuple)):
        sequence = cast(list[object] | tuple[object, ...], value)
        return tuple(
            _freeze_json_value(item, f"{path}[{index}]") for index, item in enumerate(sequence)
        )
    raise ModelAssetConfigurationError(f"{path} contains a non-JSON value")


def _thaw_json_mapping(
    value: Mapping[str, ImmutableJsonValue],
) -> dict[str, object]:
    """把不可变 JSON 元数据转换为可序列化副本。"""

    return {key: _thaw_json_value(item) for key, item in value.items()}


def _thaw_json_value(value: ImmutableJsonValue) -> object:
    """递归复制不可变 JSON 值, 不暴露内部 mapping proxy。"""

    if isinstance(value, Mapping):
        return {key: _thaw_json_value(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_thaw_json_value(item) for item in value]
    return value
