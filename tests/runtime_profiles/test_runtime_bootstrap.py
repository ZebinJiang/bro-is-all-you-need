"""M13 workspace 全局运行时 bootstrap 缺陷回归测试。"""

from __future__ import annotations

import contextlib
import io
import json
import platform
import subprocess
import sys
import types
from pathlib import Path

import pytest

from autovla.runtime_profiles import (
    CudaCompatibilityIntent,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
)
from autovla.runtime_profiles.manager import _PROBE
from autovla.runtime_profiles.uv_lock import _package_from_record

ROOT = Path(__file__).resolve().parents[2]


def _cuda_intent(
    required: bool = True,
    *,
    cuda_driver_version: str = "570.00",
) -> CudaCompatibilityIntent:
    """构造不声称已执行 CUDA 的显式解析输入。"""

    return CudaCompatibilityIntent(
        schema_version="autovla.cuda_compatibility_intent.v1",
        required=required,
        torch_compiled_cuda_version="12.8" if required else None,
        cuda_runtime_version="12.8" if required else None,
        cuda_driver_version=cuda_driver_version if required else None,
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

    def __init__(self, *, cuda_driver_version: str = "570.00") -> None:
        self.packages: dict[str, str] = {}
        self.cuda_driver_version = cuda_driver_version

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
            "cuda_driver_version": self.cuda_driver_version,
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


def _execute_embedded_probe(
    monkeypatch: pytest.MonkeyPatch,
    *,
    driver_stdout: str,
) -> tuple[dict[str, object], list[tuple[list[str], dict[str, object]]]]:
    """以 Torch 2.7.1 形状执行真实 probe 字符串并记录驱动命令。"""

    fake_torch = types.SimpleNamespace(
        version=types.SimpleNamespace(cuda="12.8"),
        backends=types.SimpleNamespace(
            cudnn=types.SimpleNamespace(
                is_available=lambda: True,
                version=lambda: 90701,
            )
        ),
        distributed=types.SimpleNamespace(
            is_available=lambda: True,
            is_nccl_available=lambda: False,
        ),
        cuda=types.SimpleNamespace(
            is_available=lambda: True,
            get_device_name=lambda _index: "NVIDIA A100",
            get_device_capability=lambda _index: (8, 0),
        ),
        _C=types.SimpleNamespace(_cuda_getCompiledVersion=lambda: 12080),
    )
    calls: list[tuple[list[str], dict[str, object]]] = []

    def _run(
        command: list[str],
        **kwargs: object,
    ) -> subprocess.CompletedProcess[str]:
        """返回固定 nvidia-smi 输出并记录完整调用形状。"""

        calls.append((list(command), dict(kwargs)))
        return subprocess.CompletedProcess(command, 0, stdout=driver_stdout, stderr="")

    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setattr(platform, "platform", lambda: "manylinux_2_31_x86_64")
    monkeypatch.setattr(subprocess, "run", _run)
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        exec(_PROBE, {})
    return json.loads(stdout.getvalue()), calls


class _CudaMismatchRunner(_MaterializingRunner):
    """模拟安全 CUDA 字段不匹配及不可持久化的额外 probe 文本。"""

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
        """返回成功 uv 结果或带明确字段差异的 probe 结果。"""

        result = super().__call__(
            command,
            cwd=cwd,
            env=env,
            check=check,
            text=text,
            capture_output=capture_output,
        )
        if command[:2] == ["uv", "sync"]:
            return subprocess.CompletedProcess(
                command,
                result.returncode,
                stdout="bounded-uv-output-" * 400,
                stderr="",
            )
        probe = json.loads(result.stdout)
        probe.update(
            {
                "torch_compiled_cuda_version": "observed-compiled",
                "cuda_runtime_version": "observed-runtime",
                "cuda_driver_version": "observed-driver",
                "cudnn_version": "observed-cudnn",
                "nccl_version": "observed-nccl",
                "gpu_compute_capability": "9.9",
                "gpu_name": "/srv/private/cuda?api_key=fixture",
                "untrusted_probe_field": "token=fixture",
            }
        )
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(probe),
            stderr="",
        )


def test_resolve_parses_platform_exact_target_inventory() -> None:
    """真实 N1D6 lock 排除 Windows 依赖并匹配安装后的精确清单。"""

    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=ROOT,
        source_sha="1" * 40,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())

    packages = {package.name: package for package in lock.packages}
    assert tuple(packages) == tuple(sorted(packages))
    assert len(packages) == len(lock.packages)
    assert len(packages) == 59
    assert lock.fingerprint == "a55cc759ef8ec28099af96a17d1a666c22b66f614185950b3fc85ba3a58bc886"
    assert packages["autovla"].version == "0.1.0.dev0"
    assert "colorama" not in packages
    assert packages["flash-attn"].version == "2.7.4.post1"
    assert packages["torch"].version == "2.7.1+cu128"
    assert packages["torchvision"].version == "0.22.1+cu128"
    assert packages["torch"].artifact_sha256
    assert "model-gr00t-n1d6" not in packages


def test_direct_wheel_uses_metadata_version_and_retains_artifact_hash() -> None:
    """direct wheel 的文件名构建标签不替换安装后 METADATA 版本。"""

    source_url = (
        "https://packages.example.invalid/releases/"
        "accelerator_kernel-1.2.3+cu12torch2.7-cp310-cp310-linux_x86_64.whl"
    )
    artifact_sha256 = "a" * 64

    package = _package_from_record(
        {
            "name": "accelerator-kernel",
            "version": "1.2.3",
            "source": {"url": source_url},
            "wheels": [{"url": source_url, "hash": f"sha256:{artifact_sha256}"}],
        },
        source_distribution_version="0.1.0",
    )

    assert package is not None
    assert package.name == "accelerator-kernel"
    assert package.version == "1.2.3"
    assert package.artifact_sha256 == (artifact_sha256,)
    with pytest.raises(RuntimeEnvironmentError) as error:
        _package_from_record(
            {
                "name": "accelerator-kernel",
                "version": "1.2.3",
                "source": {"url": source_url},
                "wheels": [
                    {
                        "url": f"{source_url}.different",
                        "hash": f"sha256:{artifact_sha256}",
                    }
                ],
            },
            source_distribution_version="0.1.0",
        )
    assert error.value.code == "RUNTIME_LOCK_WHEEL_IDENTITY_INVALID"


def test_m13_n1d6_resolve_uses_isolated_python312_tomllib_bootstrap() -> None:
    """N1D6 lock 解析绕过无 tomllib 的 3.10,固定到隔离的 3.12 stdlib。"""

    script = (ROOT / "scripts/slurm/m13_n1d6_environment.sbatch").read_text(encoding="utf-8")
    resolve_command = script.split("RESOLVE_COMMAND=(", maxsplit=1)[1].split(")", maxsplit=1)[0]

    assert "command -v python3.12" in script
    assert '"$LOCK_RESOLVER_PYTHON" -I -S -c' in script
    assert "CPython 3.12 tomllib" in script
    assert "RUNTIME_LOCK_TOML_UNAVAILABLE" in script
    assert '"$LOCK_RESOLVER_PYTHON" -S -m autovla.cli.env' in resolve_command
    assert "python3 -S -m autovla.cli.env" not in resolve_command


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


def test_cuda_mismatch_details_reach_bounded_non_secret_failure_receipt(
    tmp_path: Path,
) -> None:
    """CUDA intent 拒绝收据保留逐字段差异,但不保留 probe 路径或凭据文本。"""

    runner = _CudaMismatchRunner()
    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=tmp_path,
        source_sha="5" * 40,
        runner=runner,
    )
    lock = manager.resolve("gr00t_n1d6_runtime", _cuda_intent())
    runner.packages = {package.name: package.version for package in lock.packages}

    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.create(
            "gr00t_n1d6_runtime",
            lock,
            nonce="cuda-mismatch-0001",
            allow_create=True,
        )

    assert captured.value.code == "RUNTIME_ENVIRONMENT_CUDA_INTENT_MISMATCH"
    receipt_path = (
        tmp_path
        / "runs/tmp/autovla-runtime-profiles/diagnostics"
        / "gr00t_n1d6_runtime.last-create-failure.json"
    )
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["error"]["details"] == {
        "expected": {
            "torch_compiled_cuda_version": "12.8",
            "cuda_runtime_version": "12.8",
            "cuda_driver_version": "570.00",
            "cudnn_version": "9.7.1",
            "nccl_version": "2.26.2",
            "compute_capabilities": ["8.0"],
        },
        "observed": {
            "torch_compiled_cuda_version": "observed-compiled",
            "cuda_runtime_version": "observed-runtime",
            "cuda_driver_version": "observed-driver",
            "cudnn_version": "observed-cudnn",
            "nccl_version": "observed-nccl",
            "gpu_compute_capability": "9.9",
        },
    }
    serialized_error = json.dumps(receipt["error"], sort_keys=True)
    serialized_receipt = json.dumps(receipt, sort_keys=True)
    assert len(serialized_error.encode("utf-8")) <= 2048
    assert len(receipt["stdout_tail"]) == 4096
    assert str(tmp_path) not in serialized_receipt
    assert "/srv/private" not in serialized_receipt
    assert "api_key=" not in serialized_receipt
    assert "token=" not in serialized_receipt
    assert not tuple((tmp_path / ".autovla_envs/gr00t_n1d6_runtime").glob(".materializing-*"))


def test_probe_normalizes_cuda_driver_and_cudnn_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """真实 probe 将 Torch/CUDA 编码与单行驱动输出规范化。"""

    observed, calls = _execute_embedded_probe(
        monkeypatch,
        driver_stdout="570.195.03\n",
    )

    assert observed["cuda_runtime_version"] == "12.8"
    assert observed["cuda_driver_version"] == "570.195.03"
    assert observed["cudnn_version"] == "9.7.1"
    assert observed["gpu_compute_capability"] == "8.0"
    assert calls == [
        (
            [
                "nvidia-smi",
                "--query-gpu=driver_version",
                "--format=csv,noheader,nounits",
            ],
            {
                "check": True,
                "text": True,
                "capture_output": True,
                "timeout": 5,
                "shell": False,
            },
        )
    ]


@pytest.mark.parametrize(
    "driver_stdout",
    (
        "570.195.03\n570.195.03\n",
        "driver_version=570.195.03\n",
        "570.195.03, 570.195.03\n",
        " 570.195.03\n",
        "9" * 129,
    ),
)
def test_probe_rejects_ambiguous_or_non_version_driver_output(
    monkeypatch: pytest.MonkeyPatch,
    driver_stdout: str,
) -> None:
    """多行、非版本或越界驱动输出保持未知并关闭验证。"""

    observed, calls = _execute_embedded_probe(
        monkeypatch,
        driver_stdout=driver_stdout,
    )

    assert observed["cuda_driver_version"] is None
    assert observed["cuda_driver_probe_error"] == "ValueError"
    assert len(calls) == 1


def test_cuda_driver_version_equality_remains_exact(tmp_path: Path) -> None:
    """语义近似但文本不等的驱动版本仍触发 CUDA intent 拒绝。"""

    runner = _MaterializingRunner(cuda_driver_version="570.195.3")
    manager = RuntimeEnvironmentManager(
        ROOT,
        workspace_root=tmp_path,
        source_sha="6" * 40,
        runner=runner,
    )
    lock = manager.resolve(
        "gr00t_n1d6_runtime",
        _cuda_intent(cuda_driver_version="570.195.03"),
    )
    runner.packages = {package.name: package.version for package in lock.packages}

    with pytest.raises(RuntimeEnvironmentError) as captured:
        manager.create(
            "gr00t_n1d6_runtime",
            lock,
            nonce="exact-driver-mismatch-0001",
            allow_create=True,
        )

    assert captured.value.code == "RUNTIME_ENVIRONMENT_CUDA_INTENT_MISMATCH"


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
