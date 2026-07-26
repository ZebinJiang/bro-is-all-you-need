"""显式、离线、锁定的 AutoVLA 运行时环境管理器。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
from collections.abc import Generator, Mapping, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol, cast

from autovla._version import __version__ as AUTOVLA_VERSION
from autovla.runtime_profiles.contracts import (
    CudaCompatibilityIntent,
    FamilyRuntimeProfile,
    ResolvedRuntimeLock,
    RuntimeCompatibilityReport,
    RuntimeDiagnostic,
    RuntimeEnvironmentFingerprint,
    RuntimeEnvironmentReceipt,
    RuntimeEnvironmentSpec,
    RuntimeExecutionReceipt,
    RuntimeProfileSpec,
    redact_environment,
)
from autovla.runtime_profiles.errors import RuntimeEnvironmentError
from autovla.runtime_profiles.planning import EnvironmentPublicationPlan
from autovla.runtime_profiles.registry import (
    load_runtime_profiles,
    runtime_profile_descriptor_sha256,
)
from autovla.runtime_profiles.uv_lock import resolve_uv_lock


class CommandRunner(Protocol):
    """描述测试注入命令执行器的最小边界。"""

    def __call__(
        self,
        command: list[str],
        *,
        cwd: Path,
        env: dict[str, str],
        check: bool,
        text: bool,
        capture_output: bool = ...,
    ) -> subprocess.CompletedProcess[str]:
        """执行显式命令并返回文本完成结果。"""

        ...


class OfflineSubprocessRunner:
    """为后续显式授权操作提供标准 subprocess 执行边界。"""

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
        """按调用方提供的离线环境执行命令。"""

        return subprocess.run(
            command,
            cwd=cwd,
            env=env,
            check=check,
            text=text,
            capture_output=capture_output,
        )


_FINGERPRINT_SCHEMA = "autovla.runtime_profile_fingerprint.v1"
_REPORT_SCHEMA = "autovla.runtime_compatibility_report.v1"
_MARKER_NAME = ".autovla-runtime-profile.json"
_RECEIPT_NAME = "receipt.json"
_INSTALLED_PACKAGES_NAME = "installed-packages.json"
_VERIFICATION_NAME = "verification.json"
_DIAGNOSTIC_LIMIT = 4096
_SOURCE_SHA = re.compile(r"(?:[0-9a-f]{40}|[0-9a-f]{64})")
_PROBE = r"""
import ctypes
import hashlib
import importlib.metadata
import contextlib
import io
import json
import pathlib
import platform
import re
import subprocess
import sys

import autovla

_NVIDIA_DRIVER_COMMAND = [
    "nvidia-smi",
    "--query-gpu=driver_version",
    "--format=csv,noheader,nounits",
]
_NVIDIA_DRIVER_VERSION = re.compile(r"[0-9]+(?:\.[0-9]+){1,3}")
_NVIDIA_DRIVER_OUTPUT_LIMIT = 128


def _normalize_cuda_runtime_version(value):
    '''把 CUDA 编码整数转换为稳定的语义版本。'''

    if type(value) is not int or value <= 0:
        raise ValueError("invalid CUDA runtime version")
    major, remainder = divmod(value, 1000)
    minor, patch = divmod(remainder, 10)
    if major <= 0:
        raise ValueError("invalid CUDA runtime version")
    version = f"{major}.{minor}"
    return f"{version}.{patch}" if patch else version


def _loaded_cuda_runtime_version(torch):
    '''从 Torch 已加载的 CUDART 读取真实运行时版本。'''

    cudart = torch.cuda.cudart()
    runtime_library = ctypes.CDLL(None)
    get_runtime_version = runtime_library.cudaRuntimeGetVersion
    get_runtime_version.argtypes = (ctypes.POINTER(ctypes.c_int),)
    get_runtime_version.restype = ctypes.c_int
    encoded_version = ctypes.c_int()
    status = get_runtime_version(ctypes.byref(encoded_version))
    if type(status) is not int or status != int(cudart.cudaError.success):
        raise ValueError("CUDA runtime version query failed")
    return _normalize_cuda_runtime_version(encoded_version.value)


def _normalize_cudnn_version(value):
    '''把 cuDNN 编码整数转换为 major.minor.patch。'''

    if type(value) is not int or value <= 0:
        raise ValueError("invalid cuDNN version")
    if value >= 10000:
        major, remainder = divmod(value, 10000)
    else:
        major, remainder = divmod(value, 1000)
    minor, patch = divmod(remainder, 100)
    if major <= 0:
        raise ValueError("invalid cuDNN version")
    return f"{major}.{minor}.{patch}"


def _parse_nvidia_driver_version(output):
    '''只接收单行、有界、纯版本号的 NVIDIA 驱动输出。'''

    if (
        type(output) is not str
        or len(output.encode("utf-8")) > _NVIDIA_DRIVER_OUTPUT_LIMIT
    ):
        raise ValueError("invalid NVIDIA driver version output")
    lines = output.splitlines()
    if len(lines) != 1:
        raise ValueError("invalid NVIDIA driver version output")
    version = lines[0]
    if _NVIDIA_DRIVER_VERSION.fullmatch(version) is None:
        raise ValueError("invalid NVIDIA driver version output")
    return version


packages = {}
for distribution in importlib.metadata.distributions():
    name = (distribution.metadata.get("Name") or "").lower().replace("_", "-")
    if name:
        packages[name] = distribution.version
inventory = "\n".join(f"{name}=={packages[name]}" for name in sorted(packages))
package_root = pathlib.Path(autovla.__file__).resolve().parent
package_digest = hashlib.sha256()
package_files = []
package_has_symlink = False
for candidate in package_root.rglob("*"):
    package_has_symlink = package_has_symlink or candidate.is_symlink()
    if "__pycache__" in candidate.parts or not candidate.is_file():
        continue
    relative = candidate.relative_to(package_root)
    if candidate.suffix in {".py", ".pyi"} or relative.parts[0] == "resources":
        package_files.append((relative.as_posix(), candidate))
for relative, candidate in sorted(package_files):
    package_digest.update(relative.encode("utf-8"))
    package_digest.update(b"\0")
    with candidate.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            package_digest.update(block)
    package_digest.update(b"\0")
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
    "autovla_package_root": str(package_root),
    "autovla_package_source_sha256": package_digest.hexdigest(),
    "autovla_package_has_symlink": package_has_symlink,
}
try:
    import torch
    result["torch_compiled_cuda_version"] = torch.version.cuda
    if torch.backends.cudnn.is_available():
        version = torch.backends.cudnn.version()
        result["cudnn_version"] = (
            None if version is None else _normalize_cudnn_version(version)
        )
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
        try:
            result["cuda_runtime_version"] = _loaded_cuda_runtime_version(torch)
        except Exception as exc:
            result["cuda_runtime_probe_error"] = type(exc).__name__
        try:
            driver_result = subprocess.run(
                _NVIDIA_DRIVER_COMMAND,
                check=True,
                text=True,
                capture_output=True,
                timeout=5,
                shell=False,
            )
            result["cuda_driver_version"] = _parse_nvidia_driver_version(
                driver_result.stdout
            )
        except Exception as exc:
            result["cuda_driver_probe_error"] = type(exc).__name__
except Exception as exc:
    result["torch_probe_error"] = type(exc).__name__
if "deepspeed" in packages:
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import deepspeed
        imported_version = getattr(deepspeed, "__version__", None)
        result["deepspeed_version"] = imported_version
        result["deepspeed_compatible"] = (
            isinstance(imported_version, str)
            and imported_version == packages["deepspeed"]
        )
    except Exception as exc:
        result["deepspeed_probe_error"] = type(exc).__name__
        result["deepspeed_compatible"] = False
else:
    result["deepspeed_version"] = None
    result["deepspeed_compatible"] = None
print(json.dumps(result, sort_keys=True, separators=(",", ":")))
"""


def _sha256(path: Path) -> str:
    """以流式读取计算文件 SHA256,避免把 lock 整体读入内存。"""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _package_source_sha256(package_root: Path) -> str:
    """计算可导入 Python 与 packaged resources 的确定性源码摘要。"""

    if package_root.is_symlink() or not package_root.is_dir():
        raise RuntimeEnvironmentError(
            "PACKAGE_SOURCE_IDENTITY_INVALID",
            "AutoVLA package source root must be a real directory",
        )
    selected: list[tuple[str, Path]] = []
    for candidate in package_root.rglob("*"):
        if "__pycache__" in candidate.parts:
            continue
        relative = candidate.relative_to(package_root)
        if candidate.is_symlink():
            raise RuntimeEnvironmentError(
                "PACKAGE_SOURCE_IDENTITY_INVALID",
                "AutoVLA package source must not contain symbolic links",
            )
        if candidate.is_file() and (
            candidate.suffix in {".py", ".pyi"} or relative.parts[0] == "resources"
        ):
            selected.append((relative.as_posix(), candidate))
    if not selected:
        raise RuntimeEnvironmentError(
            "PACKAGE_SOURCE_IDENTITY_INVALID",
            "AutoVLA package source contains no identity-bearing files",
        )
    digest = hashlib.sha256()
    for relative, candidate in sorted(selected):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        with candidate.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def _optional_probe_text(value: object, field: str) -> str | None:
    """只接收 probe 返回的空值或真实文本,拒绝隐式字符串化。"""

    if value is None or isinstance(value, str):
        return value
    raise RuntimeEnvironmentError(
        "ENVIRONMENT_PROBE_INVALID",
        f"runtime probe field {field!r} must be a string or null",
    )


def _optional_probe_bool(value: object, field: str) -> bool | None:
    """只接收 probe 返回的空值或真实布尔值。"""

    if value is None or type(value) is bool:
        return value
    raise RuntimeEnvironmentError(
        "ENVIRONMENT_PROBE_INVALID",
        f"runtime probe field {field!r} must be a boolean or null",
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
        workspace_root: Path | None = None,
        source_sha: str | None = None,
        runner: CommandRunner | None = None,
    ) -> None:
        """分别绑定不可变源码 checkout 与 workspace 全局物理根。"""

        self.repository_root = (
            None if repository_root is None else self._validate_checkout_root(repository_root)
        )
        selected_workspace = workspace_root if workspace_root is not None else self.repository_root
        self.workspace_root = (
            None
            if selected_workspace is None
            else self._validate_workspace_root(selected_workspace)
        )
        self.profiles = load_runtime_profiles()
        self.source_sha = source_sha or (
            self._resolve_source_sha() if self.repository_root is not None else None
        )
        self._runner: CommandRunner = runner if runner is not None else OfflineSubprocessRunner()

    @property
    def command_runner(self) -> CommandRunner:
        """暴露可审计 runner 能力,但不触发任何命令。"""

        return self._runner

    @staticmethod
    def _validate_checkout_root(repository_root: Path) -> Path:
        """拒绝不存在、非目录或不含项目环境声明的伪 checkout。"""

        expanded = repository_root.expanduser()
        if expanded.is_symlink():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_SYMLINK", "checkout root must not be a symbolic link"
            )
        root = expanded.resolve()
        if root != expanded.absolute():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_SYMLINK",
                "checkout root ancestry must not traverse symbolic links",
            )
        if not root.is_dir() or not (root / "pyproject.toml").is_file():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_INVALID", "checkout root must contain pyproject.toml"
            )
        if not (root / "envs").is_dir():
            raise RuntimeEnvironmentError(
                "CHECKOUT_ROOT_INVALID", "checkout root must contain the envs directory"
            )
        return root

    @staticmethod
    def _validate_workspace_root(workspace_root: Path) -> Path:
        """拒绝不存在、非目录或经符号链接解析的 workspace 物理根。"""

        expanded = workspace_root.expanduser()
        if expanded.is_symlink():
            raise RuntimeEnvironmentError(
                "WORKSPACE_ROOT_SYMLINK", "workspace root must not be a symbolic link"
            )
        root = expanded.resolve()
        if root != expanded.absolute():
            raise RuntimeEnvironmentError(
                "WORKSPACE_ROOT_SYMLINK",
                "workspace root ancestry must not traverse symbolic links",
            )
        if not root.is_dir():
            raise RuntimeEnvironmentError(
                "WORKSPACE_ROOT_INVALID", "workspace root must be an existing directory"
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

    def _require_workspace_root(self) -> Path:
        """为环境、缓存和跨 worktree 锁要求显式物理根。"""

        if self.workspace_root is None:
            raise RuntimeEnvironmentError(
                "WORKSPACE_ROOT_REQUIRED",
                "this operation requires an explicit validated workspace root",
            )
        return self.workspace_root

    def _require_source_sha(self) -> str:
        """为环境身份收据要求可验证源提交。"""

        if self.source_sha is None:
            raise RuntimeEnvironmentError(
                "SOURCE_SHA_REQUIRED", "runtime operations require a checkout source sha"
            )
        if not _SOURCE_SHA.fullmatch(self.source_sha):
            raise RuntimeEnvironmentError(
                "SOURCE_SHA_INVALID", "runtime operations require a full lowercase source sha"
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

    def _current_package_source_sha256(self) -> str:
        """返回当前 checkout 中实际可安装 AutoVLA 包源码摘要。"""

        return _package_source_sha256(self._require_checkout_root() / "autovla")

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
        spec = RuntimeEnvironmentSpec.for_profile(self._require_workspace_root(), profile)
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

    def resolve(
        self,
        profile_id: str,
        cuda_compatibility: CudaCompatibilityIntent,
    ) -> ResolvedRuntimeLock:
        """从提交内 TOML lock 和显式 CUDA 意图构造精确 M12 lock。"""

        profile = self.require_profile(profile_id)
        return resolve_uv_lock(
            checkout_root=self._require_checkout_root(),
            profile=profile,
            cuda_compatibility=cuda_compatibility,
            source_distribution_version=AUTOVLA_VERSION,
        )

    def plan_create(
        self,
        profile_id: str,
        lock: ResolvedRuntimeLock,
        *,
        nonce: str,
    ) -> EnvironmentPublicationPlan:
        """从精确 lock 生成无副作用发布计划。"""

        root = self._require_checkout_root()
        profile = self.require_profile(profile_id)
        project = root / profile.uv_project
        pyproject = project / "pyproject.toml"
        lock_path = project / "uv.lock"
        if not pyproject.is_file():
            raise RuntimeEnvironmentError(
                "PROFILE_PROJECT_MISSING", "runtime project pyproject.toml is absent"
            )
        self._reject_symlink_components(root, pyproject)
        self._reject_symlink_components(root, lock_path)
        if not lock_path.is_file():
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_FILE_MISSING", "resolved lock file is absent"
            )
        if _sha256(lock_path) != lock.lock_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_FILE_MISMATCH",
                "resolved lock content does not match the supplied exact lock",
            )
        plan = EnvironmentPublicationPlan.build(
            repository_root=root,
            workspace_root=self._require_workspace_root(),
            profile=profile,
            lock=lock,
            source_sha=self._require_source_sha(),
            package_source_sha256=self._current_package_source_sha256(),
            descriptor_sha256=runtime_profile_descriptor_sha256(),
            pyproject_sha256=_sha256(pyproject),
            nonce=nonce,
        )
        plan.validate_identity(
            profile=profile,
            lock=lock,
            source_sha=self._require_source_sha(),
            package_source_sha256=self._current_package_source_sha256(),
        )
        return plan

    def _plan_existing(
        self,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
    ) -> EnvironmentPublicationPlan:
        """为 verify 重建同一规范身份,但不要求目标缺失。"""

        root = self._require_checkout_root()
        project = root / profile.uv_project
        pyproject = project / "pyproject.toml"
        lock_path = project / "uv.lock"
        self._reject_symlink_components(root, pyproject)
        self._reject_symlink_components(root, lock_path)
        if not pyproject.is_file() or not lock_path.is_file():
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_FILE_MISSING", "exact pyproject and lock files are required"
            )
        if _sha256(lock_path) != lock.lock_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_FILE_MISMATCH",
                "resolved lock content does not match the supplied exact lock",
            )
        plan = EnvironmentPublicationPlan.build(
            repository_root=root,
            workspace_root=self._require_workspace_root(),
            profile=profile,
            lock=lock,
            source_sha=self._require_source_sha(),
            package_source_sha256=self._current_package_source_sha256(),
            descriptor_sha256=runtime_profile_descriptor_sha256(),
            pyproject_sha256=_sha256(pyproject),
            nonce="verify-identity",
            allow_existing_target=True,
        )
        plan.validate_identity(
            profile=profile,
            lock=lock,
            source_sha=self._require_source_sha(),
            package_source_sha256=self._current_package_source_sha256(),
        )
        return plan

    def _require_runner(self, operation: str) -> CommandRunner:
        """返回已注入或默认 runner;操作授权仍由各入口独立控制。"""

        del operation
        return self._runner

    @contextmanager
    def _creation_lock(self, profile_id: str) -> Generator[None, None, None]:
        """在 runs/tmp 内获取进程锁,避免并发 materialization。"""

        workspace = self._require_workspace_root()
        lock_dir = workspace / "runs" / "tmp" / "autovla-runtime-profiles" / "locks"
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

        env = dict(redact_environment(os.environ))
        workspace = self._require_workspace_root()
        env.update(
            {
                "HF_DATASETS_OFFLINE": "1",
                "HF_HUB_OFFLINE": "1",
                "PIP_NO_INDEX": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "UV_CACHE_DIR": str(workspace / ".autovla_cache" / "uv"),
                "UV_OFFLINE": "1",
                "UV_PROJECT_ENVIRONMENT": str(spec.profile_root),
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
        self._reject_symlink_components(root, pyproject)
        self._reject_symlink_components(root, lock)
        if not pyproject.is_file() or not lock.is_file() or profile.lock_sha256 is None:
            raise RuntimeEnvironmentError(
                "PROFILE_LOCK_MISSING", "an accepted pyproject/uv.lock pair is required"
            )
        if _sha256(lock) != profile.lock_sha256:
            raise RuntimeEnvironmentError("PROFILE_LOCK_HASH_MISMATCH", "uv.lock digest drifted")
        if spec.profile_root.exists():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_ALREADY_EXISTS", "create never mutates an existing target"
            )

    @staticmethod
    def _reject_symlink_components(root: Path, path: Path) -> None:
        """拒绝 root 下任一路径分量通过符号链接逃逸。"""

        try:
            relative = path.relative_to(root)
        except ValueError as exc:
            raise RuntimeEnvironmentError(
                "RUNTIME_PATH_EXTERNAL", "runtime input path must remain under checkout root"
            ) from exc
        current = root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise RuntimeEnvironmentError(
                    "RUNTIME_PATH_SYMLINK",
                    "runtime project, pyproject, and lock paths must not use symbolic links",
                )

    @staticmethod
    def _write_creation_marker(marker: Path, payload: Mapping[str, object]) -> None:
        """以独占创建方式写入并同步一个小型 JSON 身份文件。"""

        with marker.open("x", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _fsync_directory(path: Path) -> None:
        """同步目录项,保证 marker 与原子发布顺序可审计。"""

        descriptor = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

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

        workspace = self._require_workspace_root()
        diagnostic_dir = workspace / "runs" / "tmp" / "autovla-runtime-profiles" / "diagnostics"
        try:
            diagnostic_dir.mkdir(parents=True, exist_ok=True)
            destination = diagnostic_dir / f"{profile_id}.last-create-failure.json"
            temporary = diagnostic_dir / f".{profile_id}.last-create-failure.tmp"
            payload = {
                "schema_version": "autovla.runtime_profile_create_failure.v1",
                "profile_id": profile_id,
                "error": error.to_dict(),
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

    def _offline_plan_environment(
        self,
        plan: EnvironmentPublicationPlan,
        environment_path: Path,
    ) -> dict[str, str]:
        """从发布计划构造删除秘密后的绝对子进程环境。"""

        workspace = self._require_workspace_root()
        env = dict(redact_environment(os.environ))
        env.update(dict(plan.child_environment))
        env["UV_CACHE_DIR"] = str(workspace / plan.cache_path)
        env["UV_PROJECT_ENVIRONMENT"] = str(environment_path)
        return env

    @staticmethod
    def _publication_path(plan: EnvironmentPublicationPlan) -> Path:
        """从 canonical ``.venv`` 路径取得不可变 lock 发布目录。"""

        environment = Path(plan.environment_path)
        if environment.name != ".venv":
            raise RuntimeEnvironmentError(
                "PUBLICATION_PLAN_IDENTITY_MISMATCH",
                "canonical environment target must end with .venv",
            )
        return environment.parent

    def _write_receipt_sidecars(
        self,
        publication_path: Path,
        receipt: RuntimeEnvironmentReceipt,
    ) -> None:
        """在 staging lock 目录内写入真实环境、包清单与验证收据。"""

        self._write_creation_marker(
            publication_path / _RECEIPT_NAME,
            receipt.to_dict(),
        )
        self._write_creation_marker(
            publication_path / _INSTALLED_PACKAGES_NAME,
            {
                "schema_version": "autovla.installed_packages.v1",
                "profile_id": receipt.profile_id,
                "lock_fingerprint": receipt.lock_fingerprint,
                "package_source_sha256": receipt.package_source_sha256,
                "installed_inventory_fingerprint": receipt.inventory_fingerprint,
                "packages": dict(receipt.installed_packages),
            },
        )
        self._write_creation_marker(
            publication_path / _VERIFICATION_NAME,
            {
                "schema_version": "autovla.runtime_environment_verification.v1",
                "profile_id": receipt.profile_id,
                "lock_fingerprint": receipt.lock_fingerprint,
                "package_source_sha256": receipt.package_source_sha256,
                "environment_receipt_fingerprint": receipt.fingerprint,
                "verification_status": receipt.verification_status,
                "diagnostics": [item.to_dict() for item in receipt.diagnostics],
            },
        )
        self._fsync_directory(publication_path)

    def _validate_plan_inputs(
        self,
        plan: EnvironmentPublicationPlan,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
    ) -> None:
        """在锁内复核计划、精确 lock 和所有发布路径。"""

        checkout = self._require_checkout_root()
        workspace = self._require_workspace_root()
        plan.validate_identity(
            profile=profile,
            lock=lock,
            source_sha=self._require_source_sha(),
            package_source_sha256=self._current_package_source_sha256(),
        )
        pyproject = checkout / plan.pyproject_path
        lock_path = checkout / plan.lock_path
        environment_root = workspace / plan.environment_root
        environment_path = workspace / plan.environment_path
        publication_path = workspace / self._publication_path(plan)
        staging_path = workspace / plan.staging_path
        for path in (pyproject, lock_path):
            self._reject_symlink_components(checkout, path)
        for path in (environment_root, publication_path, environment_path, staging_path):
            self._reject_symlink_components(workspace, path)
        if not pyproject.is_file() or _sha256(pyproject) != plan.pyproject_sha256:
            raise RuntimeEnvironmentError(
                "PUBLICATION_PLAN_PROJECT_MISMATCH",
                "pyproject content changed after publication planning",
            )
        if not lock_path.is_file() or _sha256(lock_path) != plan.lock_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_LOCK_FILE_MISMATCH",
                "resolved lock content changed after publication planning",
            )
        if publication_path.exists():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_ALREADY_EXISTS", "create never mutates an existing target"
            )
        if staging_path.exists():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_STAGING_EXISTS", "exact publication staging path must be absent"
            )

    def cache(
        self,
        profile_id: str,
        lock: ResolvedRuntimeLock,
        *,
        allow_network: bool = False,
    ) -> dict[str, object]:
        """显式联网填充 workspace UV cache,随后离线 dry-run 验证完整性。"""

        if not allow_network:
            raise RuntimeEnvironmentError(
                "RUNTIME_CACHE_NETWORK_NOT_AUTHORIZED",
                "cache priming requires --allow-network",
            )
        profile = self.require_profile(profile_id)
        checkout = self._require_checkout_root()
        workspace = self._require_workspace_root()
        plan = self.plan_create(profile_id, lock, nonce="cache-prime")
        runner = self._require_runner("cache")
        with self._creation_lock(profile_id):
            self._validate_plan_inputs(plan, profile, lock)
            environment_root = workspace / plan.environment_root
            online_path = environment_root / f".cache-prime-{profile_id}"
            offline_path = environment_root / f".cache-check-{profile_id}"
            for path in (environment_root, online_path, offline_path):
                self._reject_symlink_components(workspace, path)
            if online_path.exists() or offline_path.exists():
                raise RuntimeEnvironmentError(
                    "RUNTIME_CACHE_STAGING_EXISTS",
                    "cache staging paths must be absent",
                )
            environment_root.mkdir(parents=True, exist_ok=True)
            base_command = [
                "uv",
                "sync",
                "--locked",
                "--no-editable",
                "--no-python-downloads",
                "--project",
                plan.project_path,
                "--python",
                profile.requested_python_version,
            ]
            online_env = dict(redact_environment(os.environ))
            online_env.pop("UV_OFFLINE", None)
            for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
                if key in os.environ:
                    online_env[key] = os.environ[key]
            online_env.update(
                {
                    "HF_DATASETS_OFFLINE": "1",
                    "HF_HUB_OFFLINE": "1",
                    "PIP_NO_INDEX": "1",
                    "TRANSFORMERS_OFFLINE": "1",
                    "UV_CACHE_DIR": str(workspace / plan.cache_path),
                    "UV_PROJECT_ENVIRONMENT": str(online_path),
                    "WANDB_MODE": "disabled",
                }
            )
            offline_command = [*base_command, "--offline", "--dry-run"]
            try:
                online_result = runner(
                    base_command,
                    cwd=checkout,
                    env=online_env,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if online_result.returncode != 0:
                    raise RuntimeEnvironmentError(
                        "RUNTIME_CACHE_PRIME_FAILED",
                        "authorized uv cache priming failed",
                    )
                self._remove_staging(online_path)
                if online_path.exists():
                    raise RuntimeEnvironmentError(
                        "RUNTIME_CACHE_STAGING_CLEANUP_FAILED",
                        "online cache staging environment could not be removed",
                    )
                offline_env = dict(online_env)
                offline_env["UV_OFFLINE"] = "1"
                offline_env["UV_PROJECT_ENVIRONMENT"] = str(offline_path)
                offline_result = runner(
                    offline_command,
                    cwd=checkout,
                    env=offline_env,
                    check=False,
                    text=True,
                    capture_output=True,
                )
                if offline_result.returncode != 0:
                    raise RuntimeEnvironmentError(
                        "RUNTIME_CACHE_INCOMPLETE",
                        "offline locked cache-completeness dry run failed",
                    )
            except OSError as exc:
                raise RuntimeEnvironmentError(
                    "RUNTIME_CACHE_FAILED", "uv executable could not run"
                ) from exc
            finally:
                self._remove_staging(online_path)
                self._remove_staging(offline_path)
        return {
            "profile_id": profile.profile_id,
            "profile_fingerprint": profile.fingerprint,
            "lock_fingerprint": lock.fingerprint,
            "lock_sha256": lock.lock_sha256,
            "cache_path": plan.cache_path,
            "network_authorized": True,
            "online_command": base_command,
            "offline_completeness_command": offline_command,
            "offline_completeness_status": "pass",
        }

    def create(
        self,
        profile_id: str,
        lock: ResolvedRuntimeLock,
        *,
        nonce: str,
        allow_create: bool = False,
    ) -> RuntimeEnvironmentReceipt:
        """消费精确 lock,在 staging 验证后发布 realized environment 收据。"""

        if not allow_create:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_CREATE_NOT_AUTHORIZED", "create requires --allow-create"
            )
        profile = self.require_profile(profile_id)
        checkout = self._require_checkout_root()
        workspace = self._require_workspace_root()
        plan = self.plan_create(profile_id, lock, nonce=nonce)
        runner = self._require_runner("create")
        with self._creation_lock(profile_id):
            self._validate_plan_inputs(plan, profile, lock)
            environment_root = workspace / plan.environment_root
            profile_root = workspace / self._publication_path(plan).parent
            publication_path = workspace / self._publication_path(plan)
            environment_path = workspace / plan.environment_path
            staging_path = workspace / plan.staging_path
            staging_environment_path = staging_path / ".venv"
            profile_root.mkdir(parents=True, exist_ok=True)
            staging_path.mkdir()
            command = list(plan.command)
            result: subprocess.CompletedProcess[str] | None = None
            try:
                env = self._offline_plan_environment(plan, staging_environment_path)
                try:
                    result = runner(
                        command,
                        cwd=checkout,
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
                python = staging_environment_path / "bin" / "python"
                if not python.is_file():
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_CREATE_INCOMPLETE", "created environment has no bin/python"
                    )
                receipt = self._probe_receipt(
                    profile=profile,
                    lock=lock,
                    plan=plan,
                    environment_path=staging_environment_path,
                )
                try:
                    self._write_creation_marker(
                        staging_environment_path / _MARKER_NAME,
                        dict(plan.marker),
                    )
                    self._write_receipt_sidecars(staging_path, receipt)
                    self._fsync_directory(staging_environment_path)
                    self._fsync_directory(staging_path)
                except OSError as exc:
                    raise RuntimeEnvironmentError(
                        "ENVIRONMENT_MARKER_WRITE_FAILED",
                        "creation marker could not be written",
                    ) from exc
                try:
                    if publication_path.exists() or environment_path.exists():
                        raise RuntimeEnvironmentError(
                            "ENVIRONMENT_ALREADY_EXISTS",
                            "create never mutates an existing target",
                        )
                    os.replace(staging_path, publication_path)
                    self._fsync_directory(profile_root)
                    self._fsync_directory(environment_root)
                except RuntimeEnvironmentError:
                    raise
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
        return receipt

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
        """用目标解释器探测基础运行时与已锁定 DeepSpeed 导入。"""

        root = self._require_checkout_root()
        python = spec.profile_root / "bin" / "python"
        runner = self._require_runner("verify")
        try:
            result = runner(
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

    def _probe_receipt(
        self,
        *,
        profile: RuntimeProfileSpec,
        lock: ResolvedRuntimeLock,
        plan: EnvironmentPublicationPlan,
        environment_path: Path,
    ) -> RuntimeEnvironmentReceipt:
        """探测精确环境并构造声明-lock-environment 权威收据。"""

        root = self._require_checkout_root()
        python = environment_path / "bin" / "python"
        runner = self._require_runner("verify")
        try:
            result = runner(
                [str(python), "-I", "-c", _PROBE],
                cwd=root,
                env=self._offline_plan_environment(plan, environment_path),
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
        observed_mapping = cast("dict[str, object]", observed)
        package_root_text = observed_mapping.get("autovla_package_root")
        package_source_sha256 = observed_mapping.get("autovla_package_source_sha256")
        if (
            not isinstance(package_root_text, str)
            or not package_root_text
            or not isinstance(package_source_sha256, str)
            or package_source_sha256 != plan.package_source_sha256
            or observed_mapping.get("autovla_package_has_symlink") is not False
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PACKAGE_SOURCE_MISMATCH",
                "installed AutoVLA package bytes do not match the publication plan",
            )
        package_root = Path(package_root_text)
        try:
            environment_root = environment_path.resolve(strict=True)
            package_root.resolve(strict=True).relative_to(environment_root)
            self._reject_symlink_components(environment_root, package_root)
        except (FileNotFoundError, ValueError) as exc:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PACKAGE_SOURCE_SHADOWED",
                "AutoVLA must import from the realized non-editable environment",
            ) from exc
        if not package_root.is_dir():
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PACKAGE_SOURCE_SHADOWED",
                "AutoVLA package source root must be a realized environment directory",
            )
        raw_packages = observed_mapping.get("packages")
        if not isinstance(raw_packages, dict):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime package inventory is invalid"
            )
        package_mapping = cast("dict[object, object]", raw_packages)
        if not all(
            isinstance(name, str) and isinstance(version, str) and name and version
            for name, version in package_mapping.items()
        ):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime package inventory is invalid"
            )
        installed_packages = tuple(
            sorted(
                (
                    _normal_package_name(cast("str", name)),
                    cast("str", version),
                )
                for name, version in package_mapping.items()
            )
        )
        python_version = observed_mapping.get("python_version")
        python_implementation = observed_mapping.get("python_implementation")
        platform = observed_mapping.get("platform")
        if not all(
            isinstance(value, str) and value
            for value in (python_version, python_implementation, platform)
        ):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_PROBE_INVALID", "runtime Python identity is invalid"
            )
        receipt = RuntimeEnvironmentReceipt(
            schema_version="autovla.runtime_environment_receipt.v1",
            profile_id=profile.profile_id,
            profile_fingerprint=profile.fingerprint,
            lock_fingerprint=lock.fingerprint,
            source_sha=plan.source_sha,
            environment_path=plan.environment_path,
            installed_packages=installed_packages,
            python_implementation=cast("str", python_implementation),
            python_version=cast("str", python_version),
            platform=cast("str", platform),
            torch_version=dict(installed_packages).get("torch"),
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
            gpu_name=_optional_probe_text(observed_mapping.get("gpu_name"), "gpu_name"),
            gpu_compute_capability=_optional_probe_text(
                observed_mapping.get("gpu_compute_capability"),
                "gpu_compute_capability",
            ),
            deepspeed_compatible=_optional_probe_bool(
                observed_mapping.get("deepspeed_compatible"),
                "deepspeed_compatible",
            ),
            offline_flags=tuple(
                (key, value)
                for key, value in plan.child_environment
                if key
                in {
                    "HF_DATASETS_OFFLINE",
                    "HF_HUB_OFFLINE",
                    "PIP_NO_INDEX",
                    "TRANSFORMERS_OFFLINE",
                    "UV_OFFLINE",
                    "WANDB_MODE",
                }
            ),
            verification_status="pass",
            diagnostics=(),
            package_source_sha256=package_source_sha256,
        )
        lock.validate_profile(profile)
        receipt.validate_lock(lock)
        receipt.validate_profile(profile)
        if not receipt.python_version.startswith(lock.python_version + "."):
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PYTHON_MISMATCH",
                "realized Python version does not match the resolved lock",
            )
        if receipt.python_implementation != lock.python_implementation:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PYTHON_MISMATCH",
                "realized Python implementation does not match the resolved lock",
            )
        return receipt

    def legacy_compatibility_report(self, profile_id: str) -> RuntimeCompatibilityReport:
        """为显式 M11 适配器保留旧兼容报告,且不参与 M12 链。"""

        root = self._require_checkout_root()
        source_sha = self._require_source_sha()
        profile = self.require_profile(profile_id)
        spec = RuntimeEnvironmentSpec.for_profile(self._require_workspace_root(), profile)
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
        python = spec.profile_root / "bin" / "python"
        fingerprint = self._empty_fingerprint(profile)
        observed: dict[str, object] = {}
        if not spec.profile_root.is_dir() or not python.is_file():
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
                    observed_prefix == spec.profile_root.resolve()
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
            marker = spec.profile_root / _MARKER_NAME
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

    def _validate_existing_marker(self, plan: EnvironmentPublicationPlan) -> Path:
        """只读验证 canonical target、marker 与三个物理收据完全一致。"""

        workspace = self._require_workspace_root()
        publication_path = workspace / self._publication_path(plan)
        environment_path = workspace / plan.environment_path
        marker_path = workspace / plan.marker_path
        receipt_path = publication_path / _RECEIPT_NAME
        installed_path = publication_path / _INSTALLED_PACKAGES_NAME
        verification_path = publication_path / _VERIFICATION_NAME
        for path in (
            publication_path,
            environment_path,
            marker_path,
            receipt_path,
            installed_path,
            verification_path,
        ):
            self._reject_symlink_components(workspace, path)
        if not environment_path.is_dir() or not (environment_path / "bin/python").is_file():
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_MISSING", "verify never creates a missing environment"
            )
        try:
            marker_payload = cast(object, json.loads(marker_path.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError, TypeError) as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_MARKER_MISMATCH",
                "environment marker is absent or invalid",
            ) from exc
        if not isinstance(marker_payload, dict) or marker_payload != dict(plan.marker):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_MARKER_MISMATCH",
                "environment was not materialized from the supplied exact lock",
            )
        try:
            persisted = RuntimeEnvironmentReceipt.from_dict(
                cast("dict[str, object]", json.loads(receipt_path.read_text(encoding="utf-8")))
            )
            installed = cast(
                "dict[str, object]",
                json.loads(installed_path.read_text(encoding="utf-8")),
            )
            verification = cast(
                "dict[str, object]",
                json.loads(verification_path.read_text(encoding="utf-8")),
            )
        except (OSError, json.JSONDecodeError, TypeError, RuntimeEnvironmentError) as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_RECEIPT_SIDECAR_INVALID",
                "canonical environment receipt sidecars are absent or invalid",
            ) from exc
        expected_installed = {
            "schema_version": "autovla.installed_packages.v1",
            "profile_id": persisted.profile_id,
            "lock_fingerprint": persisted.lock_fingerprint,
            "package_source_sha256": persisted.package_source_sha256,
            "installed_inventory_fingerprint": persisted.inventory_fingerprint,
            "packages": dict(persisted.installed_packages),
        }
        expected_verification = {
            "schema_version": "autovla.runtime_environment_verification.v1",
            "profile_id": persisted.profile_id,
            "lock_fingerprint": persisted.lock_fingerprint,
            "package_source_sha256": persisted.package_source_sha256,
            "environment_receipt_fingerprint": persisted.fingerprint,
            "verification_status": persisted.verification_status,
            "diagnostics": [item.to_dict() for item in persisted.diagnostics],
        }
        if (
            persisted.environment_path != plan.environment_path
            or persisted.profile_id != plan.profile_id
            or persisted.profile_fingerprint != plan.profile_fingerprint
            or persisted.lock_fingerprint != plan.lock_fingerprint
            or persisted.source_sha != plan.source_sha
            or persisted.package_source_sha256 != plan.package_source_sha256
            or installed != expected_installed
            or verification != expected_verification
        ):
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_RECEIPT_SIDECAR_MISMATCH",
                "canonical environment sidecars do not match the publication plan",
            )
        return environment_path

    def verify(
        self,
        profile_id: str,
        lock: ResolvedRuntimeLock,
    ) -> RuntimeEnvironmentReceipt:
        """只读验证精确 lock 对应环境并返回 realized environment 收据。"""

        profile = self.require_profile(profile_id)
        plan = self._plan_existing(profile, lock)
        environment_path = self._validate_existing_marker(plan)
        return self._probe_receipt(
            profile=profile,
            lock=lock,
            plan=plan,
            environment_path=environment_path,
        )

    @staticmethod
    def _is_training_command(command: Sequence[str]) -> bool:
        """识别转换画像不得执行的生产训练入口。"""

        joined = " ".join(command)
        return bool(command) and (
            Path(command[0]).name == "autovla-train" or "autovla.cli.train" in joined
        )

    def _prepare_execution_evidence(self, evidence_path: str) -> tuple[Path, str | None]:
        """在 runner 前验证受管证据路径并记录既有内容摘要。"""

        root = self._require_checkout_root()
        evidence = Path(evidence_path)
        if (
            evidence.is_absolute()
            or evidence.as_posix() != evidence_path
            or not evidence.parts
            or evidence.parts[0] != "runs"
            or any(part in {"", ".", ".."} for part in evidence.parts)
        ):
            raise RuntimeEnvironmentError(
                "RUNTIME_PATH_INVALID",
                "evidence_path must be a canonical repository-relative runs path",
            )
        absolute = root / evidence
        self._reject_symlink_components(root, absolute)
        if not absolute.exists():
            return absolute, None
        try:
            mode = absolute.lstat().st_mode
        except OSError as exc:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_EVIDENCE_INVALID",
                "pre-existing execution evidence cannot be inspected",
            ) from exc
        if not stat.S_ISREG(mode):
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_EVIDENCE_INVALID",
                "execution evidence must be a regular non-symlink file",
            )
        return absolute, _sha256(absolute)

    def _validate_execution_evidence(
        self,
        absolute_evidence: Path,
        previous_sha256: str | None,
    ) -> str:
        """验证 runner 后证据为新建或内容发生变化的普通文件。"""

        root = self._require_checkout_root()
        self._reject_symlink_components(root, absolute_evidence)
        try:
            mode = absolute_evidence.lstat().st_mode
        except OSError as exc:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_EVIDENCE_MISSING",
                "execution evidence file is absent",
            ) from exc
        if not stat.S_ISREG(mode):
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_EVIDENCE_INVALID",
                "execution evidence must be a regular non-symlink file",
            )
        current_sha256 = _sha256(absolute_evidence)
        if previous_sha256 is not None and current_sha256 == previous_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_EVIDENCE_STALE",
                "pre-existing evidence was not changed by this execution",
            )
        return current_sha256

    def _execution_working_directory(self, lock_fingerprint: str) -> Path:
        """创建不位于 checkout 的受管执行工作目录。"""

        workspace = self._require_workspace_root()
        working = (
            workspace / "runs" / "tmp" / "autovla-runtime-profiles" / "exec" / lock_fingerprint
        )
        self._reject_symlink_components(workspace, working)
        working.mkdir(parents=True, exist_ok=True)
        self._reject_symlink_components(workspace, working)
        for shadow_name in ("autovla", "autovla.py"):
            if (working / shadow_name).exists() or (working / shadow_name).is_symlink():
                raise RuntimeEnvironmentError(
                    "RUNTIME_EXECUTION_WORKDIR_SHADOWED",
                    "execution working directory must not contain an AutoVLA shadow",
                )
        return working

    def exec(
        self,
        profile_id: str,
        lock: ResolvedRuntimeLock,
        environment: RuntimeEnvironmentReceipt,
        command: Sequence[str],
        *,
        asset_fingerprint: str,
        topology_fingerprint: str,
        evidence_path: str,
        operation: str,
    ) -> RuntimeExecutionReceipt:
        """消费通过环境收据执行命令,并绑定实际证据内容摘要。"""

        if not command:
            raise RuntimeEnvironmentError("COMMAND_REQUIRED", "exec requires a command")
        root = self._require_checkout_root()
        profile = self.require_profile(profile_id)
        if not profile.is_training_runtime and self._is_training_command(command):
            raise RuntimeEnvironmentError(
                "CONVERSION_TRAINING_FORBIDDEN",
                "Pi0.5 conversion profile is never a production training runtime",
            )
        lock.validate_profile(profile)
        environment.validate_lock(lock)
        environment.validate_profile(profile)
        if environment.verification_status != "pass":
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_INCOMPATIBLE", "exec requires a passing environment receipt"
            )
        if environment.source_sha != self._require_source_sha():
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_SOURCE_MISMATCH",
                "environment receipt source does not match the checkout",
            )
        package_source_sha256 = RuntimeExecutionReceipt.validate_request(
            profile=profile,
            lock=lock,
            environment=environment,
            source_sha=self._require_source_sha(),
            asset_fingerprint=asset_fingerprint,
            command=command,
            topology_fingerprint=topology_fingerprint,
            evidence_path=evidence_path,
            operation=operation,
        )
        current_package_source = self._current_package_source_sha256()
        if package_source_sha256 != current_package_source:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_PACKAGE_SOURCE_MISMATCH",
                "environment package source does not match the current checkout bytes",
            )
        absolute_evidence, previous_evidence_sha256 = self._prepare_execution_evidence(
            evidence_path
        )
        plan = self._plan_existing(profile, lock)
        environment_path = self._validate_existing_marker(plan)
        if environment.environment_path != plan.environment_path:
            raise RuntimeEnvironmentError(
                "RUNTIME_ENVIRONMENT_PATH_MISMATCH",
                "environment receipt path does not match the publication plan",
            )
        if plan.package_source_sha256 != package_source_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_PACKAGE_SOURCE_MISMATCH",
                "publication plan package source does not match the environment receipt",
            )
        env = self._offline_plan_environment(plan, environment_path)
        env["PATH"] = str(environment_path / "bin") + os.pathsep + env.get("PATH", "")
        env["VIRTUAL_ENV"] = str(environment_path)
        env["AUTOVLA_CHECKOUT_ROOT"] = str(root)
        execution_cwd = self._execution_working_directory(lock.fingerprint)
        runner = self._require_runner("exec")
        try:
            result = runner(
                list(command),
                cwd=execution_cwd,
                env=env,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeEnvironmentError(
                "ENVIRONMENT_EXEC_FAILED", "verified command could not start"
            ) from exc
        if self._current_package_source_sha256() != package_source_sha256:
            raise RuntimeEnvironmentError(
                "RUNTIME_EXECUTION_PACKAGE_SOURCE_CHANGED",
                "checkout package source changed during execution",
            )
        evidence_sha256 = self._validate_execution_evidence(
            absolute_evidence,
            previous_evidence_sha256,
        )
        status = "pass" if result.returncode == 0 else "fail"
        diagnostics = (
            ()
            if result.returncode == 0
            else (
                RuntimeDiagnostic(
                    "RUNTIME_COMMAND_NONZERO",
                    f"runtime command returned {result.returncode}",
                ),
            )
        )
        return RuntimeExecutionReceipt.from_command(
            profile=profile,
            lock=lock,
            environment=environment,
            source_sha=self._require_source_sha(),
            asset_fingerprint=asset_fingerprint,
            command=command,
            topology_fingerprint=topology_fingerprint,
            evidence_path=evidence_path,
            evidence_sha256=evidence_sha256,
            operation=operation,
            status=status,
            diagnostics=diagnostics,
        )


class LegacyRuntimeProfileAdapter:
    """集中暴露 M11 只读兼容面,不生成或推断 M12 精确 lock。"""

    def __init__(self, manager: RuntimeEnvironmentManager) -> None:
        """绑定单一 manager,不复制其画像或环境状态。"""

        self._manager = manager

    def list_profiles(self) -> tuple[FamilyRuntimeProfile, ...]:
        """沿用 M11 画像列表。"""

        return self._manager.list_profiles()

    def inspect(self, profile_id: str) -> dict[str, object]:
        """沿用 M11 静态检查结果。"""

        return self._manager.inspect(profile_id)

    def verify(self, profile_id: str) -> RuntimeCompatibilityReport:
        """显式请求旧兼容报告,不进入 M12 环境收据链。"""

        return self._manager.legacy_compatibility_report(profile_id)

    @staticmethod
    def create(profile_id: str, *, allow_create: bool = False) -> None:
        """拒绝从 M11 画像状态推断精确 lock。"""

        del profile_id, allow_create
        raise RuntimeEnvironmentError(
            "M12_EXACT_LOCK_REQUIRED",
            "legacy adapter cannot create an environment without an exact M12 lock",
        )

    @staticmethod
    def exec(profile_id: str, command: Sequence[str]) -> None:
        """拒绝从旧兼容报告提升为执行授权。"""

        del profile_id, command
        raise RuntimeEnvironmentError(
            "M12_ENVIRONMENT_RECEIPT_REQUIRED",
            "legacy adapter cannot execute without an M12 environment receipt",
        )


__all__ = [
    "CommandRunner",
    "LegacyRuntimeProfileAdapter",
    "OfflineSubprocessRunner",
    "RuntimeEnvironmentManager",
]
