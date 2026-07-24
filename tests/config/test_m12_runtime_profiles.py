"""M12 运行时声明、lock 与收据分层契约测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from autovla.cli.env import main
from autovla.runtime_profiles import (
    FamilyRuntimeProfile,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentError,
    RuntimeEnvironmentReceipt,
    RuntimeExecutionReceipt,
    RuntimeProfileSpec,
    load_runtime_profiles,
    redact_environment,
)

ROOT = Path(__file__).resolve().parents[2]


def _lock(profile: RuntimeProfileSpec) -> ResolvedRuntimeLock:
    """构造与 Pi0.5 转换声明匹配的最小精确 lock。"""

    return ResolvedRuntimeLock(
        schema_version="autovla.resolved_runtime_lock.v1",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        python_version=profile.requested_python_version,
        python_implementation=profile.python_implementation,
        platform_intent=profile.platform_intent,
        resolver_name="uv",
        resolver_version="0.8.1",
        upstream_revision="1" * 40,
        lock_sha256="2" * 64,
        packages=(ResolvedPackage("jax", "0.4.1", ("3" * 64,)),),
    )


def _environment(
    profile: RuntimeProfileSpec,
    lock: ResolvedRuntimeLock,
) -> RuntimeEnvironmentReceipt:
    """构造精确匹配 lock 的通过环境收据。"""

    return RuntimeEnvironmentReceipt(
        schema_version="autovla.runtime_environment_receipt.v1",
        profile_id=profile.profile_id,
        profile_fingerprint=profile.fingerprint,
        lock_fingerprint=lock.fingerprint,
        source_sha="4" * 40,
        environment_path=f".autovla_envs/{profile.profile_id}",
        installed_packages=(("jax", "0.4.1"),),
        python_implementation="CPython",
        python_version="3.10.14",
        platform="linux-x86_64",
        torch_version=None,
        torch_compiled_cuda_version=None,
        cuda_runtime_version=None,
        cuda_driver_version=None,
        cudnn_version=None,
        nccl_version=None,
        gpu_name=None,
        gpu_compute_capability=None,
        deepspeed_compatible=None,
        offline_flags=(
            ("HF_HUB_OFFLINE", "1"),
            ("PIP_NO_INDEX", "1"),
            ("UV_OFFLINE", "1"),
        ),
        verification_status="pass",
        diagnostics=(),
    )


def test_profile_spec_is_canonical_and_legacy_name_is_alias() -> None:
    """旧 FamilyRuntimeProfile 名称只映射到唯一 M12 声明类型。"""

    assert FamilyRuntimeProfile is RuntimeProfileSpec
    profile = load_runtime_profiles()["pi0_5_conversion"]
    assert isinstance(profile, RuntimeProfileSpec)
    parsed = RuntimeProfileSpec.from_spec_dict(profile.to_spec_dict())
    assert parsed.fingerprint == profile.fingerprint
    assert parsed.lock_accepted is False
    assert parsed.lock_sha256 is None


def test_profile_registry_rejects_unknown_fields_and_bool_as_int() -> None:
    """动态声明边界拒绝未知字段和整数冒充布尔值。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    payload = profile.to_spec_dict()
    payload["unknown"] = "value"
    with pytest.raises(RuntimeEnvironmentError, match="unknown=unknown"):
        RuntimeProfileSpec.from_spec_dict(payload)

    payload = profile.to_spec_dict()
    payload["requires_cuda"] = 0
    with pytest.raises(RuntimeEnvironmentError, match="requires_cuda must be a boolean"):
        RuntimeProfileSpec.from_spec_dict(payload)


def test_resolved_lock_is_strict_stable_and_profile_bound() -> None:
    """精确 lock 稳定往返且拒绝部分摘要、未知字段和陈旧声明。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = _lock(profile)
    assert ResolvedRuntimeLock.from_dict(lock.to_dict()) == lock
    assert ResolvedRuntimeLock.from_dict(lock.to_dict()).fingerprint == lock.fingerprint

    unknown = lock.to_dict(include_fingerprint=False)
    unknown["extra"] = True
    with pytest.raises(RuntimeEnvironmentError, match="unknown=extra"):
        ResolvedRuntimeLock.from_dict(unknown)

    partial = lock.to_dict(include_fingerprint=False)
    partial["lock_sha256"] = "2" * 12
    with pytest.raises(RuntimeEnvironmentError, match="full lowercase sha256"):
        ResolvedRuntimeLock.from_dict(partial)

    stale_profile = RuntimeProfileSpec.from_spec_dict(
        {
            **profile.to_spec_dict(),
            "platform_intent": "linux-aarch64",
        }
    )
    with pytest.raises(RuntimeEnvironmentError, match="does not match the profile"):
        lock.validate_profile(stale_profile)


def test_environment_receipt_is_strict_and_lock_bound() -> None:
    """环境收据拒绝非规范路径、bool-as-int 和精确清单漂移。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = _lock(profile)
    receipt = _environment(profile, lock)
    assert RuntimeEnvironmentReceipt.from_dict(receipt.to_dict()) == receipt
    receipt.validate_lock(lock)

    absolute = receipt.to_dict(include_fingerprint=False)
    absolute.pop("installed_inventory_fingerprint")
    absolute["environment_path"] = "/tmp/environment"
    with pytest.raises(RuntimeEnvironmentError, match="canonical repository-relative"):
        RuntimeEnvironmentReceipt.from_dict(absolute)

    malformed_bool = receipt.to_dict(include_fingerprint=False)
    malformed_bool.pop("installed_inventory_fingerprint")
    malformed_bool["deepspeed_compatible"] = 1
    with pytest.raises(RuntimeEnvironmentError, match="boolean or null"):
        RuntimeEnvironmentReceipt.from_dict(malformed_bool)

    drifted = replace(receipt, installed_packages=(("jax", "0.4.2"),))
    with pytest.raises(RuntimeEnvironmentError, match="does not exactly match"):
        drifted.validate_lock(lock)


def test_execution_receipt_binds_all_identities_without_command_secret() -> None:
    """执行收据只保存命令名称与摘要并稳定严格往返。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = _lock(profile)
    environment = _environment(profile, lock)
    receipt = RuntimeExecutionReceipt.from_command(
        profile=profile,
        lock=lock,
        environment=environment,
        source_sha="4" * 40,
        asset_fingerprint="5" * 64,
        command=("/opt/private/bin/convert", "--token", "test-token-value"),
        topology_fingerprint="6" * 64,
        evidence_path="runs/tmp/m12/conversion.json",
        operation="conversion",
        status="pass",
    )
    payload = receipt.to_dict()
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["command_name"] == "convert"
    assert "test-token-value" not in rendered
    assert RuntimeExecutionReceipt.from_dict(payload) == receipt


def test_secret_and_proxy_environment_redaction_is_complete() -> None:
    """子进程环境删除代理、令牌、凭据与 Python 注入变量。"""

    sanitized = dict(
        redact_environment(
            {
                "PATH": "/usr/bin",
                "ALL_PROXY": "proxy",
                "http_proxy": "proxy",
                "HF_TOKEN": "secret",
                "CUSTOM_CREDENTIAL": "secret",
                "WANDB_API_KEY": "secret",
                "PYTHONPATH": "/outside",
                "SAFE_FLAG": "1",
            }
        )
    )
    assert sanitized == {"PATH": "/usr/bin", "SAFE_FLAG": "1"}


def test_cli_resolve_is_static_and_does_not_create_lock(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """resolve 只输出确定性计划,不要求 checkout 或 resolver。"""

    assert main(["resolve", "pi0_5_conversion"]) == 0
    payload = json.loads(capsys.readouterr().out)["result"]
    assert payload["network_used"] is False
    assert payload["lock_created"] is False
    assert payload["status"] == "blocked_static_planning_only"


def test_fresh_import_does_not_load_runtime_or_network_clients() -> None:
    """轻量导入不得级联 Torch、uv、模型包或网络客户端。"""

    script = """
import json
import sys
import autovla.runtime_profiles
blocked = ["torch", "uv", "requests", "huggingface_hub", "transformers"]
print(json.dumps([name for name in blocked if name in sys.modules]))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT,
        check=True,
        text=True,
        capture_output=True,
    )
    assert json.loads(completed.stdout) == []
