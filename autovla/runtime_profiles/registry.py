"""四个 M11 运行时画像的无依赖注册表。"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

from autovla.runtime_profiles.contracts import FamilyRuntimeProfile, ProfileKind
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

PROFILE_FILES = (
    "model-gr00t-n1d6.yaml",
    "model-gr00t-n1d7.yaml",
    "model-pi0-5.yaml",
    "pi0-5-conversion.yaml",
)
EXPECTED_PROFILE_IDS = (
    "gr00t_n1d6_runtime",
    "gr00t_n1d7_runtime",
    "pi0_5_runtime",
    "pi0_5_conversion",
)
_LIST_FIELDS = {
    "allowed_commands",
    "exact_packages",
    "observed_lock_packages",
    "expected_assets",
    "forbidden_commands",
    "prohibited_packages",
    "runtime_blockers",
}


def _scalar(raw: str) -> str | bool:
    """解析画像 YAML 使用的受控标量子集。"""

    text = raw.strip()
    if text in {"true", "false"}:
        return text == "true"
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def _load_flat_yaml(path: Path) -> dict[str, Any]:
    """解析顶层标量和字符串列表，拒绝隐式复杂 YAML。"""

    result: dict[str, Any] = {}
    active_list: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        line = raw_line.strip()
        if line.startswith("- "):
            if active_list is None:
                raise RuntimeEnvironmentError("PROFILE_PARSE_ERROR", f"orphan list item in {path}")
            result[active_list].append(str(_scalar(line[2:])))
            continue
        if raw_line != raw_line.lstrip(" ") or ":" not in line:
            raise RuntimeEnvironmentError("PROFILE_PARSE_ERROR", f"unsupported YAML in {path}")
        key, raw_value = line.split(":", 1)
        if not raw_value.strip():
            if key not in _LIST_FIELDS:
                raise RuntimeEnvironmentError(
                    "PROFILE_PARSE_ERROR", f"unsupported mapping field {key!r} in {path}"
                )
            result[key] = []
            active_list = key
        elif raw_value.strip() == "[]" and key in _LIST_FIELDS:
            result[key] = []
            active_list = None
        else:
            result[key] = _scalar(raw_value)
            active_list = None
    return result


def _required_string(values: dict[str, Any], key: str, path: Path) -> str:
    """读取非空字符串字段。"""

    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{path}: {key} must be a string")
    return value


def _required_bool(values: dict[str, Any], key: str, path: Path) -> bool:
    """读取严格布尔字段。"""

    value = values.get(key)
    if type(value) is not bool:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{path}: {key} must be a boolean")
    return value


def _string_list(values: dict[str, Any], key: str, path: Path) -> tuple[str, ...]:
    """读取纯字符串列表。"""

    value = values.get(key, [])
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{path}: {key} must be a string list")
    return tuple(value)


def _profile_from_file(repository_root: Path, relative_path: Path) -> FamilyRuntimeProfile:
    """把单个受控描述文件转换为类型化画像。"""

    path = repository_root / relative_path
    values = _load_flat_yaml(path)
    exact_packages: list[tuple[str, str]] = []
    for pin in _string_list(values, "exact_packages", relative_path):
        if "==" not in pin:
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", f"{relative_path}: exact package pin must use =="
            )
        name, version = pin.split("==", 1)
        exact_packages.append((name.lower().replace("_", "-"), version))
    observed_lock_packages: list[tuple[str, str]] = []
    for pin in _string_list(values, "observed_lock_packages", relative_path):
        if "==" not in pin:
            raise RuntimeEnvironmentError(
                "PROFILE_INVALID", f"{relative_path}: observed lock pin must use =="
            )
        name, version = pin.split("==", 1)
        observed_lock_packages.append((name.lower().replace("_", "-"), version))
    lock_sha = _required_string(values, "runtime_lock_sha256", relative_path)
    if lock_sha == "unresolved":
        normalized_lock_sha: str | None = None
    elif len(lock_sha) == 64 and all(char in "0123456789abcdef" for char in lock_sha):
        normalized_lock_sha = lock_sha
    else:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{relative_path}: invalid lock sha256")
    kind = _required_string(values, "runtime_profile_kind", relative_path)
    if kind not in {"training_runtime", "conversion"}:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{relative_path}: invalid profile kind")
    return FamilyRuntimeProfile(
        profile_id=_required_string(values, "runtime_profile_id", relative_path),
        family_key=_required_string(values, "runtime_family_key", relative_path),
        kind=cast("ProfileKind", kind),
        descriptor_path=relative_path,
        uv_project=Path(_required_string(values, "uv_project", relative_path)),
        requested_python_version=_required_string(values, "python_version", relative_path),
        lock_status=_required_string(values, "runtime_lock_status", relative_path),
        lock_sha256=normalized_lock_sha,
        lock_accepted=_required_bool(values, "runtime_lock_accepted", relative_path),
        exact_packages=tuple(sorted(exact_packages)),
        observed_lock_packages=tuple(sorted(observed_lock_packages)),
        prohibited_packages=tuple(
            sorted(
                name.lower().replace("_", "-")
                for name in _string_list(values, "prohibited_packages", relative_path)
            )
        ),
        blockers=_string_list(values, "runtime_blockers", relative_path),
        asset_license_gate_status=_required_string(
            values, "asset_license_gate_status", relative_path
        ),
        requires_cuda=_required_bool(values, "requires_cuda", relative_path),
    )


def load_runtime_profiles(repository_root: Path) -> dict[str, FamilyRuntimeProfile]:
    """只加载 M11 合同列出的四个画像并验证身份闭集。"""

    config_root = Path("configs/env/profiles")
    profiles: dict[str, FamilyRuntimeProfile] = {}
    for filename in PROFILE_FILES:
        profile = _profile_from_file(repository_root.resolve(), config_root / filename)
        if profile.profile_id in profiles:
            raise RuntimeEnvironmentError("PROFILE_DUPLICATE", profile.profile_id)
        profiles[profile.profile_id] = profile
    if tuple(sorted(profiles)) != tuple(sorted(EXPECTED_PROFILE_IDS)):
        raise RuntimeEnvironmentError(
            "PROFILE_SET_INVALID", "runtime profile ids do not match the M11 closed set"
        )
    runtime_pi = profiles["pi0_5_runtime"]
    required_prohibitions = {"jax", "flax", "orbax", "orbax-checkpoint"}
    if not required_prohibitions.issubset(runtime_pi.prohibited_packages):
        raise RuntimeEnvironmentError(
            "PI_RUNTIME_DEPENDENCY_POLICY_INVALID",
            "Pi0.5 training runtime must prohibit JAX, Flax, and Orbax",
        )
    if profiles["pi0_5_conversion"].is_training_runtime:
        raise RuntimeEnvironmentError(
            "CONVERSION_TRAINING_FORBIDDEN", "Pi0.5 conversion cannot be a training runtime"
        )
    return profiles


__all__ = ["EXPECTED_PROFILE_IDS", "PROFILE_FILES", "load_runtime_profiles"]
