"""M12 运行时声明、lock 与收据分层契约测试。"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from autovla.cli.env import main
from autovla.runtime_profiles import (
    CudaCompatibilityIntent,
    FamilyRuntimeProfile,
    OfflineSubprocessRunner,
    ResolvedPackage,
    ResolvedRuntimeLock,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
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
        packages=(ResolvedPackage("jax", "0.4.1", ("3" * 64,)),),
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
        evidence_sha256="7" * 64,
        operation="conversion",
        status="pass",
    )
    payload = receipt.to_dict()
    rendered = json.dumps(payload, sort_keys=True)
    assert payload["command_name"] == "convert"
    assert "test-token-value" not in rendered
    assert RuntimeExecutionReceipt.from_dict(payload) == receipt


def test_execution_receipt_rejects_source_and_evidence_identity_mismatch() -> None:
    """执行收据拒绝源码漂移与非完整证据摘要。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = _lock(profile)
    environment = _environment(profile, lock)
    with pytest.raises(RuntimeEnvironmentError) as source_error:
        RuntimeExecutionReceipt.from_command(
            profile=profile,
            lock=lock,
            environment=environment,
            source_sha="8" * 40,
            asset_fingerprint="5" * 64,
            command=("convert",),
            topology_fingerprint="6" * 64,
            evidence_path="runs/tmp/m12/conversion.json",
            evidence_sha256="7" * 64,
            operation="conversion",
            status="pass",
        )
    assert source_error.value.code == "RUNTIME_EXECUTION_SOURCE_MISMATCH"

    with pytest.raises(RuntimeEnvironmentError, match="full lowercase sha256"):
        RuntimeExecutionReceipt.from_command(
            profile=profile,
            lock=lock,
            environment=environment,
            source_sha=environment.source_sha,
            asset_fingerprint="5" * 64,
            command=("convert",),
            topology_fingerprint="6" * 64,
            evidence_path="runs/tmp/m12/conversion.json",
            evidence_sha256="7" * 12,
            operation="conversion",
            status="pass",
        )


def test_lock_cuda_intent_is_strict_and_profile_bound() -> None:
    """CUDA 意图参与 lock fingerprint、严格解析和 profile 校验。"""

    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = _lock(profile)
    payload = lock.to_dict(include_fingerprint=False)
    cuda_payload = payload["cuda_compatibility"]
    assert isinstance(cuda_payload, dict)
    cuda_payload["required"] = 1
    with pytest.raises(RuntimeEnvironmentError, match="required must be a boolean"):
        ResolvedRuntimeLock.from_dict(payload)

    cuda_profile = load_runtime_profiles()["gr00t_n1d7_runtime"]
    non_cuda_lock = replace(
        lock,
        profile_id=cuda_profile.profile_id,
        profile_fingerprint=cuda_profile.fingerprint,
    )
    with pytest.raises(RuntimeEnvironmentError) as mismatch:
        non_cuda_lock.validate_profile(cuda_profile)
    assert mismatch.value.code == "RUNTIME_LOCK_CUDA_PROFILE_MISMATCH"


def test_real_offline_runner_is_available_without_invocation() -> None:
    """默认 manager 提供真实 runner 能力,构造过程不调用该 runner。"""

    manager = RuntimeEnvironmentManager(source_sha="9" * 40)
    assert isinstance(manager.command_runner, OfflineSubprocessRunner)


def test_canonical_create_consumes_exact_lock_and_plan_marker(tmp_path: Path) -> None:
    """canonical create 只消费传入 lock,并发布同一计划 marker。"""

    (tmp_path / "pyproject.toml").write_text("[project]\nname='fixture'\n", encoding="utf-8")
    project = tmp_path / "envs/model-pi0-5-conversion"
    project.mkdir(parents=True)
    (project / "pyproject.toml").write_text("[project]\nname='runtime'\n", encoding="utf-8")
    lock_path = project / "uv.lock"
    lock_path.write_text("fixture-lock\n", encoding="utf-8")
    profile = load_runtime_profiles()["pi0_5_conversion"]
    lock = replace(
        _lock(profile),
        lock_sha256=hashlib.sha256(lock_path.read_bytes()).hexdigest(),
    )
    calls: list[list[str]] = []

    def fake_runner(
        command: list[str],
        *,
        env: dict[str, str],
        **_: object,
    ) -> subprocess.CompletedProcess[str]:
        """模拟离线 materialization 与严格环境 probe。"""

        calls.append(command)
        if command[0] == "uv":
            environment = Path(env["UV_PROJECT_ENVIRONMENT"])
            (environment / "bin").mkdir(parents=True)
            (environment / "bin/python").write_text("fixture", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        payload = {
            "python_version": "3.10.14",
            "python_implementation": "CPython",
            "platform": "linux-x86_64",
            "packages": {"jax": "0.4.1"},
            "inventory_sha256": "8" * 64,
            "torch_compiled_cuda_version": None,
            "cuda_runtime_version": None,
            "cuda_driver_version": None,
            "cudnn_version": None,
            "nccl_version": None,
            "gpu_name": None,
            "gpu_compute_capability": None,
            "deepspeed_compatible": None,
            "sys_executable": command[0],
            "sys_prefix": str(Path(command[0]).parent.parent),
        }
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(payload), stderr="")

    manager = RuntimeEnvironmentManager(
        tmp_path,
        source_sha="9" * 40,
        runner=fake_runner,
    )
    receipt = manager.create(
        profile.profile_id,
        lock,
        nonce="fixture-canonical",
        allow_create=True,
    )
    marker_path = (
        tmp_path / f".autovla_envs/{profile.profile_id}/.autovla-runtime-profile.json"
    )
    marker = json.loads(marker_path.read_text(encoding="utf-8"))
    assert receipt.lock_fingerprint == lock.fingerprint
    assert marker["lock_fingerprint"] == lock.fingerprint
    assert marker["lock_sha256"] == lock.lock_sha256
    assert calls[0][:3] == ["uv", "sync", "--offline"]
    assert len(calls) == 2


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


def test_canonical_operations_do_not_call_resolve() -> None:
    """create/verify/exec 源码不得把静态解析计划提升为 lock。"""

    source = (ROOT / "autovla/runtime_profiles/manager.py").read_text(encoding="utf-8")
    for method, next_method in (
        ("    def create(", "    def _empty_fingerprint("),
        ("    def verify(", "    @staticmethod\n    def _is_training_command("),
        ("    def exec(", "\n\nclass LegacyRuntimeProfileAdapter:"),
    ):
        body = source.split(method, 1)[1].split(next_method, 1)[0]
        assert "self.resolve(" not in body


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
