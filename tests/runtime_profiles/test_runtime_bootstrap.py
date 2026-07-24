"""M13 workspace 全局运行时 bootstrap 缺陷回归测试。"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from autovla.runtime_profiles import (
    CudaCompatibilityIntent,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
)
from autovla.runtime_profiles.manager import _PROBE

ROOT = Path(__file__).resolve().parents[2]


def _cuda_intent(required: bool = True) -> CudaCompatibilityIntent:
    """构造不声称已执行 CUDA 的显式解析输入。"""

    return CudaCompatibilityIntent(
        schema_version="autovla.cuda_compatibility_intent.v1",
        required=required,
        torch_compiled_cuda_version="12.8" if required else None,
        cuda_runtime_version="12.8" if required else None,
        cuda_driver_version="570.00" if required else None,
        cudnn_version="9.7.1" if required else None,
        nccl_version="2.26.2" if required else None,
        compute_capabilities=("8.0",) if required else (),
    )


class _RecordingRunner:
    """记录 cache 子进程边界,不执行 uv。"""

    def __init__(self) -> None:
        self.calls: list[tuple[list[str], dict[str, str]]] = []

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """返回成功结果并保留命令和环境副本。"""

        del cwd, check, text, capture_output
        self.calls.append((list(command), dict(env)))
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")


class _MaterializingRunner:
    """模拟 uv 与隔离 probe,用于验证物理发布布局。"""

    def __init__(self) -> None:
        self.packages: dict[str, str] = {}

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """只创建测试解释器占位并返回精确运行观测。"""

        del cwd, check, text, capture_output
        if command[:2] == ["uv", "sync"]:
            python = Path(env["UV_PROJECT_ENVIRONMENT"]) / "bin" / "python"
            python.parent.mkdir(parents=True)
            python.write_text("#!/bin/sh\n", encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
        probe = {
            "python_version": "3.10.13",
            "python_implementation": "CPython",
            "platform": "manylinux_2_31_x86_64",
            "packages": self.packages,
            "torch_compiled_cuda_version": "12.8",
            "cuda_runtime_version": "12.8",
            "cuda_driver_version": "570.00",
            "cudnn_version": "9.7.1",
            "nccl_version": "2.26.2",
            "gpu_name": "NVIDIA A100",
            "gpu_compute_capability": "8.0",
            "deepspeed_compatible": True,
        }
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(probe),
            stderr="",
        )


def test_resolve_parses_full_unique_target_inventory() -> None:
    """TOML lock 选择唯一 x86_64 distribution 并保留全部制品摘要。"""

    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=ROOT,
        source_sha="1" * 40,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())

    packages = {package.name: package for package in lock.packages}
    assert tuple(packages) == tuple(sorted(packages))
    assert len(packages) == len(lock.packages)
    assert packages["autovla"].version == "0.1.0.dev0"
    assert packages["torch"].version == "2.7.1+cu128"
    assert packages["torchvision"].version == "0.22.1+cu128"
    assert packages["torch"].artifact_sha256
    assert "model-gr00t-n1d6" not in packages


def test_plan_uses_workspace_physical_root_without_changing_receipt_paths(
    tmp_path: Path,
) -> None:
    """checkout 提供源码身份,workspace 独立控制物理目标。"""

    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=tmp_path,
        source_sha="2" * 40,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())
    plan = manager.plan_create("gr00t_n1d6_runtime", lock, nonce="global-0001")

    assert plan.environment_path == (f".autovla_envs/gr00t_n1d6_runtime/{lock.fingerprint}/.venv")
    assert plan.staging_path.startswith(
        f".autovla_envs/gr00t_n1d6_runtime/.materializing-{lock.fingerprint}-"
    )
    assert plan.cache_path == ".autovla_cache/uv"
    assert "--offline" in plan.command
    assert "--no-editable" in plan.command
    assert "--no-python-downloads" in plan.command
    (tmp_path / plan.environment_path).parent.mkdir(parents=True)
    with pytest.raises(RuntimeEnvironmentError, match="never mutates"):
        manager.plan_create("gr00t_n1d6_runtime", lock, nonce="global-0002")


def test_create_publishes_lock_directory_with_venv_and_three_receipts(
    tmp_path: Path,
) -> None:
    """离线 create 原子发布 fingerprint 目录及三个真实 sidecar。"""

    runner = _MaterializingRunner()
    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=tmp_path,
        source_sha="4" * 40,
        runner=runner,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())
    runner.packages = {package.name: package.version for package in lock.packages}

    receipt = manager.create(
        "gr00t_n1d6_runtime",
        lock,
        nonce="physical-0001",
        allow_create=True,
    )

    publication = tmp_path / ".autovla_envs" / "gr00t_n1d6_runtime" / lock.fingerprint
    assert receipt.environment_path.endswith(f"{lock.fingerprint}/.venv")
    assert (publication / ".venv/bin/python").is_file()
    assert {
        "receipt.json",
        "installed-packages.json",
        "verification.json",
    } <= {path.name for path in publication.iterdir()}
    assert manager.verify("gr00t_n1d6_runtime", lock).verification_status == "pass"


def test_cache_requires_authorization_then_runs_online_and_offline_dry_run(
    tmp_path: Path,
) -> None:
    """只有显式 cache 首命令可联网,第二命令强制离线 dry-run。"""

    runner = _RecordingRunner()
    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=tmp_path,
        source_sha="3" * 40,
        runner=runner,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())

    with pytest.raises(RuntimeEnvironmentError, match="allow-network"):
        manager.cache("gr00t_n1d6_runtime", lock)
    result = manager.cache("gr00t_n1d6_runtime", lock, allow_network=True)

    assert result["offline_completeness_status"] == "pass"
    assert len(runner.calls) == 2
    online_command, online_env = runner.calls[0]
    offline_command, offline_env = runner.calls[1]
    assert "--offline" not in online_command
    assert "--dry-run" not in online_command
    assert "--no-editable" in online_command
    assert "UV_OFFLINE" not in online_env
    assert "--offline" in offline_command
    assert "--dry-run" in offline_command
    assert "--no-editable" in offline_command
    assert offline_env["UV_OFFLINE"] == "1"


def test_probe_records_exact_deepspeed_import_version_compatibility() -> None:
    """probe 只证明 import/version 一致,不声明 ZeRO 执行。"""

    assert "import deepspeed" in _PROBE
    assert 'imported_version == packages["deepspeed"]' in _PROBE
    assert '"deepspeed_compatible"' in _PROBE
    assert "zero" not in _PROBE.lower()
