"""M12 环境发布的无副作用事务计划。"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from autovla.runtime_profiles.contracts import (
    ResolvedRuntimeLock,
    RuntimeProfileSpec,
    redact_environment,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

_NONCE = re.compile(r"[a-z0-9][a-z0-9-]{5,63}")
_HEX_64 = re.compile(r"[0-9a-f]{64}")
_SOURCE_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")


@dataclass(frozen=True, slots=True)
class EnvironmentPublicationPlan:
    """描述同一文件系统内 staging 到 canonical target 的发布计划。"""

    schema_version: str
    profile_id: str
    profile_fingerprint: str
    lock_fingerprint: str
    source_sha: str
    descriptor_sha256: str
    pyproject_sha256: str
    lock_sha256: str
    project_path: str
    pyproject_path: str
    lock_path: str
    environment_root: str
    environment_path: str
    staging_path: str
    cache_path: str
    marker_path: str
    command: tuple[str, ...]
    child_environment: tuple[tuple[str, str], ...]
    marker: tuple[tuple[str, str], ...]
    publication_steps: tuple[str, ...]

    @classmethod
    def build(
        cls,
        *,
        repository_root: Path,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
        source_sha: str,
        descriptor_sha256: str,
        pyproject_sha256: str,
        nonce: str,
        allow_existing_target: bool = False,
    ) -> "EnvironmentPublicationPlan":
        """验证安全路径并生成不执行命令的确定性计划。"""

        lock.validate_profile(profile)
        if not _SOURCE_SHA.fullmatch(source_sha):
            raise RuntimeEnvironmentError(
                "PUBLICATION_PLAN_INVALID", "source_sha must be a full lowercase source sha"
            )
        for field, value in (
            ("descriptor_sha256", descriptor_sha256),
            ("pyproject_sha256", pyproject_sha256),
        ):
            if not _HEX_64.fullmatch(value):
                raise RuntimeEnvironmentError(
                    "PUBLICATION_PLAN_INVALID", f"{field} must be a full lowercase sha256"
                )
        if not _NONCE.fullmatch(nonce):
            raise RuntimeEnvironmentError(
                "PUBLICATION_PLAN_INVALID", "nonce must be a bounded lowercase token"
            )
        raw_root = repository_root.expanduser()
        if raw_root.is_symlink():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PATH_SYMLINK", "repository root must not be a symbolic link"
            )
        root = raw_root.resolve()
        if root != raw_root.absolute():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PATH_SYMLINK",
                "repository root ancestry must not traverse symbolic links",
            )
        environment_root = root / ".autovla_envs"
        environment_path = environment_root / profile.profile_id
        staging_path = environment_root / f".materializing-{profile.profile_id}-{nonce}"
        for path in (environment_root, environment_path, staging_path):
            if path.is_symlink():
                raise RuntimeEnvironmentError(
                    "ENVIRONMENT_PATH_SYMLINK",
                    "environment root, target, and staging path must not be symbolic links",
                )
        if environment_path.exists() and not allow_existing_target:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_ALREADY_EXISTS", "publication never mutates an existing target"
            )
        if staging_path.exists() and not allow_existing_target:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_STAGING_EXISTS", "publication staging path must be absent"
            )
        project_text = profile.uv_project.as_posix()
        pyproject_text = f"{project_text}/pyproject.toml"
        lock_text = f"{project_text}/uv.lock"
        environment_text = f".autovla_envs/{profile.profile_id}"
        staging_text = f".autovla_envs/.materializing-{profile.profile_id}-{nonce}"
        cache_text = ".autovla_cache/uv"
        marker_text = f"{environment_text}/.autovla-runtime-profile.json"
        child_environment = redact_environment(
            {
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_OFFLINE": "1",
                "PIP_NO_INDEX": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "UV_CACHE_DIR": cache_text,
                "UV_OFFLINE": "1",
                "UV_PROJECT_ENVIRONMENT": staging_text,
                "WANDB_MODE": "disabled",
            }
        )
        marker = tuple(
            sorted(
                {
                    "schema_version": "autovla.runtime_environment_marker.v2",
                    "profile_id": profile.profile_id,
                    "profile_fingerprint": profile.fingerprint,
                    "lock_fingerprint": lock.fingerprint,
                    "lock_sha256": lock.lock_sha256,
                    "source_sha": source_sha,
                    "descriptor_sha256": descriptor_sha256,
                    "pyproject_sha256": pyproject_sha256,
                    "environment_path": environment_text,
                    "lock_path": lock_text,
                }.items()
            )
        )
        return cls(
            schema_version="autovla.environment_publication_plan.v1",
            profile_id=profile.profile_id,
            profile_fingerprint=profile.fingerprint,
            lock_fingerprint=lock.fingerprint,
            source_sha=source_sha,
            descriptor_sha256=descriptor_sha256,
            pyproject_sha256=pyproject_sha256,
            lock_sha256=lock.lock_sha256,
            project_path=project_text,
            pyproject_path=pyproject_text,
            lock_path=lock_text,
            environment_root=".autovla_envs",
            environment_path=environment_text,
            staging_path=staging_text,
            cache_path=cache_text,
            marker_path=marker_text,
            command=(
                "uv",
                "sync",
                "--offline",
                "--locked",
                "--project",
                project_text,
                "--python",
                profile.requested_python_version,
            ),
            child_environment=child_environment,
            marker=marker,
            publication_steps=(
                "acquire_profile_lock",
                "create_absent_sibling_staging",
                "run_fake_or_future_authorized_materializer",
                "verify_staging_inventory",
                "write_and_fsync_marker",
                "fsync_staging_directory",
                "atomic_replace_to_absent_target",
                "fsync_environment_root",
            ),
        )

    def validate_identity(
        self,
        *,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
        source_sha: str,
    ) -> None:
        """要求计划完整绑定声明、lock、源码和规范路径。"""

        lock.validate_profile(profile)
        expected_project = profile.uv_project.as_posix()
        expected_environment = f".autovla_envs/{profile.profile_id}"
        expected_marker = {
            "schema_version": "autovla.runtime_environment_marker.v2",
            "profile_id": profile.profile_id,
            "profile_fingerprint": profile.fingerprint,
            "lock_fingerprint": lock.fingerprint,
            "lock_sha256": lock.lock_sha256,
            "source_sha": source_sha,
            "descriptor_sha256": self.descriptor_sha256,
            "pyproject_sha256": self.pyproject_sha256,
            "environment_path": expected_environment,
            "lock_path": f"{expected_project}/uv.lock",
        }
        if (
            self.profile_id != profile.profile_id
            or self.profile_fingerprint != profile.fingerprint
            or self.lock_fingerprint != lock.fingerprint
            or self.lock_sha256 != lock.lock_sha256
            or self.source_sha != source_sha
            or self.project_path != expected_project
            or self.pyproject_path != f"{expected_project}/pyproject.toml"
            or self.lock_path != f"{expected_project}/uv.lock"
            or self.environment_root != ".autovla_envs"
            or self.environment_path != expected_environment
            or self.cache_path != ".autovla_cache/uv"
            or self.marker_path != f"{expected_environment}/.autovla-runtime-profile.json"
            or dict(self.marker) != expected_marker
        ):
            raise RuntimeEnvironmentError(
                "PUBLICATION_PLAN_IDENTITY_MISMATCH",
                "publication plan does not match the exact declaration and lock identity",
            )

    def to_dict(self) -> dict[str, object]:
        """返回不含主机绝对路径和秘密的计划。"""

        return {
            "schema_version": self.schema_version,
            "profile_id": self.profile_id,
            "profile_fingerprint": self.profile_fingerprint,
            "lock_fingerprint": self.lock_fingerprint,
            "source_sha": self.source_sha,
            "descriptor_sha256": self.descriptor_sha256,
            "pyproject_sha256": self.pyproject_sha256,
            "lock_sha256": self.lock_sha256,
            "project_path": self.project_path,
            "pyproject_path": self.pyproject_path,
            "lock_path": self.lock_path,
            "environment_root": self.environment_root,
            "environment_path": self.environment_path,
            "staging_path": self.staging_path,
            "cache_path": self.cache_path,
            "marker_path": self.marker_path,
            "command": list(self.command),
            "child_environment": dict(self.child_environment),
            "marker": dict(self.marker),
            "publication_steps": list(self.publication_steps),
        }


__all__ = ["EnvironmentPublicationPlan"]
