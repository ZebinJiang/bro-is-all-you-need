"""M12 环境发布计划的安全路径与事务边界测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from autovla.runtime_profiles import (
    CudaCompatibilityIntent,
    EnvironmentPublicationPlan,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentError,
    RuntimeProfileSpec,
    load_runtime_profiles,
)


def _lock(profile: RuntimeProfileSpec) -> ResolvedRuntimeLock:
    """构造发布计划使用的最小精确 lock。"""

    return ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name="uv",
        resolver_version="0.8.1",
        upstream_revision="1" * 40,
        lock_sha256="2" * 64,
        packages=tuple(
            ResolvedPackage(name, version, ()) for name, version in profile.exact_packages
        ),
        cuda_compatibility=CudaCompatibilityIntent(
            schema_version="autovla.cuda_compatibility_intent.v1",
            required=False,
            torch_compiled_cuda_version=None,
            cuda_runtime_version=None,
            cuda_driver_version=None,
            cudnn_version=None,
            nccl_version=None,
            compute_capabilities=(),
        ),
    )


def _plan(root: Path) -> EnvironmentPublicationPlan:
    """生成固定 nonce 的无副作用发布计划。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    return EnvironmentPublicationPlan.build(
        repository_root=root,
        profile=profile,
        lock=_lock(profile),
        source_sha="3" * 40,
        descriptor_sha256="4" * 64,
        pyproject_sha256="5" * 64,
        nonce="fixture-0001",
    )


def test_publication_plan_is_deterministic_and_does_not_create_paths(tmp_path: Path) -> None:
    """规划不落盘,且明确同文件系统原子发布与 fsync 顺序。"""

    first = _plan(tmp_path)
    second = _plan(tmp_path)
    assert first == second
    assert first.environment_path == (
        f".autovla_envs/pi0_5_conversion/{first.lock_fingerprint}/.venv"
    )
    assert first.lock_path == "envs/model-pi0-5-conversion/uv.lock"
    assert first.lock_sha256 == "2" * 64
    assert dict(first.marker)["lock_fingerprint"] == first.lock_fingerprint
    assert first.staging_path.startswith(
        f".autovla_envs/pi0_5_conversion/.materializing-{first.lock_fingerprint}-"
    )
    assert "atomic_replace_to_absent_target" in first.publication_steps
    assert "fsync_environment_root" in first.publication_steps
    assert not (tmp_path / ".autovla_envs").exists()
    assert not (tmp_path / ".autovla_cache").exists()


def test_publication_plan_rejects_existing_target(tmp_path: Path) -> None:
    """既有 canonical target 永不被更新或覆盖。"""

    target = tmp_path / ".autovla_envs/pi0_5_conversion" / _plan(tmp_path).lock_fingerprint
    target.mkdir(parents=True)
    with pytest.raises(RuntimeEnvironmentError, match="never mutates"):
        _plan(tmp_path)


def test_publication_plan_rejects_symlink_root(tmp_path: Path) -> None:
    """环境根符号链接在任何 staging 计划生成前失败关闭。"""

    external = tmp_path / "external"
    external.mkdir()
    (tmp_path / ".autovla_envs").symlink_to(external, target_is_directory=True)
    with pytest.raises(RuntimeEnvironmentError, match="symbolic links"):
        _plan(tmp_path)
