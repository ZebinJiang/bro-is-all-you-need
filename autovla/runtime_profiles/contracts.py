"""AutoVLA 家族运行时环境的类型化契约。"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from autovla.runtime_profiles.errors import RuntimeEnvironmentError

ProfileKind = Literal["training_runtime", "conversion"]
CompatibilityStatus = Literal["pass", "fail"]
_PROFILE_ID = re.compile(r"[a-z0-9][a-z0-9_]*")


def _stable_hash(payload: object) -> str:
    """返回不受映射插入顺序影响的 SHA256。"""

    encoded = json.dumps(
        payload,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class FamilyRuntimeProfile:
    """描述一个家族运行时或隔离转换环境的静态真相。

    该类型只声明环境项目、精确已知版本和显式 blocker，不导入模型、
    不打开数据集，也不把版本范围提升为受支持版本。
    """

    profile_id: str
    family_key: str
    kind: ProfileKind
    descriptor_path: Path
    uv_project: Path
    requested_python_version: str
    lock_status: str
    lock_sha256: str | None
    exact_packages: tuple[tuple[str, str], ...]
    prohibited_packages: tuple[str, ...]
    blockers: tuple[str, ...]
    asset_license_gate_status: str
    requires_cuda: bool

    def __post_init__(self) -> None:
        """拒绝模糊身份、重复包和转换环境训练冒充。"""

        if not _PROFILE_ID.fullmatch(self.profile_id) or not _PROFILE_ID.fullmatch(
            self.family_key
        ):
            raise RuntimeEnvironmentError("PROFILE_INVALID", "profile and family ids are required")
        if self.kind not in {"training_runtime", "conversion"}:
            raise RuntimeEnvironmentError("PROFILE_INVALID", "unsupported profile kind")
        names = tuple(name for name, _ in self.exact_packages)
        if len(names) != len(set(names)):
            raise RuntimeEnvironmentError("PROFILE_INVALID", "exact package names must be unique")
        if any(not name or not version for name, version in self.exact_packages):
            raise RuntimeEnvironmentError("PROFILE_INVALID", "exact package pins must be complete")
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

    @property
    def is_training_runtime(self) -> bool:
        """仅对生产训练画像返回真。"""

        return self.kind == "training_runtime"

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
            "exact_packages": dict(self.exact_packages),
            "prohibited_packages": list(self.prohibited_packages),
            "blockers": list(self.blockers),
            "asset_license_gate_status": self.asset_license_gate_status,
            "requires_cuda": self.requires_cuda,
            "is_training_runtime": self.is_training_runtime,
        }


@dataclass(frozen=True, slots=True)
class RuntimeEnvironmentSpec:
    """绑定仓库根、固定环境根和单一画像目标路径。"""

    repository_root: Path
    profile: FamilyRuntimeProfile
    environment_root: Path
    environment_path: Path

    @classmethod
    def for_profile(
        cls,
        repository_root: Path,
        profile: FamilyRuntimeProfile,
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
        """返回相对仓库路径，避免泄露主机绝对路径。"""

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
        """环境未实现时返回空，否则计算节点实现身份。"""

        if self.python_executable is None:
            return None
        return _stable_hash(self.to_dict(include_fingerprints=False))

    def to_dict(self, *, include_fingerprints: bool = True) -> dict[str, object]:
        """序列化 fingerprint，不记录代理、令牌或外部绝对路径。"""

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
            "installed_distribution_inventory_sha256": (
                self.installed_distribution_inventory_sha256
            ),
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
class RuntimeDiagnostic:
    """稳定错误码或警告码。"""

    code: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """返回 JSON-safe 诊断。"""

        return {"code": self.code, "message": self.message}


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
    "FamilyRuntimeProfile",
    "RuntimeCompatibilityReport",
    "RuntimeDiagnostic",
    "RuntimeEnvironmentFingerprint",
    "RuntimeEnvironmentSpec",
    "canonical_report_json",
]
