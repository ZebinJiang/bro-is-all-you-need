"""显式、离线、锁定的 AutoVLA 运行时环境管理器。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from collections.abc import Callable, Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from autovla.runtime_profiles.contracts import (
    FamilyRuntimeProfile,
    RuntimeCompatibilityReport,
    RuntimeDiagnostic,
    RuntimeEnvironmentFingerprint,
    RuntimeEnvironmentSpec,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.runtime_profiles.registry import (
    load_runtime_profiles,
    runtime_profile_descriptor_sha256,
)

CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
_FINGERPRINT_SCHEMA = "autovla.runtime_profile_fingerprint.v1"
_REPORT_SCHEMA = "autovla.runtime_compatibility_report.v1"
_MARKER_NAME = ".autovla-runtime-profile.json"
_DIAGNOSTIC_LIMIT = 4096
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
_PROBE = r"""
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
"""


def _sha256(path: Path) -> str:
    """以流式读取计算文件 SHA256,避免把 lock 整体读入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _optional_probe_text(value: object, field: str) -> str | None:
    """只接收 probe 返回的空值或真实文本,拒绝隐式字符串化。"""

    if value is None or isinstance(value, str):
        return value
    raise RuntimeEnvironmentError(
        "ENVIRONMENT_PROBE_INVALID",
        f"runtime probe field {field!r} must be a string or null",
    )


def _normal_package_name(name: str) -> str:
    """统一 Python distribution 名称比较格式。"""

    return name.lower().replace("_", "-").replace(".", "-")


class RuntimeEnvironmentManager:
    """管理四个显式 profile,且不在 verify/exec 中创建或同步环境。"""

    def __init__(
        self,
        repository_root: Path | None = None,
        *,
        source_sha: str | None = None,
        runner: CommandRunner = subprocess.run,
    ) -> None:
        """绑定包内画像,并可选绑定经过校验的显式 checkout。"""

        self.repository_root = (
            None if repository_root is None else self._validate_checkout_root(repository_root)
        )
        self.profiles = load_runtime_profiles()
        self.source_sha = source_sha or (
            self._resolve_source_sha() if self.repository_root is not None else None
        )
        self._runner = runner

    @staticmethod
    def _validate_checkout_root(repository_root: Path) -> Path:
        """拒绝不存在、非目录或不含项目环境声明的伪 checkout。"""

        root = repository_root.expanduser().resolve()
        if not root.is_dir() or not (root / "pyproject.toml").is_file():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_INVALID", "checkout root must contain pyproject.toml"
            )
        if not (root / "envs").is_dir():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_INVALID", "checkout root must contain the envs directory"
            )
        return root

    def _require_checkout_root(self) -> Path:
        """为会读取 envs 或写入运行目录的操作要求显式 checkout。"""

        if self.repository_root is None:
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_REQUIRED",
                "this operation requires an explicit validated checkout root",
            )
        return self.repository_root

    def _require_source_sha(self) -> str:
        """为环境身份收据要求可验证源提交。"""

        if self.source_sha is None:
            raise RuntimeEnvironmentError(
                "SOURCE_SHA_REQUIRED", "runtime operations require a checkout source sha"
            )
        return self.source_sha

    def _resolve_source_sha(self) -> str:
        """读取当前 Git 源身份,不执行网络或工作树变更。"""

        root = self._require_checkout_root()
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=root,
                check=True,
                text=True,
                capture_output=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise RuntimeEnvironmentError(
                "CHECKOUT_SOURCE_IDENTITY_UNAVAILABLE",
                "checkout root must expose a readable Git HEAD",
            ) from exc
        return result.stdout.strip()

    def list_profiles(self) -> tuple[FamilyRuntimeProfile, ...]:
        """按 profile id 返回闭集,不检查或创建环境。"""

        return tuple(self.profiles[key] for key in sorted(self.profiles))

    def require_profile(self, profile_id: str) -> FamilyRuntimeProfile:
        """查找画像;未知身份以稳定错误码失败。"""

        try:
            return self.profiles[profile_id]
        except KeyError as exc:
            raise RuntimeEnvironmentError("PROFILE_UNKNOWN", profile_id) from exc

    def inspect(self, profile_id: str) -> dict[str, object]:
        """返回包内元数据;仅在显式绑定 checkout 后读取项目与 lock。"""

        profile = self.require_profile(profile_id)
        descriptor_hash = runtime_profile_descriptor_sha256()
        if self.repository_root is None:
            return {
                "profile": profile.to_dict(),
                "profile_descriptor_sha256": descriptor_hash,
                "checkout_bound": False,
                "checkout_required_for_operations": True,
                "pyproject_exists": None,
                "pyproject_sha256": None,
                "uv_lock_exists": None,
                "observed_uv_lock_sha256": None,
                "lock_hash_matches_descriptor": None,
                "lock_accepted": profile.lock_accepted,
                "creation_ready": False,
            }
        spec = RuntimeEnvironmentSpec.for_profile(self.repository_root, profile)
        spec.validate()
        project = self.repository_root / profile.uv_project
        pyproject = project / "pyproject.toml"
        lock = project / "uv.lock"
        lock_hash = _sha256(lock) if lock.is_file() else None
        return {
            "profile": profile.to_dict(),
            "environment": spec.to_dict(),
            "profile_descriptor_sha256": descriptor_hash,
            "checkout_bound": True,
            "checkout_required_for_operations": True,
            "pyproject_exists": pyproject.is_file(),
            "pyproject_sha256": _sha256(pyproject) if pyproject.is_file() else None,
            "uv_lock_exists": lock.is_file(),
            "observed_uv_lock_sha256": lock_hash,
            "lock_hash_matches_descriptor": lock_hash == profile.lock_sha256,
            "lock_accepted": profile.lock_accepted,
            "creation_ready": (
                profile.lock_accepted and not profile.blockers and lock_hash == profile.lock_sha256
            ),
        }

    @contextmanager
    def _creation_lock(self, profile_id: str) -> Generator[None, None, None]:
        """在 runs/tmp 内获取进程锁,避免并发 materialization。"""

        root = self._require_checkout_root()
        lock_dir = root / "runs" / "tmp" / "autovla-runtime-profiles" / "locks"
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
        root = self._require_checkout_root()
        env.update(
            {
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_OFFLINE": "1",
                "PIP_NO_INDEX": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "UV_CACHE_DIR": str(
                    root / "runs" / "tmp" / "autovla-runtime-profiles" / "uv-cache"
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
        root = self._require_checkout_root()
        if profile.blockers or not profile.lock_accepted:
            raise RuntimeEnvironmentError(
                "PROFILE_EXACT_VERSIONS_UNRESOLVED", "; ".join(profile.blockers)
            )
        project = root / profile.uv_project
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

    @staticmethod
    def _write_creation_marker(marker: Path, payload: Mapping[str, object]) -> None:
        """在 staging 环境中写入最终身份标记。"""

        marker.write_text(
            json.dumps(payload, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    @staticmethod
    def _bounded_output(value: str | None) -> str:
        """只保留子进程输出尾部,避免诊断收据无界增长。"""

        return (value or "")[-_DIAGNOSTIC_LIMIT:]

    def _record_creation_failure(
        self,
        *,
        profile_id: str,
        error: RuntimeEnvironmentError,
        command: Sequence[str],
        result: subprocess.CompletedProcess[str] | None,
        staging_name: str,
    ) -> None:
        """原子覆盖单画像最后一次失败收据,且不遮蔽原始失败。"""

        root = self._require_checkout_root()
        diagnostic_dir = root / "runs" / "tmp" / "autovla-runtime-profiles" / "diagnostics"
        try:
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            destination = diagnostic_dir / f"{profile_id}.last-create-failure.json"
            temporary = diagnostic_dir / f".{profile_id}.last-create-failure.tmp"
            payload = {
                "schema_version": "autovla.runtime_profile_create_failure.v1",
                "profile_id": profile_id,
                "error": {"code": error.code, "message": error.message},
                "command": list(command),
                "returncode": None if result is None else result.returncode,
                "stdout_tail": self._bounded_output(None if result is None else result.stdout),
                "stderr_tail": self._bounded_output(None if result is None else result.stderr),
                "staging_name": staging_name,
            }
            temporary.write_text(
                json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            os.replace(temporary, destination)
        except OSError:
            # 诊断落盘失败不能改变 create 的稳定主错误。
            return

    @staticmethod
    def _remove_staging(path: Path) -> None:
        """只清理由本次 create 生成的精确 staging 目标。"""

        try:
            if path.is_symlink():
                path.unlink()
            elif path.exists():
                shutil.rmtree(path)
        except OSError:
            # Canonical target 尚未发布;残留 staging 名不会阻断后续重试。
            return

    def create(self, profile_id: str, *, allow_create: bool = False) -> dict[str, object]:
        """在隔离 staging 中离线创建,并在标记成功后原子发布。"""

        if not allow_create:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_CREATE_NOT_AUTHORIZED", "create requires --allow-create"
            )
        profile = self.require_profile(profile_id)
        root = self._require_checkout_root()
        source_sha = self._require_source_sha()
        spec = RuntimeEnvironmentSpec.for_profile(root, profile)
        self._validate_materialization_inputs(profile, spec)
        with self._creation_lock(profile_id):
            self._validate_materialization_inputs(profile, spec)
            spec.environment_root.mkdir(parents=True, exist_ok=True)
            staging_path = Path(
                tempfile.mkdtemp(
                    prefix=f".materializing-{profile_id}-",
                    dir=spec.environment_root,
                )
            )
            command = [
                "uv",
                "sync",
                "--offline",
                "--locked",
                "--project",
                str(root / profile.uv_project),
                "--python",
                profile.requested_python_version,
            ]
            result: subprocess.CompletedProcess[str] | None = None
            try:
                staging_spec = RuntimeEnvironmentSpec(
                    repository_root=spec.repository_root,
                    profile=spec.profile,
                    environment_root=spec.environment_root,
                    environment_path=staging_path,
                )
                env = self._offline_environment(staging_spec)
                try:
                    result = self._runner(
                        command,
                        cwd=root,
                        env=env,
                        check=False,
                        text=True,
                        capture_output=True,
                    )
                except OSError as exc:
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_CREATE_FAILED", "offline uv executable could not run"
                    ) from exc
                if result.returncode != 0:
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_CREATE_FAILED", "offline locked uv sync failed"
                    )
                python = staging_path / "bin" / "python"
                if not python.is_file():
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_CREATE_INCOMPLETE", "created environment has no bin/python"
                    )
                marker_payload = {
                    "profile_id": profile.profile_id,
                    "source_sha": source_sha,
                    "uv_lock_sha256": profile.lock_sha256,
                }
                try:
                    self._write_creation_marker(staging_path / _MARKER_NAME, marker_payload)
                except OSError as exc:
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_MARKER_WRITE_FAILED",
                        "creation marker could not be written",
                    ) from exc
                try:
                    os.replace(staging_path, spec.environment_path)
                except OSError as exc:
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_PUBLISH_FAILED",
                        "staged environment could not be atomically published",
                    ) from exc
            except RuntimeEnvironmentError as exc:
                self._record_creation_failure(
                    profile_id=profile_id,
                    error=exc,
                    command=command,
                    result=result,
                    staging_name=staging_path.name,
                )
                raise
            finally:
                self._remove_staging(staging_path)
        return {"profile_id": profile_id, **spec.to_dict(), "created": True}

    def _empty_fingerprint(self, profile: FamilyRuntimeProfile) -> RuntimeEnvironmentFingerprint:
        """构造不依赖已实现环境的 portable fingerprint。"""

        root = self._require_checkout_root()
        pyproject = root / profile.uv_project / "pyproject.toml"
        lock = root / profile.uv_project / "uv.lock"
        return RuntimeEnvironmentFingerprint(
            schema_version=_FINGERPRINT_SCHEMA,
            source_sha=self._require_source_sha(),
            profile_id=profile.profile_id,
            profile_descriptor_sha256=runtime_profile_descriptor_sha256(),
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
    ) -> tuple[RuntimeEnvironmentFingerprint, dict[str, object]]:
        """用目标解释器执行单次小型 probe,不导入任何模型包。"""

        root = self._require_checkout_root()
        python = spec.environment_path / "bin" / "python"
        try:
            result = self._runner(
                [str(python), "-I", "-c", _PROBE],
                cwd=root,
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
            observed = cast(object, json.loads(result.stdout))
        except (json.JSONDecodeError, TypeError) as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime probe did not return valid JSON"
            ) from exc
        if not isinstance(observed, dict):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime probe shape is invalid"
            )
        observed_mapping = cast(dict[str, object], observed)
        observed_packages = observed_mapping.get("packages")
        if not isinstance(observed_packages, dict):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime probe shape is invalid"
            )
        packages_mapping = cast(dict[object, object], observed_packages)
        base = self._empty_fingerprint(spec.profile)
        packages = tuple(
            sorted(
                (_normal_package_name(str(name)), str(version))
                for name, version in packages_mapping.items()
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
            python_version=str(observed_mapping.get("python_version") or ""),
            python_implementation=str(observed_mapping.get("python_implementation") or ""),
            platform=str(observed_mapping.get("platform") or ""),
            observed_packages=packages,
            installed_distribution_inventory_sha256=str(
                observed_mapping.get("inventory_sha256") or ""
            ),
            torch_compiled_cuda_version=_optional_probe_text(
                observed_mapping.get("torch_compiled_cuda_version"),
                "torch_compiled_cuda_version",
            ),
            cuda_runtime_version=_optional_probe_text(
                observed_mapping.get("cuda_runtime_version"),
                "cuda_runtime_version",
            ),
            cuda_driver_version=_optional_probe_text(
                observed_mapping.get("cuda_driver_version"),
                "cuda_driver_version",
            ),
            cudnn_version=_optional_probe_text(
                observed_mapping.get("cudnn_version"),
                "cudnn_version",
            ),
            nccl_version=_optional_probe_text(
                observed_mapping.get("nccl_version"),
                "nccl_version",
            ),
            gpu_name=_optional_probe_text(
                observed_mapping.get("gpu_name"),
                "gpu_name",
            ),
            gpu_compute_capability=_optional_probe_text(
                observed_mapping.get("gpu_compute_capability"),
                "gpu_compute_capability",
            ),
            offline_flags=base.offline_flags,
        )
        return fingerprint, observed_mapping

    def verify(self, profile_id: str) -> RuntimeCompatibilityReport:
        """验证已有环境;绝不创建目录、同步依赖或修改第三方包目录。"""

        root = self._require_checkout_root()
        source_sha = self._require_source_sha()
        profile = self.require_profile(profile_id)
        spec = RuntimeEnvironmentSpec.for_profile(root, profile)
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
        lock = root / profile.uv_project / "uv.lock"
        if profile.blockers:
            errors.append(
                RuntimeDiagnostic("PROFILE_EXACT_VERSIONS_UNRESOLVED", "; ".join(profile.blockers))
            )
        if not profile.lock_accepted:
            errors.append(
                RuntimeDiagnostic(
                    "PROFILE_LOCK_NOT_ACCEPTED",
                    "the present or missing lock is not accepted for this M11 runtime profile",
                )
            )
        if profile.lock_sha256 is None or not lock.is_file():
            errors.append(RuntimeDiagnostic("PROFILE_LOCK_MISSING", "accepted uv.lock is absent"))
        elif _sha256(lock) != profile.lock_sha256:
            errors.append(RuntimeDiagnostic("PROFILE_LOCK_HASH_MISMATCH", "uv.lock digest drifted"))
        if profile.asset_license_gate_status.startswith("blocked"):
            errors.append(
                RuntimeDiagnostic("ASSET_LICENSE_GATE_BLOCKED", profile.asset_license_gate_status)
            )
        python = spec.environment_path / "bin" / "python"
        fingerprint = self._empty_fingerprint(profile)
        observed: dict[str, object] = {}
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
                    "source_sha": source_sha,
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
            source_sha=source_sha,
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
        """仅在现有环境验证通过后直通执行,不捕获大输出。"""

        if not command:
            raise RuntimeEnvironmentError("COMMAND_REQUIRED", "exec requires a command")
        root = self._require_checkout_root()
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
        spec = RuntimeEnvironmentSpec.for_profile(root, profile)
        env = self._offline_environment(spec)
        env["PATH"] = str(spec.environment_path / "bin") + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(spec.environment_path)
        try:
            result = self._runner(
                list(command),
                cwd=root,
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
