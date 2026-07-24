"""把已提交的 uv.lock 解析为 M12 精确运行时 lock。"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

try:
    import tomllib as _toml_parser
except ModuleNotFoundError:  # pragma: no cover - Python 3.10 使用项目 dev 依赖
    try:
        import tomli as _toml_parser
    except ModuleNotFoundError:  # pragma: no cover - resolve 会返回稳定错误
        _toml_parser: Any | None = None

from autovla.runtime_profiles.contracts import (
    CudaCompatibilityIntent,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeProfileSpec,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError


def _sha256(path: Path) -> str:
    """流式计算 lock 摘要。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normal_name(name: str) -> str:
    """按 Python distribution 规则统一名称。"""

    return name.lower().replace("_", "-").replace(".", "-")


def _artifact_hashes(package: Mapping[str, object]) -> tuple[str, ...]:
    """收集一个已选 package 记录的全部 sdist/wheel SHA256。"""

    artifacts: list[object] = []
    sdist = package.get("sdist")
    if sdist is not None:
        artifacts.append(sdist)
    wheels = package.get("wheels", [])
    if not isinstance(wheels, list):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package wheels must be an object list"
        )
    artifacts.extend(cast("list[object]", wheels))
    hashes: set[str] = set()
    for artifact in artifacts:
        if not isinstance(artifact, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock artifacts must be objects"
            )
        raw_hash = cast("dict[object, object]", artifact).get("hash")
        if not isinstance(raw_hash, str) or not raw_hash.startswith("sha256:"):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock artifacts require sha256 hashes"
            )
        hashes.add(raw_hash.removeprefix("sha256:"))
    return tuple(sorted(hashes))


def _package_from_record(
    raw_package: Mapping[str, object],
    *,
    source_distribution_version: str,
) -> ResolvedPackage | None:
    """把单个 uv package 记录转换为 distribution;virtual 项目不安装。"""

    raw_name = raw_package.get("name")
    source = raw_package.get("source")
    if not isinstance(raw_name, str) or not raw_name:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package name must be non-empty text"
        )
    if not isinstance(source, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package source must be an object"
        )
    source_mapping = cast("dict[object, object]", source)
    if "virtual" in source_mapping:
        return None
    raw_version = raw_package.get("version")
    if raw_version is None and _normal_name(raw_name) == "autovla":
        raw_version = source_distribution_version
    if not isinstance(raw_version, str) or not raw_version:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID",
            f"installed distribution {raw_name!r} has no exact version",
        )
    return ResolvedPackage(
        name=_normal_name(raw_name),
        version=raw_version,
        artifact_sha256=_artifact_hashes(raw_package),
    )


def resolve_uv_lock(
    *,
    checkout_root: Path,
    profile: RuntimeProfileSpec,
    cuda_compatibility: CudaCompatibilityIntent,
    source_distribution_version: str,
) -> ResolvedRuntimeLock:
    """解析提交内 uv.lock,选择目标画像的唯一 distribution 清单并校验身份。

    输入是不可变 checkout、画像、源码 distribution 版本和显式 CUDA 观测意图;
    输出沿用 M12 ``ResolvedRuntimeLock.v2``,不访问网络也不修改 lock。
    """

    lock_path = checkout_root / profile.uv_project / "uv.lock"
    if not lock_path.is_file() or lock_path.is_symlink():
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_FILE_MISSING", "profile uv.lock must be a regular non-symlink file"
        )
    lock_sha256 = _sha256(lock_path)
    if profile.lock_sha256 is None or lock_sha256 != profile.lock_sha256:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_FILE_MISMATCH", "committed uv.lock does not match the profile digest"
        )
    if _toml_parser is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_UNAVAILABLE",
            "uv.lock resolution requires Python tomllib or the project tomli backport",
        )
    try:
        with lock_path.open("rb") as handle:
            payload = cast(object, _toml_parser.load(handle))
    except (OSError, _toml_parser.TOMLDecodeError) as exc:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "profile uv.lock is not valid TOML"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "profile uv.lock must contain one TOML document"
        )
    lock_mapping = cast("dict[str, object]", payload)
    expected_python = f"=={profile.requested_python_version}.*"
    if lock_mapping.get("requires-python") != expected_python:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PLATFORM_MISMATCH",
            "uv.lock requires-python does not match the runtime profile",
        )
    raw_packages = lock_mapping.get("package")
    if not isinstance(raw_packages, list):
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_TOML_INVALID", "uv.lock package inventory must be an object list"
        )

    candidates: dict[str, list[ResolvedPackage]] = {}
    for raw_package in cast("list[object]", raw_packages):
        if not isinstance(raw_package, dict):
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_TOML_INVALID", "uv.lock package inventory must contain objects"
            )
        package = _package_from_record(
            cast("dict[str, object]", raw_package),
            source_distribution_version=source_distribution_version,
        )
        if package is not None:
            candidates.setdefault(package.name, []).append(package)

    declared = dict(profile.exact_packages)
    packages: list[ResolvedPackage] = []
    for name in sorted(candidates):
        choices = candidates[name]
        if len(choices) == 1:
            packages.append(choices[0])
            continue
        expected_version = declared.get(name)
        selected = [package for package in choices if package.version == expected_version]
        if len(selected) != 1:
            versions = ", ".join(sorted({package.version for package in choices}))
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_DISTRIBUTION_AMBIGUOUS",
                f"{name} has no unique profile-selected version among: {versions}",
            )
        packages.append(selected[0])

    if profile.resolver_version is None or profile.upstream_revision is None:
        raise RuntimeEnvironmentError(
            "RUNTIME_LOCK_PROFILE_INCOMPLETE",
            "profile resolver version and upstream revision are required",
        )
    resolved = ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name=profile.resolver_name,
        resolver_version=profile.resolver_version,
        upstream_revision=profile.upstream_revision,
        lock_sha256=lock_sha256,
        packages=tuple(packages),
        cuda_compatibility=cuda_compatibility,
    )
    resolved.validate_profile(profile)
    return resolved


__all__ = ["resolve_uv_lock"]
