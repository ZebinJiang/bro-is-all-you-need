"""AutoVLA 家族运行时环境的类型化契约。"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

from autovla.runtime_profiles.errors import RuntimeEnvironmentError

ProfileKind = Literal["training_runtime", "conversion"]
CompatibilityStatus = Literal["pass", "fail"]
VerificationStatus = Literal["pass", "fail"]
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9_]*")
_PACKAGE_NAME = re.compile(r"[a-z0-9][a-z0-9._-]*")
_PACKAGE_VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9.!+_-]*")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_SOURCE_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_SCHEMA_PROFILE = "autovla.runtime_profile_spec.v2"
_SCHEMA_CUDA_INTENT = "autovla.cuda_compatibility_intent.v1"
_SCHEMA_LOCK = "autovla.resolved_runtime_lock.v2"
_SCHEMA_ENVIRONMENT = "autovla.runtime_environment_receipt.v1"
_SCHEMA_EXECUTION = "autovla.runtime_execution_receipt.v2"
_SENSITIVE_ENV_PARTS = (
    "ACCESS_KEY",
    "API_KEY",
    "AUTH",
    "CREDENTIAL",
    "PASSWORD",
    "PROXY",
    "SECRET",
    "TOKEN",
)
_RUNTIME_OPERATIONS = frozenset(
    {
        "backward",
        "checkpoint_load",
        "checkpoint_save",
        "construction",
        "conversion",
        "data_binding",
        "decode",
        "forward",
        "optimizer_step",
        "prediction",
        "processor",
        "profiling",
        "resume",
    }
)


def _stable_hash(payload: object) -> str:
    """返回不受映射插入顺序影响的 SHA256。"""

    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_non_empty(value: str, field: str) -> None:
    """拒绝空文本和首尾空白。"""

    if not value or value != value.strip():
        raise RuntimeEnvironmentError("RUNTIME_CONTRACT_INVALID", f"{field} must be non-empty")


def _require_sha256(value: str, field: str) -> None:
    """要求完整小写 SHA256,避免部分摘要进入身份链。"""

    if not _HEX_64.fullmatch(value):
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_INVALID", f"{field} must be a full lowercase sha256"
        )


def _require_source_sha(value: str, field: str = "source_sha") -> None:
    """要求完整 Git SHA-1 或 SHA-256。"""

    if not _SOURCE_SHA.fullmatch(value):
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_INVALID", f"{field} must be a full lowercase source sha"
        )


def _require_relative_path(value: str, field: str, *, prefix: str | None = None) -> None:
    """拒绝绝对路径、遍历、空段和非规范路径。"""

    path = Path(value)
    if (
        not value
        or path.is_absolute()
        or value != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
        or (prefix is not None and not value.startswith(prefix))
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_PATH_INVALID", f"{field} must be a canonical repository-relative path"
        )


def _strict_mapping(
    payload: Mapping[str, object],
    expected_fields: frozenset[str],
    *,
    contract: str,
) -> dict[str, object]:
    """复制严格映射并拒绝缺字段和未知字段。"""

    values = dict(payload)
    missing = sorted(expected_fields - values.keys())
    unknown = sorted(values.keys() - expected_fields)
    if missing or unknown:
        details: list[str] = []
        if missing:
            details.append(f"missing={','.join(missing)}")
        if unknown:
            details.append(f"unknown={','.join(unknown)}")
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_FIELDS_INVALID",
            f"{contract} fields are invalid: {'; '.join(details)}",
        )
    return values


def _mapping_string(values: Mapping[str, object], field: str) -> str:
    """读取严格非空字符串。"""

    value = values[field]
    if not isinstance(value, str):
        raise RuntimeEnvironmentError("RUNTIME_CONTRACT_INVALID", f"{field} must be a string")
    _require_non_empty(value, field)
    return value


def _mapping_optional_string(values: Mapping[str, object], field: str) -> str | None:
    """读取严格可空字符串。"""

    value = values[field]
    if value is None:
        return None
    if not isinstance(value, str):
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_INVALID", f"{field} must be a string or null"
        )
    _require_non_empty(value, field)
    return value


def _mapping_bool(values: Mapping[str, object], field: str) -> bool:
    """读取严格布尔值并拒绝 bool-as-int 的相邻混淆。"""

    value = values[field]
    if type(value) is not bool:
        raise RuntimeEnvironmentError("RUNTIME_CONTRACT_INVALID", f"{field} must be a boolean")
    return value


def _mapping_strings(values: Mapping[str, object], field: str) -> tuple[str, ...]:
    """读取严格字符串数组。"""

    value = values[field]
    if not isinstance(value, list):
        raise RuntimeEnvironmentError("RUNTIME_CONTRACT_INVALID", f"{field} must be a string list")
    raw_items = cast("list[object]", value)
    if not all(isinstance(item, str) and item and item == item.strip() for item in raw_items):
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_INVALID", f"{field} must be a non-empty string list"
        )
    return tuple(cast("list[str]", raw_items))


def _mapping_pairs(values: Mapping[str, object], field: str) -> tuple[tuple[str, str], ...]:
    """读取字符串到字符串的严格映射并按键排序。"""

    value = values[field]
    if not isinstance(value, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_CONTRACT_INVALID", f"{field} must be a string mapping"
        )
    raw_mapping = cast("dict[object, object]", value)
    pairs: list[tuple[str, str]] = []
    for key, item in raw_mapping.items():
        if not isinstance(key, str) or not isinstance(item, str):
            raise RuntimeEnvironmentError(
                "RUNTIME_CONTRACT_INVALID", f"{field} must be a string mapping"
            )
        _require_non_empty(key, field)
        _require_non_empty(item, field)
        pairs.append((key, item))
    if len(pairs) != len({key for key, _ in pairs}):
        raise RuntimeEnvironmentError("RUNTIME_CONTRACT_INVALID", f"{field} keys must be unique")
    return tuple(sorted(pairs))


def redact_environment(environment: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    """删除代理、令牌、凭据和 Python 注入变量并稳定排序。"""

    retained: list[tuple[str, str]] = []
    for key, value in environment.items():
        upper = key.upper()
        if upper in {"PYTHONHOME", "PYTHONPATH"} or any(
            part in upper for part in _SENSITIVE_ENV_PARTS
        ):
            continue
        retained.append((key, value))
    return tuple(sorted(retained))


@dataclass(frozen=True, slots=True)
class RuntimeProfileSpec:
    """描述声明层的家族运行时约束。

    M11 lock 字段只作为兼容读取信息保留,不会构造
    :class:`ResolvedRuntimeLock`,也不会证明环境已经实现。
    """

    profile_id: str
    family_key: str
    kind: ProfileKind
    descriptor_path: Path
    uv_project: Path
    requested_python_version: str
    lock_status: str
    lock_sha256: str | None
    lock_accepted: bool
    exact_packages: tuple[tuple[str, str], ...]
    observed_lock_packages: tuple[tuple[str, str], ...]
    prohibited_packages: tuple[str, ...]
    blockers: tuple[str, ...]
    asset_license_gate_status: str
    requires_cuda: bool
    schema_version: str = _SCHEMA_PROFILE
    python_implementation: str = "CPython"
    platform_intent: str = "linux-x86_64"
    resolver_name: str = "uv"
    resolver_version: str | None = None
    upstream_revision: str | None = None

    def __post_init__(self) -> None:
        """拒绝模糊身份、重复包和转换环境训练冒充。"""

        if not _PROFILE_ID.fullmatch(self.profile_id) or not _PROFILE_ID.fullmatch(self.family_key):
            raise RuntimeEnvironmentError("PROFILE_INVALID", "profile and family ids are required")
        if self.kind not in {"training_runtime", "conversion"}:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "unsupported profile kind")
        names = tuple(name for name, _ in self.exact_packages)
        if (
            names != tuple(sorted(names))
            or len(names) != len(set(names))
            or any(not _PACKAGE_NAME.fullmatch(name) for name in names)
        ):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "exact package names must be normalized, unique, and sorted"
            )
        if any(not _PACKAGE_VERSION.fullmatch(version) for _, version in self.exact_packages):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "exact package pins must use exact versions"
            )
        observed_names = tuple(name for name, _ in self.observed_lock_packages)
        if (
            observed_names != tuple(sorted(observed_names))
            or len(observed_names) != len(set(observed_names))
            or any(not _PACKAGE_NAME.fullmatch(name) for name in observed_names)
            or any(
                not _PACKAGE_VERSION.fullmatch(version)
                for _, version in self.observed_lock_packages
            )
        ):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID",
                "observed lock package records must be exact, unique, and sorted",
            )
        if (
            self.prohibited_packages != tuple(sorted(self.prohibited_packages))
            or len(self.prohibited_packages) != len(set(self.prohibited_packages))
            or any(not _PACKAGE_NAME.fullmatch(name) for name in self.prohibited_packages)
        ):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "prohibited packages must be normalized, unique, and sorted"
            )
        if any(not blocker or blocker != blocker.strip() for blocker in self.blockers):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "runtime blockers must be non-empty text"
            )
        if type(self.lock_accepted) is not bool:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "lock_accepted must be boolean")
        if self.lock_sha256 is not None:
            _require_sha256(self.lock_sha256, "lock_sha256")
        if self.lock_accepted and (self.lock_sha256 is None or self.blockers):
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "accepted lock requires a digest and no blockers"
            )
        if self.kind == "conversion" and self.requires_cuda:
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", "conversion profile cannot require CUDA"
            )
        for name, path in (
            ("descriptor_path", self.descriptor_path),
            ("uv_project", self.uv_project),
        ):
            if path.is_absolute() or ".." in path.parts or "." in path.parts:
                raise RuntimeEnvironmentError(
                    "PROFILE_INVALID", f"{name} must be a canonical repository-relative path"
                )
        if self.schema_version != _SCHEMA_PROFILE:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "unsupported profile schema")
        for field, value in (
            ("requested_python_version", self.requested_python_version),
            ("python_implementation", self.python_implementation),
            ("platform_intent", self.platform_intent),
            ("resolver_name", self.resolver_name),
            ("asset_license_gate_status", self.asset_license_gate_status),
            ("lock_status", self.lock_status),
        ):
            _require_non_empty(value, field)
        if self.resolver_version is not None:
            _require_non_empty(self.resolver_version, "resolver_version")
        if self.upstream_revision is not None:
            _require_source_sha(self.upstream_revision, "upstream_revision")
        if type(self.requires_cuda) is not bool:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "requires_cuda must be boolean")

    @property
    def is_training_runtime(self) -> bool:
        """仅对生产训练画像返回真。"""

        return self.kind == "training_runtime"

    @property
    def fingerprint(self) -> str:
        """返回仅由声明层字段生成的稳定身份。"""

        return _stable_hash(self.to_spec_dict())

    def to_spec_dict(self) -> dict[str, object]:
        """返回不含 lock 实现状态的规范 M12 声明。"""

        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "family_key": self.family_key,
            "kind": self.kind,
            "descriptor_path": self.descriptor_path.as_posix(),
            "uv_project": self.uv_project.as_posix(),
            "requested_python_version": self.requested_python_version,
            "python_implementation": self.python_implementation,
            "platform_intent": self.platform_intent,
            "resolver_name": self.resolver_name,
            "resolver_version": self.resolver_version,
            "upstream_revision": self.upstream_revision,
            "declared_packages": dict(self.exact_packages),
            "prohibited_packages": list(self.prohibited_packages),
            "requires_cuda": self.requires_cuda,
        }

    def to_dict(self) -> dict[str, object]:
        """返回稳定、无密钥的 JSON 结构。"""

        return {
            "profile_id": self.profile_id,
            "family_key": self.family_key,
            "kind": self.kind,
            "descriptor_path": self.descriptor_path.as_posix(),
            "uv_project": self.uv_project.as_posix(),
            "requested_python_version": self.requested_python_version,
            "lock_status": self.lock_status,
            "lock_sha256": self.lock_sha256,
            "lock_accepted": self.lock_accepted,
            "exact_packages": dict(self.exact_packages),
            "observed_lock_packages": dict(self.observed_lock_packages),
            "prohibited_packages": list(self.prohibited_packages),
            "blockers": list(self.blockers),
            "asset_license_gate_status": self.asset_license_gate_status,
            "requires_cuda": self.requires_cuda,
            "is_training_runtime": self.is_training_runtime,
            "schema_version": self.schema_version,
            "python_implementation": self.python_implementation,
            "platform_intent": self.platform_intent,
            "resolver_name": self.resolver_name,
            "resolver_version": self.resolver_version,
            "upstream_revision": self.upstream_revision,
            "profile_fingerprint": self.fingerprint,
        }

    @classmethod
    def from_spec_dict(cls, payload: Mapping[str, object]) -> "RuntimeProfileSpec":
        """严格读取纯声明层记录,不从中推断 lock。"""

        fields = frozenset(
            {
                "schema_version",
                "profile_id",
                "family_key",
                "kind",
                "descriptor_path",
                "uv_project",
                "requested_python_version",
                "python_implementation",
                "platform_intent",
                "resolver_name",
                "resolver_version",
                "upstream_revision",
                "declared_packages",
                "prohibited_packages",
                "requires_cuda",
            }
        )
        values = _strict_mapping(payload, fields, contract="runtime profile spec")
        kind = _mapping_string(values, "kind")
        if kind not in {"training_runtime", "conversion"}:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "unsupported profile kind")
        return cls(
            profile_id=_mapping_string(values, "profile_id"),
            family_key=_mapping_string(values, "family_key"),
            kind=cast("ProfileKind", kind),
            descriptor_path=Path(_mapping_string(values, "descriptor_path")),
            uv_project=Path(_mapping_string(values, "uv_project")),
            requested_python_version=_mapping_string(values, "requested_python_version"),
            lock_status="declaration_only",
            lock_sha256=None,
            lock_accepted=False,
            exact_packages=_mapping_pairs(values, "declared_packages"),
            observed_lock_packages=(),
            prohibited_packages=tuple(sorted(_mapping_strings(values, "prohibited_packages"))),
            blockers=("resolved runtime lock is not attached to a declaration",),
            asset_license_gate_status="separate_receipt_required",
            requires_cuda=_mapping_bool(values, "requires_cuda"),
            schema_version=_mapping_string(values, "schema_version"),
            python_implementation=_mapping_string(values, "python_implementation"),
            platform_intent=_mapping_string(values, "platform_intent"),
            resolver_name=_mapping_string(values, "resolver_name"),
            resolver_version=_mapping_optional_string(values, "resolver_version"),
            upstream_revision=_mapping_optional_string(values, "upstream_revision"),
        )


FamilyRuntimeProfile = RuntimeProfileSpec


@dataclass(frozen=True, slots=True)
class ResolvedPackage:
    """记录一个精确 distribution 及可用制品摘要。"""

    name: str
    version: str
    artifact_sha256: tuple[str, ...]

    def __post_init__(self) -> None:
        """规范化包身份并拒绝版本范围和无效摘要。"""

        if not _PACKAGE_NAME.fullmatch(self.name) or self.name != self.name.lower():
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_INVALID", "package name must be normalized lowercase text"
            )
        _require_non_empty(self.version, "package.version")
        if not _PACKAGE_VERSION.fullmatch(self.version):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_INVALID", "resolved package version must be exact"
            )
        if self.artifact_sha256 != tuple(sorted(self.artifact_sha256)) or len(
            self.artifact_sha256
        ) != len(set(self.artifact_sha256)):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_INVALID", "artifact hashes must be unique and sorted"
            )
        for digest in self.artifact_sha256:
            _require_sha256(digest, "package.artifact_sha256")

    def to_dict(self) -> dict[str, object]:
        """返回稳定包记录。"""

        return {
            "name": self.name,
            "version": self.version,
            "artifact_sha256": list(self.artifact_sha256),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ResolvedPackage":
        """严格解析单个包记录。"""

        values = _strict_mapping(
            payload,
            frozenset({"name", "version", "artifact_sha256"}),
            contract="resolved package",
        )
        return cls(
            name=_mapping_string(values, "name"),
            version=_mapping_string(values, "version"),
            artifact_sha256=_mapping_strings(values, "artifact_sha256"),
        )


@dataclass(frozen=True, slots=True)
class CudaCompatibilityIntent:
    """记录 lock 解析时选择的显式 CUDA 兼容目标。"""

    schema_version: str
    required: bool
    torch_compiled_cuda_version: str | None
    cuda_runtime_version: str | None
    cuda_driver_version: str | None
    cudnn_version: str | None
    nccl_version: str | None
    compute_capabilities: tuple[str, ...]

    def __post_init__(self) -> None:
        """拒绝缺失的 CUDA 目标、隐式布尔值和非确定性能力集合。"""

        if self.schema_version != _SCHEMA_CUDA_INTENT:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_CUDA_INTENT_INVALID", "unsupported CUDA intent schema"
            )
        if type(self.required) is not bool:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_CUDA_INTENT_INVALID", "required must be a boolean"
            )
        version_values = (
            self.torch_compiled_cuda_version,
            self.cuda_runtime_version,
            self.cuda_driver_version,
            self.cudnn_version,
            self.nccl_version,
        )
        if self.required:
            if any(value is None for value in version_values) or not self.compute_capabilities:
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_CUDA_INTENT_INVALID",
                    "CUDA locks require complete version and compute capability intent",
                )
        elif any(value is not None for value in version_values) or self.compute_capabilities:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_CUDA_INTENT_INVALID",
                "non-CUDA locks must not carry CUDA compatibility intent",
            )
        for field, value in (
            ("torch_compiled_cuda_version", self.torch_compiled_cuda_version),
            ("cuda_runtime_version", self.cuda_runtime_version),
            ("cuda_driver_version", self.cuda_driver_version),
            ("cudnn_version", self.cudnn_version),
            ("nccl_version", self.nccl_version),
        ):
            if value is not None:
                _require_non_empty(value, field)
        if (
            self.compute_capabilities != tuple(sorted(self.compute_capabilities))
            or len(self.compute_capabilities) != len(set(self.compute_capabilities))
            or any(not value or value != value.strip() for value in self.compute_capabilities)
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_CUDA_INTENT_INVALID",
                "compute capabilities must be non-empty, unique, and sorted",
            )

    def to_dict(self) -> dict[str, object]:
        """返回稳定 CUDA 兼容目标。"""

        return {
            "schema_version": self.schema_version,
            "required": self.required,
            "torch_compiled_cuda_version": self.torch_compiled_cuda_version,
            "cuda_runtime_version": self.cuda_runtime_version,
            "cuda_driver_version": self.cuda_driver_version,
            "cudnn_version": self.cudnn_version,
            "nccl_version": self.nccl_version,
            "compute_capabilities": list(self.compute_capabilities),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "CudaCompatibilityIntent":
        """严格解析 CUDA 兼容目标。"""

        values = _strict_mapping(
            payload,
            frozenset(
                {
                    "schema_version",
                    "required",
                    "torch_compiled_cuda_version",
                    "cuda_runtime_version",
                    "cuda_driver_version",
                    "cudnn_version",
                    "nccl_version",
                    "compute_capabilities",
                }
            ),
            contract="CUDA compatibility intent",
        )
        return cls(
            schema_version=_mapping_string(values, "schema_version"),
            required=_mapping_bool(values, "required"),
            torch_compiled_cuda_version=_mapping_optional_string(
                values, "torch_compiled_cuda_version"
            ),
            cuda_runtime_version=_mapping_optional_string(values, "cuda_runtime_version"),
            cuda_driver_version=_mapping_optional_string(values, "cuda_driver_version"),
            cudnn_version=_mapping_optional_string(values, "cudnn_version"),
            nccl_version=_mapping_optional_string(values, "nccl_version"),
            compute_capabilities=tuple(sorted(_mapping_strings(values, "compute_capabilities"))),
        )


@dataclass(frozen=True, slots=True)
class ResolvedRuntimeLock:
    """记录解析层的精确、不可变 lock 身份。"""

    schema_version: str
    profile_id: str
    profile_fingerprint: str
    python_version: str
    python_implementation: str
    platform_intent: str
    resolver_name: str
    resolver_version: str
    upstream_revision: str
    lock_sha256: str
    packages: tuple[ResolvedPackage, ...]
    cuda_compatibility: CudaCompatibilityIntent

    def __post_init__(self) -> None:
        """拒绝模糊 profile、部分摘要、重复包和非确定性排序。"""

        if self.schema_version != _SCHEMA_LOCK:
            raise RuntimeEnvironmentError("RUNTIME_LOCK_INVALID", "unsupported lock schema")
        if not _PROFILE_ID.fullmatch(self.profile_id):
            raise RuntimeEnvironmentError("RUNTIME_LOCK_INVALID", "profile_id is invalid")
        _require_sha256(self.profile_fingerprint, "profile_fingerprint")
        _require_sha256(self.lock_sha256, "lock_sha256")
        _require_source_sha(self.upstream_revision, "upstream_revision")
        for field, value in (
            ("python_version", self.python_version),
            ("python_implementation", self.python_implementation),
            ("platform_intent", self.platform_intent),
            ("resolver_name", self.resolver_name),
            ("resolver_version", self.resolver_version),
        ):
            _require_non_empty(value, field)
        names = tuple(package.name for package in self.packages)
        if not names or names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_INVALID", "packages must be non-empty, unique, and sorted by name"
            )

    @property
    def fingerprint(self) -> str:
        """计算 portable lock 身份。"""

        return _stable_hash(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        """返回精确 lock 的稳定 JSON 结构。"""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_fingerprint": self.profile_fingerprint,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "platform_intent": self.platform_intent,
            "resolver_name": self.resolver_name,
            "resolver_version": self.resolver_version,
            "upstream_revision": self.upstream_revision,
            "lock_sha256": self.lock_sha256,
            "packages": [package.to_dict() for package in self.packages],
            "cuda_compatibility": self.cuda_compatibility.to_dict(),
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "ResolvedRuntimeLock":
        """严格解析 lock 并校验可选派生 fingerprint。"""

        fields = frozenset(
            {
                "schema_version",
                "profile_id",
                "profile_fingerprint",
                "python_version",
                "python_implementation",
                "platform_intent",
                "resolver_name",
                "resolver_version",
                "upstream_revision",
                "lock_sha256",
                "packages",
                "cuda_compatibility",
            }
        )
        raw_values = dict(payload)
        stored_fingerprint = raw_values.pop("fingerprint", None)
        values = _strict_mapping(raw_values, fields, contract="resolved runtime lock")
        raw_packages = values["packages"]
        if not isinstance(raw_packages, list):
            raise RuntimeEnvironmentError("RUNTIME_LOCK_INVALID", "packages must be an object list")
        packages: list[ResolvedPackage] = []
        for raw_package in cast("list[object]", raw_packages):
            if not isinstance(raw_package, dict):
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_INVALID", "packages must be an object list"
                )
            packages.append(ResolvedPackage.from_dict(cast("dict[str, object]", raw_package)))
        raw_cuda_compatibility = values["cuda_compatibility"]
        if not isinstance(raw_cuda_compatibility, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_INVALID", "cuda_compatibility must be an object"
            )
        parsed = cls(
            schema_version=_mapping_string(values, "schema_version"),
            profile_id=_mapping_string(values, "profile_id"),
            profile_fingerprint=_mapping_string(values, "profile_fingerprint"),
            python_version=_mapping_string(values, "python_version"),
            python_implementation=_mapping_string(values, "python_implementation"),
            platform_intent=_mapping_string(values, "platform_intent"),
            resolver_name=_mapping_string(values, "resolver_name"),
            resolver_version=_mapping_string(values, "resolver_version"),
            upstream_revision=_mapping_string(values, "upstream_revision"),
            lock_sha256=_mapping_string(values, "lock_sha256"),
            packages=tuple(packages),
            cuda_compatibility=CudaCompatibilityIntent.from_dict(
                cast("dict[str, object]", raw_cuda_compatibility)
            ),
        )
        if stored_fingerprint is not None:
            if not isinstance(stored_fingerprint, str) or stored_fingerprint != parsed.fingerprint:
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_FINGERPRINT_MISMATCH",
                    "stored lock fingerprint does not match canonical content",
                )
        return parsed

    def validate_profile(self, profile: RuntimeProfileSpec) -> None:
        """要求 lock 与声明身份和平台意图完全一致。"""

        if self.profile_id != profile.profile_id or self.profile_fingerprint != profile.fingerprint:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_PROFILE_MISMATCH", "lock does not match the profile declaration"
            )
        if (
            self.python_version != profile.requested_python_version
            or self.python_implementation != profile.python_implementation
            or self.platform_intent != profile.platform_intent
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_PLATFORM_MISMATCH",
                "lock Python or platform intent does not match the profile",
            )
        if self.cuda_compatibility.required is not profile.requires_cuda:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_CUDA_PROFILE_MISMATCH",
                "lock CUDA intent does not match the profile declaration",
            )
        installed = {package.name: package.version for package in self.packages}
        for name, version in profile.exact_packages:
            if installed.get(name) != version:
                raise RuntimeEnvironmentError(
                    "RUNTIME_LOCK_DECLARATION_MISMATCH",
                    f"{name} does not match the declared exact version",
                )
        leaked = sorted(set(installed).intersection(profile.prohibited_packages))
        if leaked:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_PROHIBITED_PACKAGE",
                f"prohibited packages are present: {', '.join(leaked)}",
            )


@dataclass(frozen=True, slots=True)
class RuntimeDiagnostic:
    """稳定错误码或警告码。"""

    code: str
    message: str

    def __post_init__(self) -> None:
        """拒绝空诊断和疑似秘密值。"""

        _require_non_empty(self.code, "diagnostic.code")
        _require_non_empty(self.message, "diagnostic.message")
        if any(part.lower() in self.message.lower() for part in ("hf_", "api_key=", "token=")):
            raise RuntimeEnvironmentError(
                "RUNTIME_RECEIPT_SECRET", "diagnostic must not contain credentials"
            )

    def to_dict(self) -> dict[str, str]:
        """返回 JSON-safe 诊断。"""

        return {"code": self.code, "message": self.message}

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RuntimeDiagnostic":
        """严格读取稳定诊断。"""

        values = _strict_mapping(
            payload,
            frozenset({"code", "message"}),
            contract="runtime diagnostic",
        )
        return cls(
            code=_mapping_string(values, "code"),
            message=_mapping_string(values, "message"),
        )


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentReceipt:
    """记录实现层环境与 portable lock 的精确绑定。"""

    schema_version: str
    profile_id: str
    profile_fingerprint: str
    lock_fingerprint: str
    source_sha: str
    environment_path: str
    installed_packages: tuple[tuple[str, str], ...]
    python_implementation: str
    python_version: str
    platform: str
    torch_version: str | None
    torch_compiled_cuda_version: str | None
    cuda_runtime_version: str | None
    cuda_driver_version: str | None
    cudnn_version: str | None
    nccl_version: str | None
    gpu_name: str | None
    gpu_compute_capability: str | None
    deepspeed_compatible: bool | None
    offline_flags: tuple[tuple[str, str], ...]
    verification_status: VerificationStatus
    diagnostics: tuple[RuntimeDiagnostic, ...]

    def __post_init__(self) -> None:
        """验证环境路径、精确包清单、状态和身份摘要。"""

        if self.schema_version != _SCHEMA_ENVIRONMENT:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID", "unsupported environment schema"
            )
        if not _PROFILE_ID.fullmatch(self.profile_id):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID", "profile_id is invalid"
            )
        _require_sha256(self.profile_fingerprint, "profile_fingerprint")
        _require_sha256(self.lock_fingerprint, "lock_fingerprint")
        _require_source_sha(self.source_sha)
        _require_relative_path(
            self.environment_path,
            "environment_path",
            prefix=f".autovla_envs/{self.profile_id}",
        )
        if self.environment_path != f".autovla_envs/{self.profile_id}":
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "environment_path must exactly match the canonical profile target",
            )
        names = tuple(name for name, _ in self.installed_packages)
        if not names or names != tuple(sorted(names)) or len(names) != len(set(names)):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "installed packages must be non-empty, unique, and sorted",
            )
        for name, version in self.installed_packages:
            if not _PACKAGE_NAME.fullmatch(name) or not version:
                raise RuntimeEnvironmentError(
                    "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                    "installed package inventory is invalid",
                )
        for field, value in (
            ("python_implementation", self.python_implementation),
            ("python_version", self.python_version),
            ("platform", self.platform),
        ):
            _require_non_empty(value, field)
        for field, value in (
            ("torch_version", self.torch_version),
            ("torch_compiled_cuda_version", self.torch_compiled_cuda_version),
            ("cuda_runtime_version", self.cuda_runtime_version),
            ("cuda_driver_version", self.cuda_driver_version),
            ("cudnn_version", self.cudnn_version),
            ("nccl_version", self.nccl_version),
            ("gpu_name", self.gpu_name),
            ("gpu_compute_capability", self.gpu_compute_capability),
        ):
            if value is not None:
                _require_non_empty(value, field)
        if self.deepspeed_compatible is not None and type(self.deepspeed_compatible) is not bool:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "deepspeed_compatible must be boolean or null",
            )
        if self.verification_status not in {"pass", "fail"}:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID", "verification_status is invalid"
            )
        if self.verification_status == "pass" and self.diagnostics:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "passing receipt cannot carry failure diagnostics",
            )
        if self.diagnostics != tuple(
            sorted(self.diagnostics, key=lambda item: (item.code, item.message))
        ) or len(self.diagnostics) != len(set(self.diagnostics)):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "diagnostics must be unique and deterministically sorted",
            )
        if redact_environment(dict(self.offline_flags)) != self.offline_flags:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "offline flags contain sensitive or unsorted entries",
            )
        required_offline = {
            "HF_HUB_OFFLINE": "1",
            "PIP_NO_INDEX": "1",
            "UV_OFFLINE": "1",
        }
        observed_offline = dict(self.offline_flags)
        if any(observed_offline.get(key) != value for key, value in required_offline.items()):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "environment receipt must preserve required offline flags",
            )

    @property
    def inventory_fingerprint(self) -> str:
        """返回精确已安装 distribution 清单身份。"""

        return _stable_hash(dict(self.installed_packages))

    @property
    def fingerprint(self) -> str:
        """返回 realized environment 身份。"""

        return _stable_hash(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        """序列化环境收据且不写主机绝对路径。"""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_fingerprint": self.profile_fingerprint,
            "lock_fingerprint": self.lock_fingerprint,
            "source_sha": self.source_sha,
            "environment_path": self.environment_path,
            "installed_packages": dict(self.installed_packages),
            "installed_inventory_fingerprint": self.inventory_fingerprint,
            "python_implementation": self.python_implementation,
            "python_version": self.python_version,
            "platform": self.platform,
            "torch_version": self.torch_version,
            "torch_compiled_cuda_version": self.torch_compiled_cuda_version,
            "cuda_runtime_version": self.cuda_runtime_version,
            "cuda_driver_version": self.cuda_driver_version,
            "cudnn_version": self.cudnn_version,
            "nccl_version": self.nccl_version,
            "gpu_name": self.gpu_name,
            "gpu_compute_capability": self.gpu_compute_capability,
            "deepspeed_compatible": self.deepspeed_compatible,
            "offline_flags": dict(self.offline_flags),
            "verification_status": self.verification_status,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    def validate_lock(self, lock: ResolvedRuntimeLock) -> None:
        """要求环境收据来自完全相同的 profile 与 lock。"""

        if (
            self.profile_id != lock.profile_id
            or self.profile_fingerprint != lock.profile_fingerprint
            or self.lock_fingerprint != lock.fingerprint
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_LOCK_MISMATCH",
                "environment receipt does not match the resolved lock",
            )
        observed = dict(self.installed_packages)
        expected = {package.name: package.version for package in lock.packages}
        if observed != expected:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_INVENTORY_MISMATCH",
                "installed inventory does not exactly match the resolved lock",
            )
        if "deepspeed" in expected and self.deepspeed_compatible is not True:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_DEEPSPEED_UNVERIFIED",
                "DeepSpeed lock requires an explicit compatible observation",
            )
        cuda_intent = lock.cuda_compatibility
        observed_cuda = (
            self.torch_compiled_cuda_version,
            self.cuda_runtime_version,
            self.cuda_driver_version,
            self.cudnn_version,
            self.nccl_version,
        )
        expected_cuda = (
            cuda_intent.torch_compiled_cuda_version,
            cuda_intent.cuda_runtime_version,
            cuda_intent.cuda_driver_version,
            cuda_intent.cudnn_version,
            cuda_intent.nccl_version,
        )
        if cuda_intent.required and (
            observed_cuda != expected_cuda
            or self.gpu_compute_capability not in cuda_intent.compute_capabilities
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_CUDA_INTENT_MISMATCH",
                "realized CUDA observations do not match the resolved lock intent",
            )

    def validate_profile(self, profile: RuntimeProfileSpec) -> None:
        """要求环境 profile 身份一致,并在执行前关闭 CUDA 观测缺口。"""

        if self.profile_id != profile.profile_id or self.profile_fingerprint != profile.fingerprint:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PROFILE_MISMATCH",
                "environment receipt does not match the profile declaration",
            )
        if profile.requires_cuda and any(
            value is None
            for value in (
                self.torch_compiled_cuda_version,
                self.cuda_runtime_version,
                self.cuda_driver_version,
                self.cudnn_version,
                self.nccl_version,
                self.gpu_name,
                self.gpu_compute_capability,
            )
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_CUDA_UNVERIFIED",
                "CUDA profile execution requires complete compute-node observations",
            )

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RuntimeEnvironmentReceipt":
        """严格解析 realized environment 收据并校验派生摘要。"""

        fields = frozenset(
            {
                "schema_version",
                "profile_id",
                "profile_fingerprint",
                "lock_fingerprint",
                "source_sha",
                "environment_path",
                "installed_packages",
                "python_implementation",
                "python_version",
                "platform",
                "torch_version",
                "torch_compiled_cuda_version",
                "cuda_runtime_version",
                "cuda_driver_version",
                "cudnn_version",
                "nccl_version",
                "gpu_name",
                "gpu_compute_capability",
                "deepspeed_compatible",
                "offline_flags",
                "verification_status",
                "diagnostics",
            }
        )
        raw_values = dict(payload)
        stored_fingerprint = raw_values.pop("fingerprint", None)
        stored_inventory = raw_values.pop("installed_inventory_fingerprint", None)
        values = _strict_mapping(raw_values, fields, contract="runtime environment receipt")
        raw_diagnostics = values["diagnostics"]
        if not isinstance(raw_diagnostics, list):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID", "diagnostics must be an object list"
            )
        diagnostics: list[RuntimeDiagnostic] = []
        for raw_diagnostic in cast("list[object]", raw_diagnostics):
            if not isinstance(raw_diagnostic, dict):
                raise RuntimeEnvironmentError(
                    "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                    "diagnostics must be an object list",
                )
            diagnostics.append(
                RuntimeDiagnostic.from_dict(cast("dict[str, object]", raw_diagnostic))
            )
        status = _mapping_string(values, "verification_status")
        if status not in {"pass", "fail"}:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID", "verification_status is invalid"
            )
        deepspeed = values["deepspeed_compatible"]
        if deepspeed is not None and type(deepspeed) is not bool:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_RECEIPT_INVALID",
                "deepspeed_compatible must be boolean or null",
            )
        parsed = cls(
            schema_version=_mapping_string(values, "schema_version"),
            profile_id=_mapping_string(values, "profile_id"),
            profile_fingerprint=_mapping_string(values, "profile_fingerprint"),
            lock_fingerprint=_mapping_string(values, "lock_fingerprint"),
            source_sha=_mapping_string(values, "source_sha"),
            environment_path=_mapping_string(values, "environment_path"),
            installed_packages=_mapping_pairs(values, "installed_packages"),
            python_implementation=_mapping_string(values, "python_implementation"),
            python_version=_mapping_string(values, "python_version"),
            platform=_mapping_string(values, "platform"),
            torch_version=_mapping_optional_string(values, "torch_version"),
            torch_compiled_cuda_version=_mapping_optional_string(
                values, "torch_compiled_cuda_version"
            ),
            cuda_runtime_version=_mapping_optional_string(values, "cuda_runtime_version"),
            cuda_driver_version=_mapping_optional_string(values, "cuda_driver_version"),
            cudnn_version=_mapping_optional_string(values, "cudnn_version"),
            nccl_version=_mapping_optional_string(values, "nccl_version"),
            gpu_name=_mapping_optional_string(values, "gpu_name"),
            gpu_compute_capability=_mapping_optional_string(values, "gpu_compute_capability"),
            deepspeed_compatible=deepspeed,
            offline_flags=_mapping_pairs(values, "offline_flags"),
            verification_status=cast("VerificationStatus", status),
            diagnostics=tuple(diagnostics),
        )
        if stored_inventory is not None and stored_inventory != parsed.inventory_fingerprint:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_INVENTORY_FINGERPRINT_MISMATCH",
                "stored inventory fingerprint does not match canonical content",
            )
        if stored_fingerprint is not None and stored_fingerprint != parsed.fingerprint:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_FINGERPRINT_MISMATCH",
                "stored environment fingerprint does not match canonical content",
            )
        return parsed


@dataclass(frozen=True, slots=True)
class RuntimeExecutionReceipt:
    """记录执行层的完整身份链,但不保存命令参数或秘密。"""

    schema_version: str
    profile_id: str
    profile_fingerprint: str
    lock_fingerprint: str
    environment_fingerprint: str
    source_sha: str
    asset_fingerprint: str
    command_name: str
    command_fingerprint: str
    topology_fingerprint: str
    evidence_path: str
    evidence_sha256: str
    operation: str
    status: VerificationStatus
    diagnostics: tuple[RuntimeDiagnostic, ...]

    def __post_init__(self) -> None:
        """拒绝不完整身份、绝对证据路径和自相矛盾状态。"""

        if self.schema_version != _SCHEMA_EXECUTION:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID", "unsupported execution schema"
            )
        if not _PROFILE_ID.fullmatch(self.profile_id):
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID", "profile_id is invalid"
            )
        for field, value in (
            ("profile_fingerprint", self.profile_fingerprint),
            ("lock_fingerprint", self.lock_fingerprint),
            ("environment_fingerprint", self.environment_fingerprint),
            ("asset_fingerprint", self.asset_fingerprint),
            ("command_fingerprint", self.command_fingerprint),
            ("topology_fingerprint", self.topology_fingerprint),
            ("evidence_sha256", self.evidence_sha256),
        ):
            _require_sha256(value, field)
        _require_source_sha(self.source_sha)
        _require_non_empty(self.command_name, "command_name")
        if Path(self.command_name).name != self.command_name:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID",
                "command_name must not contain a host path",
            )
        _require_relative_path(self.evidence_path, "evidence_path", prefix="runs/")
        if self.operation not in _RUNTIME_OPERATIONS:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID", "operation is not a canonical token"
            )
        if self.status not in {"pass", "fail"}:
            raise RuntimeEnvironmentError("RUNTIME_EXECUTION_RECEIPT_INVALID", "status is invalid")
        if self.status == "pass" and self.diagnostics:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID",
                "passing execution cannot carry failure diagnostics",
            )
        if self.diagnostics != tuple(
            sorted(self.diagnostics, key=lambda item: (item.code, item.message))
        ) or len(self.diagnostics) != len(set(self.diagnostics)):
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID",
                "diagnostics must be unique and deterministically sorted",
            )

    @classmethod
    def from_command(
        cls,
        *,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
        environment: RuntimeEnvironmentReceipt,
        source_sha: str,
        asset_fingerprint: str,
        command: Sequence[str],
        topology_fingerprint: str,
        evidence_path: str,
        evidence_sha256: str,
        operation: str,
        status: VerificationStatus,
        diagnostics: tuple[RuntimeDiagnostic, ...] = (),
    ) -> "RuntimeExecutionReceipt":
        """从命令生成仅含名称和摘要的收据,不保存参数。"""

        if not command:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID", "command is required"
            )
        lock.validate_profile(profile)
        environment.validate_lock(lock)
        environment.validate_profile(profile)
        if source_sha != environment.source_sha:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_SOURCE_MISMATCH",
                "execution source_sha does not match the realized environment",
            )
        if environment.verification_status != "pass":
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_ENVIRONMENT_INVALID",
                "execution requires a passing environment receipt",
            )
        return cls(
            schema_version=_SCHEMA_EXECUTION,
            profile_id=profile.profile_id,
            profile_fingerprint=profile.fingerprint,
            lock_fingerprint=lock.fingerprint,
            environment_fingerprint=environment.fingerprint,
            source_sha=source_sha,
            asset_fingerprint=asset_fingerprint,
            command_name=Path(command[0]).name,
            command_fingerprint=_stable_hash(list(command)),
            topology_fingerprint=topology_fingerprint,
            evidence_path=evidence_path,
            evidence_sha256=evidence_sha256,
            operation=operation,
            status=status,
            diagnostics=diagnostics,
        )

    @property
    def fingerprint(self) -> str:
        """返回执行收据身份。"""

        return _stable_hash(self.to_dict(include_fingerprint=False))

    def to_dict(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        """返回无命令参数、秘密和主机路径的稳定 JSON。"""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_fingerprint": self.profile_fingerprint,
            "lock_fingerprint": self.lock_fingerprint,
            "environment_fingerprint": self.environment_fingerprint,
            "source_sha": self.source_sha,
            "asset_fingerprint": self.asset_fingerprint,
            "command_name": self.command_name,
            "command_fingerprint": self.command_fingerprint,
            "topology_fingerprint": self.topology_fingerprint,
            "evidence_path": self.evidence_path,
            "evidence_sha256": self.evidence_sha256,
            "operation": self.operation,
            "status": self.status,
            "diagnostics": [diagnostic.to_dict() for diagnostic in self.diagnostics],
        }
        if include_fingerprint:
            payload["fingerprint"] = self.fingerprint
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, object]) -> "RuntimeExecutionReceipt":
        """严格读取执行收据并校验派生摘要。"""

        fields = frozenset(
            {
                "schema_version",
                "profile_id",
                "profile_fingerprint",
                "lock_fingerprint",
                "environment_fingerprint",
                "source_sha",
                "asset_fingerprint",
                "command_name",
                "command_fingerprint",
                "topology_fingerprint",
                "evidence_path",
                "evidence_sha256",
                "operation",
                "status",
                "diagnostics",
            }
        )
        raw_values = dict(payload)
        stored_fingerprint = raw_values.pop("fingerprint", None)
        values = _strict_mapping(raw_values, fields, contract="runtime execution receipt")
        raw_diagnostics = values["diagnostics"]
        if not isinstance(raw_diagnostics, list):
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_RECEIPT_INVALID", "diagnostics must be an object list"
            )
        diagnostics: list[RuntimeDiagnostic] = []
        for raw_diagnostic in cast("list[object]", raw_diagnostics):
            if not isinstance(raw_diagnostic, dict):
                raise RuntimeEnvironmentError(
                    "RUNTIME_EXECUTION_RECEIPT_INVALID",
                    "diagnostics must be an object list",
                )
            diagnostics.append(
                RuntimeDiagnostic.from_dict(cast("dict[str, object]", raw_diagnostic))
            )
        status = _mapping_string(values, "status")
        if status not in {"pass", "fail"}:
            raise RuntimeEnvironmentError("RUNTIME_EXECUTION_RECEIPT_INVALID", "status is invalid")
        parsed = cls(
            schema_version=_mapping_string(values, "schema_version"),
            profile_id=_mapping_string(values, "profile_id"),
            profile_fingerprint=_mapping_string(values, "profile_fingerprint"),
            lock_fingerprint=_mapping_string(values, "lock_fingerprint"),
            environment_fingerprint=_mapping_string(values, "environment_fingerprint"),
            source_sha=_mapping_string(values, "source_sha"),
            asset_fingerprint=_mapping_string(values, "asset_fingerprint"),
            command_name=_mapping_string(values, "command_name"),
            command_fingerprint=_mapping_string(values, "command_fingerprint"),
            topology_fingerprint=_mapping_string(values, "topology_fingerprint"),
            evidence_path=_mapping_string(values, "evidence_path"),
            evidence_sha256=_mapping_string(values, "evidence_sha256"),
            operation=_mapping_string(values, "operation"),
            status=cast("VerificationStatus", status),
            diagnostics=tuple(diagnostics),
        )
        if stored_fingerprint is not None and stored_fingerprint != parsed.fingerprint:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_FINGERPRINT_MISMATCH",
                "stored execution fingerprint does not match canonical content",
            )
        return parsed


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentSpec:
    """绑定仓库根、固定环境根和单一画像目标路径。"""

    repository_root: Path
    profile: RuntimeProfileSpec
    environment_root: Path
    environment_path: Path

    @classmethod
    def for_profile(
        cls,
        repository_root: Path,
        profile: RuntimeProfileSpec,
    ) -> "RuntimeEnvironmentSpec":
        """只构造 ``.autovla_envs/<profile-id>`` 规范路径。"""

        root = repository_root.resolve()
        environment_root = root / ".autovla_envs"
        return cls(
            repository_root=root,
            profile=profile,
            environment_root=environment_root,
            environment_path=environment_root / profile.profile_id,
        )

    def validate(self) -> None:
        """拒绝外部路径、符号链接根和任何自定义环境布局。"""

        expected_root = self.repository_root / ".autovla_envs"
        expected_path = expected_root / self.profile.profile_id
        if self.environment_root != expected_root or self.environment_path != expected_path:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PATH_INVALID",
                "environment path must be .autovla_envs/<profile-id>",
            )
        if self.environment_root.is_symlink() or self.environment_path.is_symlink():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PATH_SYMLINK",
                "environment root and target must not be symbolic links",
            )

    def to_dict(self) -> dict[str, str]:
        """返回相对仓库路径,避免泄露主机绝对路径。"""

        return {
            "environment_root": ".autovla_envs",
            "environment_path": f".autovla_envs/{self.profile.profile_id}",
        }


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentFingerprint:
    """记录 portable lock 与已实现环境的稳定身份。"""

    schema_version: str
    source_sha: str
    profile_id: str
    profile_descriptor_sha256: str
    pyproject_sha256: str | None
    uv_lock_sha256: str | None
    requested_python_version: str
    environment_path: str
    python_executable: str | None
    python_version: str | None
    python_implementation: str | None
    platform: str | None
    observed_packages: tuple[tuple[str, str], ...]
    installed_distribution_inventory_sha256: str | None
    torch_compiled_cuda_version: str | None
    cuda_runtime_version: str | None
    cuda_driver_version: str | None
    cudnn_version: str | None
    nccl_version: str | None
    gpu_name: str | None
    gpu_compute_capability: str | None
    offline_flags: tuple[tuple[str, str], ...]

    @property
    def portable_lock_fingerprint(self) -> str:
        """计算不依赖当前节点的 lock 身份。"""

        return _stable_hash(
            {
                "schema_version": self.schema_version,
                "source_sha": self.source_sha,
                "profile_id": self.profile_id,
                "profile_descriptor_sha256": self.profile_descriptor_sha256,
                "pyproject_sha256": self.pyproject_sha256,
                "uv_lock_sha256": self.uv_lock_sha256,
                "requested_python_version": self.requested_python_version,
            }
        )

    @property
    def realized_runtime_fingerprint(self) -> str | None:
        """环境未实现时返回空,否则计算节点实现身份。"""

        if self.python_executable is None:
            return None
        return _stable_hash(self.to_dict(include_fingerprints=False))

    def to_dict(self, *, include_fingerprints: bool = True) -> dict[str, object]:
        """序列化 fingerprint,不记录代理、令牌或外部绝对路径。"""

        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "source_sha": self.source_sha,
            "profile_id": self.profile_id,
            "profile_descriptor_sha256": self.profile_descriptor_sha256,
            "pyproject_sha256": self.pyproject_sha256,
            "uv_lock_sha256": self.uv_lock_sha256,
            "requested_python_version": self.requested_python_version,
            "environment_path": self.environment_path,
            "python_executable": self.python_executable,
            "python_version": self.python_version,
            "python_implementation": self.python_implementation,
            "platform": self.platform,
            "observed_packages": dict(self.observed_packages),
            "installed_distribution_inventory_sha256": self.installed_distribution_inventory_sha256,
            "torch_compiled_cuda_version": self.torch_compiled_cuda_version,
            "cuda_runtime_version": self.cuda_runtime_version,
            "cuda_driver_version": self.cuda_driver_version,
            "cudnn_version": self.cudnn_version,
            "nccl_version": self.nccl_version,
            "gpu_name": self.gpu_name,
            "gpu_compute_capability": self.gpu_compute_capability,
            "offline_flags": dict(self.offline_flags),
        }
        if include_fingerprints:
            payload["portable_lock_fingerprint"] = self.portable_lock_fingerprint
            payload["realized_runtime_fingerprint"] = self.realized_runtime_fingerprint
        return payload


@dataclass(frozen=True, slots=True)
class RuntimeCompatibilityReport:
    """现有环境的确定性 fail-closed 兼容报告。"""

    schema_version: str
    profile_id: str
    source_sha: str
    fingerprint: RuntimeEnvironmentFingerprint
    expected_versions: tuple[tuple[str, str], ...]
    observed_versions: tuple[tuple[str, str], ...]
    path_isolation_checks: tuple[tuple[str, bool], ...]
    prohibited_dependency_checks: tuple[tuple[str, bool], ...]
    cuda_compatibility_checks: tuple[tuple[str, bool], ...]
    asset_and_license_gate_status: str
    errors: tuple[RuntimeDiagnostic, ...]
    warnings: tuple[RuntimeDiagnostic, ...]
    status: CompatibilityStatus

    @property
    def is_compatible(self) -> bool:
        """仅在无错误且状态为 pass 时返回真。"""

        return self.status == "pass" and not self.errors

    def to_dict(self) -> dict[str, object]:
        """返回字段顺序无关且不含秘密的报告。"""

        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "source_sha": self.source_sha,
            "portable_lock_fingerprint": self.fingerprint.portable_lock_fingerprint,
            "realized_runtime_fingerprint": self.fingerprint.realized_runtime_fingerprint,
            "fingerprint": self.fingerprint.to_dict(),
            "expected_versions_or_constraints": dict(self.expected_versions),
            "observed_versions": dict(self.observed_versions),
            "path_isolation_checks": dict(self.path_isolation_checks),
            "prohibited_dependency_checks": dict(self.prohibited_dependency_checks),
            "cuda_compatibility_checks": dict(self.cuda_compatibility_checks),
            "asset_and_license_gate_status": self.asset_and_license_gate_status,
            "errors_with_stable_codes": [item.to_dict() for item in self.errors],
            "warnings_with_stable_codes": [item.to_dict() for item in self.warnings],
            "status": self.status,
        }


def canonical_report_json(report: RuntimeCompatibilityReport) -> str:
    """输出可重复比较的紧凑报告 JSON。"""

    return json.dumps(report.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


__all__ = [
    "CudaCompatibilityIntent",
    "FamilyRuntimeProfile",
    "ResolvedPackage",
    "ResolvedRuntimeLock",
    "RuntimeCompatibilityReport",
    "RuntimeDiagnostic",
    "RuntimeEnvironmentFingerprint",
    "RuntimeEnvironmentReceipt",
    "RuntimeEnvironmentSpec",
    "RuntimeExecutionReceipt",
    "RuntimeProfileSpec",
    "canonical_report_json",
    "redact_environment",
]
