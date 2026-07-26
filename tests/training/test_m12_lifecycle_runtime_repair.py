"""M12 lifecycle repair 的 production runtime resolver 聚焦测试。"""

from __future__ import annotations

import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from autovla.runtime_profiles.contracts import (
    CudaCompatibilityIntent,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentReceipt,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.runtime_profiles.registry import load_runtime_profiles
from autovla.training.runtime import (
    VerifiedProductionTrainingRuntime,
    resolve_verified_training_runtime,
)

ROOT = Path(__file__).resolve().parents[2]


def _lock() -> ResolvedRuntimeLock:
    """构造与 packaged N1D6 声明精确绑定的测试 lock。"""

    profile = load_runtime_profiles()["gr00t_n1d6_runtime"]
    assert profile.resolver_version is not None
    assert profile.upstream_revision is not None
    assert profile.lock_sha256 is not None
    return ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v2",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name=profile.resolver_name,
        resolver_version=profile.resolver_version,
        upstream_revision=profile.upstream_revision,
        lock_sha256=profile.lock_sha256,
        packages=tuple(
            ResolvedPackage(name, version, ()) for name, version in profile.exact_packages
        ),
        cuda_compatibility=CudaCompatibilityIntent(
            schema_version="autovla.cuda_compatibility_intent.v1",
            required=True,
            torch_compiled_cuda_version="12.8",
            cuda_runtime_version="12.8",
            cuda_driver_version="570",
            cudnn_version="9",
            nccl_version="2.27",
            compute_capabilities=("8.0", "9.0"),
        ),
    )


def _environment(lock: ResolvedRuntimeLock) -> RuntimeEnvironmentReceipt:
    """构造与 exact lock 完全一致的 canonical environment receipt。"""

    profile = load_runtime_profiles()[lock.profile_id]
    return RuntimeEnvironmentReceipt(
        schema_version="autovla.runtime_environment_receipt.v1",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        lock_fingerprint=lock.fingerprint,
        source_sha="1" * 40,
        environment_path=f".autovla_envs/{profile.profile_id}",
        installed_packages=tuple((package.name, package.version) for package in lock.packages),
        python_implementation=profile.python_implementation,
        python_version=f"{profile.requested_python_version}.13",
        platform=profile.platform_intent,
        torch_version=dict(profile.exact_packages).get("torch"),
        torch_compiled_cuda_version="12.8",
        cuda_runtime_version="12.8",
        cuda_driver_version="570",
        cudnn_version="9",
        nccl_version="2.27",
        gpu_name="NVIDIA H800",
        gpu_compute_capability="9.0",
        deepspeed_compatible=True,
        offline_flags=(
            ("HF_HUB_OFFLINE", "1"),
            ("PIP_NO_INDEX", "1"),
            ("UV_OFFLINE", "1"),
        ),
        verification_status="pass",
        diagnostics=(),
    )


def test_production_resolver_consumes_exact_lock_and_canonical_receipt() -> None:
    """resolver 只调用 M12 verify,并返回保留精确对象身份的 production 类型。"""

    lock = _lock()
    environment = _environment(lock)
    calls: list[tuple[str, ResolvedRuntimeLock]] = []

    class _Manager:
        """记录 resolver 传入的 exact lock。"""

        def verify(
            self,
            profile_id: str,
            supplied_lock: ResolvedRuntimeLock,
        ) -> RuntimeEnvironmentReceipt:
            """返回预构造 canonical receipt。"""

            calls.append((profile_id, supplied_lock))
            return environment

    resolved = resolve_verified_training_runtime(
        ROOT,
        "gr00t_n1d6",
        lock=lock,
        manager=_Manager(),  # type: ignore[arg-type]
    )

    assert type(resolved) is VerifiedProductionTrainingRuntime
    assert resolved.lock is lock
    assert resolved.environment is environment
    assert calls == [("gr00t_n1d6_runtime", lock)]
    assert resolved.bundle_profile_identity.endswith(lock.fingerprint)


def test_production_runtime_rejects_stale_environment_chain() -> None:
    """environment receipt 不能替换 lock 或声明身份。"""

    lock = _lock()
    stale = replace(_environment(lock), lock_fingerprint="2" * 64)
    with pytest.raises(RuntimeEnvironmentError, match="does not match"):
        VerifiedProductionTrainingRuntime(
            load_runtime_profiles()[lock.profile_id],
            lock,
            stale,
        )


def test_production_resolver_source_has_no_m11_report_dependency() -> None:
    """生产 resolver 源码不得重新调用 M11 compatibility report。"""

    source = inspect.getsource(resolve_verified_training_runtime)
    assert "RuntimeCompatibilityReport" not in source
    assert "legacy_compatibility_report" not in source
    assert "runtime_manager.verify(profile.profile_id, lock)" in source
