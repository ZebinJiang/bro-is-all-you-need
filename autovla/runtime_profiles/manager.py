"""显式、离线、锁定的 AutoVLA 运行时环境管理器。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import subprocess
from collections.abc import Callable, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from autovla.runtime_profiles.contracts import (
    FamilyRuntimeProfile,
    RuntimeCompatibilityReport,
    RuntimeDiagnostic,
    RuntimeEnvironmentFingerprint,
    RuntimeEnvironmentSpec,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.runtime_profiles.registry import load_runtime_profiles

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
_FINGERPRINT_SCHEMA = "autovla.runtime_profile_fingerprint.v1"
_REPORT_SCHEMA = "autovla.runtime_compatibility_report.v1"
_MARKER_NAME = ".autovla-runtime-profile.json"
_SECRET_OR_NETWORK_ENV = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "HF_TOKEN",
    "HUGGINGFACE_HUB_TOKEN",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "NO_PROXY",
    "WANDB_API_KEY",
    "http_proxy",
    "https_proxy",
    "no_proxy",
}
_PROBE = r'''
import hashlib
import importlib.metadata
import json
import platform
import sys

packages = {}
for distribution in importlib.metadata.distributions():
    name = (distribution.metadata.get("Name") or "").lower().replace("_", "-")
    if name:
        packages[name] = distribution.version
inventory = "\n".join(f"{name}=={packages[name]}" for name in sorted(packages))
result = {
    "python_version": platform.python_version(),
    "python_implementation": platform.python_implementation(),
    "platform": platform.platform(),
    "packages": packages,
    "inventory_sha256": hashlib.sha256(inventory.encode("utf-8")).hexdigest(),
    "torch_compiled_cuda_version": None,
    "cuda_runtime_version": None,
    "cuda_driver_version": None,
    "cudnn_version": None,
    "nccl_version": None,
    "gpu_name": None,
    "gpu_compute_capability": None,
    "sys_executable": sys.executable,
    "sys_prefix": sys.prefix,
}
try:
    import torch
    result["torch_compiled_cuda_version"] = torch.version.cuda
    if torch.backends.cudnn.is_available():
        version = torch.backends.cudnn.version()
        result["cudnn_version"] = None if version is None else str(version)
    if torch.distributed.is_available() and torch.distributed.is_nccl_available():
        try:
            result["nccl_version"] = ".".join(str(item) for item in torch.cuda.nccl.version())
        except Exception:
            pass
    if torch.cuda.is_available():
        result["gpu_name"] = torch.cuda.get_device_name(0)
        result["gpu_compute_capability"] = ".".join(
            str(item) for item in torch.cuda.get_device_capability(0)
        )
        get_driver_version = getattr(torch._C, "_cuda_getDriverVersion", None)
        get_runtime_version = getattr(torch._C, "_cuda_getRuntimeVersion", None)
        if get_driver_version is not None:
            result["cuda_driver_version"] = str(get_driver_version())
        if get_runtime_version is not None:
            result["cuda_runtime_version"] = str(get_runtime_version())
except Exception as exc:
    result["torch_probe_error"] = type(exc).__name__
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
'''


def _sha256(path: Path) -> str:
    """以流式读取计算文件 SHA256，避免把 lock 整体读入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _normal_package_name(name: str) -> str:
    """统一 Python distribution 名称比较格式。"""

    return name.lower().replace("_", "-").replace(".", "-")


class RuntimeEnvironmentManager:
    """管理四个显式 profile，且不在 verify/exec 中创建或同步环境。"""

    def __init__(
        self,
        repository_root: Path,
        *,
        source_sha: str | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        """绑定仓库、静态画像和可替换的无 shell 子进程执行器。"""

        self.repository_root = repository_root.resolve()
        self.profiles = load_runtime_profiles(self.repository_root)
        self.source_sha = source_sha or self._resolve_source_sha()
        self._runner = runner

    def _resolve_source_sha(self) -> str:
        """读取当前 Git 源身份，不执行网络或工作树变更。"""

        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.repository_root,
            check=True,
            text=True,
            capture_output=True,
        )
        return result.stdout.strip()

    def list_profiles(self) -> tuple[FamilyRuntimeProfile, ...]:
        """按 profile id 返回闭集，不检查或创建环境。"""

        return tuple(self.profiles[key] for key in sorted(self.profiles))

    def require_profile(self, profile_id: str) -> FamilyRuntimeProfile:
        """查找画像；未知身份以稳定错误码失败。"""

        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise RuntimeEnvironmentError("PROFILE_UNKNOWN", profile_id) from exc

    def inspect(self, profile_id: str) -> dict[str, object]:
        """返回描述、项目、lock 摘要和显式 blocker，不触碰环境。"""

        profile = self.require_profile(profile_id)
        spec = RuntimeEnvironmentSpec.for_profile(self.repository_root, profile)
        spec.validate()
        descriptor = self.repository_root / profile.descriptor_path
        project = self.repository_root / profile.uv_project
        pyproject = project / "pyproject.toml"
        lock = project / "uv.lock"
        lock_hash = _sha256(lock) if lock.is_file() else None
        return {
            "profile": profile.to_dict(),
            "environment": spec.to_dict(),
            "profile_descriptor_sha256": _sha256(descriptor),
            "pyproject_exists": pyproject.is_file(),
            "pyproject_sha256": _sha256(pyproject) if pyproject.is_file() else None,
            "uv_lock_exists": lock.is_file(),
            "observed_uv_lock_sha256": lock_hash,
            "lock_hash_matches_descriptor": lock_hash == profile.lock_sha256,
            "creation_ready": not profile.blockers and lock_hash == profile.lock_sha256,
        }

    @contextmanager
    def _creation_lock(self, profile_id: str) -> Iterator[None]:
        """在 runs/tmp 内获取进程锁，避免并发 materialization。"""

        lock_dir = (
            self.repository_root / "runs" / "tmp" / "autovla-runtime-profiles" / "locks"
        )
        lock_dir.mkdir(parents=True, exist_ok=True)
        lock_path = lock_dir / f"{profile_id}.lock"
        with lock_path.open("a+", encoding="utf-8") as handle:
            try:
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise RuntimeEnvironmentError(
                    "ENVIRONMENT_CREATE_LOCKED", f"another creator owns {profile_id}"
                ) from exc
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)

    def _offline_environment(self, spec: RuntimeEnvironmentSpec) -> dict[str, str]:
        """构造无 token/proxy/PYTHONPATH 的离线 uv/执行环境。"""

        env = {
            key: value
            for key, value in os.environ.items()
            if key not in _SECRET_OR_NETWORK_ENV and key not in {"PYTHONHOME", "PYTHONPATH"}
        }
        env.update(
            {
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_OFFLINE": "1",
                "PIP_NO_INDEX": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "UV_CACHE_DIR": str(
                    self.repository_root / "runs" / "tmp" / "autovla-runtime-profiles" / "uv-cache"
                ),
                "UV_OFFLINE": "1",
                "UV_PROJECT_ENVIRONMENT": str(spec.environment_path),
                "WANDB_MODE": "disabled",
            }
        )
        return env

    def _validate_materialization_inputs(
        self,
        profile: FamilyRuntimeProfile,
        spec: RuntimeEnvironmentSpec,
    ) -> None:
        """在调用 uv 前关闭 blocker、缺失 lock、摘要漂移和既有目标。"""

        spec.validate()
        if profile.blockers:
            raise RuntimeEnvironmentError(
                "PROFILE_EXACT_VERSIONS_UNRESOLVED", "; ".join(profile.blockers)
            )
        project = self.repository_root / profile.uv_project
        pyproject = project / "pyproject.toml"
        lock = project / "uv.lock"
        if not pyproject.is_file() or not lock.is_file() or profile.lock_sha256 is None:
            raise RuntimeEnvironmentError(
                "PROFILE_LOCK_MISSING", "an accepted pyproject/uv.lock pair is required"
            )
        if _sha256(lock) != profile.lock_sha256:
            raise RuntimeEnvironmentError("PROFILE_LOCK_HASH_MISMATCH", "uv.lock digest drifted")
        if spec.environment_path.exists():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_ALREADY_EXISTS", "create never mutates an existing target"
            )

    def create(self, profile_id: str, *, allow_create: bool = False) -> dict[str, object]:
        """显式执行 ``uv sync --offline --locked``，默认拒绝创建。"""

        if not allow_create:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_CREATE_NOT_AUTHORIZED", "create requires --allow-create"
            )
        profile = self.require_profile(profile_id)
        spec = RuntimeEnvironmentSpec.for_profile(self.repository_root, profile)
        self._validate_materialization_inputs(profile, spec)
        with self._creation_lock(profile_id):
            self._validate_materialization_inputs(profile, spec)
            env = self._offline_environment(spec)
            command = [
                "uv",
                "sync",
                "--offline",
                "--locked",
                "--project",
                str(self.repository_root / profile.uv_project),
                "--python",
                profile.requested_python_version,
            ]
            try:
                result = self._runner(
                    command,
                    cwd=self.repository_root,
                    env=env,
                    check=False,
                    text=True,
                )
            except OSError as exc:
                raise RuntimeEnvironmentError(
                    "ENVIRONMENT_CREATE_FAILED", "offline uv executable could not run"
                ) from exc
            if result.returncode != 0:
                raise RuntimeEnvironmentError(
                    "ENVIRONMENT_CREATE_FAILED", "offline locked uv sync failed"
                )
            python = spec.environment_path / "bin" / "python"
            if not python.is_file():
                raise RuntimeEnvironmentError(
                    "ENVIRONMENT_CREATE_INCOMPLETE", "created environment has no bin/python"
                )
            marker = spec.environment_path / _MARKER_NAME
            marker.write_text(
                json.dumps(
                    {
                        "profile_id": profile.profile_id,
                        "source_sha": self.source_sha,
                        "uv_lock_sha256": profile.lock_sha256,
                    },
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
            )
        return {"profile_id": profile_id, **spec.to_dict(), "created": True}

    def _empty_fingerprint(self, profile: FamilyRuntimeProfile) -> RuntimeEnvironmentFingerprint:
        """构造不依赖已实现环境的 portable fingerprint。"""

        descriptor = self.repository_root / profile.descriptor_path
        pyproject = self.repository_root / profile.uv_project / "pyproject.toml"
        lock = self.repository_root / profile.uv_project / "uv.lock"
        return RuntimeEnvironmentFingerprint(
            schema_version=_FINGERPRINT_SCHEMA,
            source_sha=self.source_sha,
            profile_id=profile.profile_id,
            profile_descriptor_sha256=_sha256(descriptor),
            pyproject_sha256=_sha256(pyproject) if pyproject.is_file() else None,
            uv_lock_sha256=_sha256(lock) if lock.is_file() else None,
            requested_python_version=profile.requested_python_version,
            environment_path=f".autovla_envs/{profile.profile_id}",
            python_executable=None,
            python_version=None,
            python_implementation=None,
            platform=None,
            observed_packages=(),
            installed_distribution_inventory_sha256=None,
            torch_compiled_cuda_version=None,
            cuda_runtime_version=None,
            cuda_driver_version=None,
            cudnn_version=None,
            nccl_version=None,
            gpu_name=None,
            gpu_compute_capability=None,
            offline_flags=(
                ("HF_DATASETS_OFFLINE", "1"),
                ("HF_HUB_OFFLINE", "1"),
                ("PIP_NO_INDEX", "1"),
                ("TRANSFORMERS_OFFLINE", "1"),
                ("UV_OFFLINE", "1"),
                ("WANDB_MODE", "disabled"),
            ),
        )

    def _probe_environment(
        self,
        spec: RuntimeEnvironmentSpec,
    ) -> tuple[RuntimeEnvironmentFingerprint, dict[str, Any]]:
        """用目标解释器执行单次小型 probe，不导入任何模型包。"""

        python = spec.environment_path / "bin" / "python"
        try:
            result = self._runner(
                [str(python), "-I", "-c", _PROBE],
                cwd=self.repository_root,
                env=self._offline_environment(spec),
                check=False,
                text=True,
                capture_output=True,
            )
        except OSError as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_FAILED", "isolated runtime interpreter could not run"
            ) from exc
        if result.returncode != 0:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_FAILED", "isolated runtime probe returned non-zero"
            )
        try:
            observed = json.loads(result.stdout)
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime probe did not return valid JSON"
            ) from exc
        if not isinstance(observed, dict) or not isinstance(observed.get("packages"), dict):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime probe shape is invalid"
            )
        base = self._empty_fingerprint(spec.profile)
        packages = tuple(
            sorted(
                (_normal_package_name(str(name)), str(version))
                for name, version in observed["packages"].items()
            )
        )
        fingerprint = RuntimeEnvironmentFingerprint(
            schema_version=base.schema_version,
            source_sha=base.source_sha,
            profile_id=base.profile_id,
            profile_descriptor_sha256=base.profile_descriptor_sha256,
            pyproject_sha256=base.pyproject_sha256,
            uv_lock_sha256=base.uv_lock_sha256,
            requested_python_version=base.requested_python_version,
            environment_path=base.environment_path,
            python_executable=f".autovla_envs/{spec.profile.profile_id}/bin/python",
            python_version=str(observed.get("python_version") or ""),
            python_implementation=str(observed.get("python_implementation") or ""),
            platform=str(observed.get("platform") or ""),
            observed_packages=packages,
            installed_distribution_inventory_sha256=str(observed.get("inventory_sha256") or ""),
            torch_compiled_cuda_version=observed.get("torch_compiled_cuda_version"),
            cuda_runtime_version=observed.get("cuda_runtime_version"),
            cuda_driver_version=observed.get("cuda_driver_version"),
            cudnn_version=observed.get("cudnn_version"),
            nccl_version=observed.get("nccl_version"),
            gpu_name=observed.get("gpu_name"),
            gpu_compute_capability=observed.get("gpu_compute_capability"),
            offline_flags=base.offline_flags,
        )
        return fingerprint, observed

    def verify(self, profile_id: str) -> RuntimeCompatibilityReport:
        """验证已有环境；绝不创建目录、同步依赖或修改第三方包目录。"""

        profile = self.require_profile(profile_id)
        spec = RuntimeEnvironmentSpec.for_profile(self.repository_root, profile)
        errors: list[RuntimeDiagnostic] = []
        warnings: list[RuntimeDiagnostic] = []
        path_checks = {
            "canonical_environment_path": True,
            "creation_marker_matches": False,
            "interpreter_inside_environment": False,
        }
        prohibited_checks = {name: False for name in profile.prohibited_packages}
        cuda_checks = {
            "torch_compiled_cuda_known": not profile.requires_cuda,
            "gpu_available": not profile.requires_cuda,
            "nccl_known": not profile.requires_cuda,
        }
        try:
            spec.validate()
        except RuntimeEnvironmentError as exc:
            path_checks["canonical_environment_path"] = False
            errors.append(RuntimeDiagnostic(exc.code, exc.message))
        lock = self.repository_root / profile.uv_project / "uv.lock"
        if profile.blockers:
            errors.append(
                RuntimeDiagnostic(
                    "PROFILE_EXACT_VERSIONS_UNRESOLVED", "; ".join(profile.blockers)
                )
            )
        if profile.lock_sha256 is None or not lock.is_file():
            errors.append(RuntimeDiagnostic("PROFILE_LOCK_MISSING", "accepted uv.lock is absent"))
        elif _sha256(lock) != profile.lock_sha256:
            errors.append(RuntimeDiagnostic("PROFILE_LOCK_HASH_MISMATCH", "uv.lock digest drifted"))
        if profile.asset_license_gate_status.startswith("blocked"):
            errors.append(
                RuntimeDiagnostic(
                    "ASSET_LICENSE_GATE_BLOCKED", profile.asset_license_gate_status
                )
            )
        python = spec.environment_path / "bin" / "python"
        fingerprint = self._empty_fingerprint(profile)
        observed: dict[str, Any] = {}
        if not spec.environment_path.is_dir() or not python.is_file():
            errors.append(
                RuntimeDiagnostic(
                    "ENVIRONMENT_MISSING", "verify never creates a missing environment"
                )
            )
        else:
            try:
                fingerprint, observed = self._probe_environment(spec)
                observed_prefix = Path(str(observed.get("sys_prefix") or "")).resolve()
                path_checks["interpreter_inside_environment"] = (
                    observed_prefix == spec.environment_path.resolve()
                )
                if not path_checks["interpreter_inside_environment"]:
                    errors.append(
                        RuntimeDiagnostic(
                            "INTERPRETER_PATH_INVALID",
                            "runtime sys.prefix is outside the declared environment",
                        )
                    )
            except RuntimeEnvironmentError as exc:
                errors.append(RuntimeDiagnostic(exc.code, exc.message))
            marker = spec.environment_path / _MARKER_NAME
            try:
                marker_payload = json.loads(marker.read_text(encoding="utf-8"))
                path_checks["creation_marker_matches"] = marker_payload == {
                    "profile_id": profile.profile_id,
                    "source_sha": self.source_sha,
                    "uv_lock_sha256": profile.lock_sha256,
                }
            except (OSError, json.JSONDecodeError, TypeError):
                path_checks["creation_marker_matches"] = False
            if not path_checks["creation_marker_matches"]:
                errors.append(
                    RuntimeDiagnostic(
                        "ENVIRONMENT_MARKER_MISMATCH",
                        "environment was not materialized from the current profile identity",
                    )
                )
        observed_packages = dict(fingerprint.observed_packages)
        if fingerprint.python_version and not fingerprint.python_version.startswith(
            profile.requested_python_version + "."
        ):
            errors.append(
                RuntimeDiagnostic(
                    "PYTHON_VERSION_MISMATCH",
                    f"expected {profile.requested_python_version}.x, "
                    f"observed {fingerprint.python_version}",
                )
            )
        if fingerprint.python_executable is not None:
            for name, version in profile.exact_packages:
                observed_version = observed_packages.get(name)
                if observed_version != version:
                    errors.append(
                        RuntimeDiagnostic(
                            "PACKAGE_VERSION_MISMATCH",
                            f"{name} expected {version}, observed {observed_version or 'missing'}",
                        )
                    )
            for name in profile.prohibited_packages:
                absent = name not in observed_packages
                prohibited_checks[name] = absent
                if not absent:
                    errors.append(
                        RuntimeDiagnostic(
                            "PROHIBITED_PACKAGE_PRESENT",
                            f"{name} is forbidden in {profile.profile_id}",
                        )
                    )
        if profile.requires_cuda and observed:
            cuda_checks = {
                "torch_compiled_cuda_known": bool(observed.get("torch_compiled_cuda_version")),
                "cuda_driver_known": bool(observed.get("cuda_driver_version")),
                "cuda_runtime_known": bool(observed.get("cuda_runtime_version")),
                "gpu_available": bool(observed.get("gpu_name")),
                "nccl_known": bool(observed.get("nccl_version")),
            }
            for key, passed in cuda_checks.items():
                if not passed:
                    errors.append(
                        RuntimeDiagnostic(
                            "CUDA_COMPATIBILITY_UNVERIFIED", f"required check failed: {key}"
                        )
                    )
            warnings.append(
                RuntimeDiagnostic(
                    "CUDA_DRIVER_RUNTIME_RECEIPT_REQUIRED",
                    "driver and runtime identity remain compute-node evidence",
                )
            )
        return RuntimeCompatibilityReport(
            schema_version=_REPORT_SCHEMA,
            profile_id=profile.profile_id,
            source_sha=self.source_sha,
            fingerprint=fingerprint,
            expected_versions=profile.exact_packages,
            observed_versions=fingerprint.observed_packages,
            path_isolation_checks=tuple(sorted(path_checks.items())),
            prohibited_dependency_checks=tuple(sorted(prohibited_checks.items())),
            cuda_compatibility_checks=tuple(sorted(cuda_checks.items())),
            asset_and_license_gate_status=profile.asset_license_gate_status,
            errors=tuple(errors),
            warnings=tuple(warnings),
            status="fail" if errors else "pass",
        )

    @staticmethod
    def _is_training_command(command: Sequence[str]) -> bool:
        """识别转换画像不得执行的生产训练入口。"""

        joined = " ".join(command)
        return bool(command) and (
            Path(command[0]).name == "autovla-train" or "autovla.cli.train" in joined
        )

    def exec(self, profile_id: str, command: Sequence[str]) -> int:
        """仅在现有环境验证通过后直通执行，不捕获大输出。"""

        if not command:
            raise RuntimeEnvironmentError("COMMAND_REQUIRED", "exec requires a command")
        profile = self.require_profile(profile_id)
        if not profile.is_training_runtime and self._is_training_command(command):
            raise RuntimeEnvironmentError(
                "CONVERSION_TRAINING_FORBIDDEN",
                "Pi0.5 conversion profile is never a production training runtime",
            )
        report = self.verify(profile_id)
        if not report.is_compatible:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_INCOMPATIBLE", "exec requires a passing compatibility report"
            )
        spec = RuntimeEnvironmentSpec.for_profile(self.repository_root, profile)
        env = self._offline_environment(spec)
        env["PATH"] = str(spec.environment_path / "bin") + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(spec.environment_path)
        try:
            result = self._runner(
                list(command),
                cwd=self.repository_root,
                env=env,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_EXEC_FAILED", "verified command could not start"
            ) from exc
        return result.returncode


__all__ = ["RuntimeEnvironmentManager"]
