"""M11 运行时画像的包内只读注册表。"""

from __future__ import annotations

import hashlib
import json
from importlib.resources import files
from pathlib import Path
from typing import cast

from autovla.runtime_profiles.contracts import ProfileKind, RuntimeProfileSpec
from autovla.runtime_profiles.errors import RuntimeEnvironmentError

PROFILE_RESOURCE = "runtime_profiles/profiles.json"
EXPECTED_PROFILE_IDS = (
    "gr00t_n1d6_runtime",
    "gr00t_n1d7_runtime",
    "pi0_5_runtime",
    "pi0_5_conversion",
)
_REGISTRY_FIELDS = frozenset({"schema_version", "profiles"})
_PROFILE_FIELDS = frozenset(
    {
        "schema_version",
        "runtime_profile_id",
        "runtime_family_key",
        "runtime_profile_kind",
        "uv_project",
        "python_version",
        "python_implementation",
        "platform_intent",
        "resolver_name",
        "resolver_version",
        "upstream_revision",
        "runtime_lock_status",
        "runtime_lock_sha256",
        "runtime_lock_accepted",
        "exact_packages",
        "observed_lock_packages",
        "prohibited_packages",
        "runtime_blockers",
        "asset_license_gate_status",
        "requires_cuda",
    }
)


def _resource_text() -> str:
    """读取随 wheel 分发的唯一画像描述源。"""

    resource = files("autovla.resources")
    for part in PROFILE_RESOURCE.split("/"):
        resource = resource.joinpath(part)
    if not resource.is_file():
        raise RuntimeEnvironmentError(
            "PROFILE_RESOURCE_MISSING", "packaged runtime profile descriptor is absent"
        )
    try:
        return resource.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeEnvironmentError(
            "PROFILE_RESOURCE_UNREADABLE", "packaged runtime profile descriptor cannot be read"
        ) from exc


def runtime_profile_descriptor_sha256() -> str:
    """返回包内画像描述源的稳定摘要。"""

    return hashlib.sha256(_resource_text().encode("utf-8")).hexdigest()


def _string_list(values: dict[str, object], key: str) -> tuple[str, ...]:
    """读取严格字符串列表。"""

    value = values.get(key, [])
    if not isinstance(value, list):
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} must be a string list")
    items = cast("list[object]", value)
    if not all(isinstance(item, str) for item in items):
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} must be a string list")
    return tuple(cast("list[str]", items))


def _string_object(values: object, message: str) -> dict[str, object]:
    """验证 JSON 对象只使用字符串键并收窄值类型。"""

    if not isinstance(values, dict):
        raise RuntimeEnvironmentError("PROFILE_PARSE_ERROR", message)
    untyped_values = cast("dict[object, object]", values)
    if not all(isinstance(key, str) for key in untyped_values):
        raise RuntimeEnvironmentError("PROFILE_PARSE_ERROR", message)
    return cast("dict[str, object]", untyped_values)


def _object_list(values: object, message: str) -> list[object]:
    """验证 JSON 数组并将元素保留为待验证对象。"""

    if not isinstance(values, list):
        raise RuntimeEnvironmentError("PROFILE_PARSE_ERROR", message)
    return cast("list[object]", values)


def _required_string(values: dict[str, object], key: str) -> str:
    """读取严格非空字符串。"""

    value = values.get(key)
    if not isinstance(value, str) or not value:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} must be a string")
    return value


def _required_bool(values: dict[str, object], key: str) -> bool:
    """读取严格布尔值。"""

    value = values.get(key)
    if type(value) is not bool:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} must be a boolean")
    return value


def _optional_string(values: dict[str, object], key: str) -> str | None:
    """读取严格可空字符串。"""

    value = values.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} must be a string or null")
    return value


def _require_exact_fields(
    values: dict[str, object],
    expected: frozenset[str],
    *,
    label: str,
) -> None:
    """拒绝注册表缺字段与未知字段。"""

    missing = sorted(expected - values.keys())
    unknown = sorted(values.keys() - expected)
    if missing or unknown:
        raise RuntimeEnvironmentError(
            "PROFILE_FIELDS_INVALID",
            f"{label} fields invalid: missing={missing}, unknown={unknown}",
        )


def _package_pairs(values: dict[str, object], key: str) -> tuple[tuple[str, str], ...]:
    """解析并规范化精确包版本列表。"""

    pairs: list[tuple[str, str]] = []
    for pin in _string_list(values, key):
        if "==" not in pin:
            raise RuntimeEnvironmentError("PROFILE_INVALID", f"{key} pins must use ==")
        name, version = pin.split("==", 1)
        pairs.append((name.lower().replace("_", "-"), version))
    return tuple(sorted(pairs))


def _profile(values: dict[str, object]) -> RuntimeProfileSpec:
    """把单个包内记录转换为类型化画像。"""

    _require_exact_fields(values, _PROFILE_FIELDS, label="profile")
    lock_sha = _required_string(values, "runtime_lock_sha256")
    if lock_sha == "unresolved":
        normalized_lock_sha: str | None = None
    elif len(lock_sha) == 64 and all(char in "0123456789abcdef" for char in lock_sha):
        normalized_lock_sha = lock_sha
    else:
        raise RuntimeEnvironmentError("PROFILE_INVALID", "invalid lock sha256")
    kind = _required_string(values, "runtime_profile_kind")
    if kind not in {"training_runtime", "conversion"}:
        raise RuntimeEnvironmentError("PROFILE_INVALID", "invalid profile kind")
    return RuntimeProfileSpec(
        profile_id=_required_string(values, "runtime_profile_id"),
        family_key=_required_string(values, "runtime_family_key"),
        kind=cast("ProfileKind", kind),
        descriptor_path=Path("autovla/resources") / PROFILE_RESOURCE,
        uv_project=Path(_required_string(values, "uv_project")),
        requested_python_version=_required_string(values, "python_version"),
        lock_status=_required_string(values, "runtime_lock_status"),
        lock_sha256=normalized_lock_sha,
        lock_accepted=_required_bool(values, "runtime_lock_accepted"),
        exact_packages=_package_pairs(values, "exact_packages"),
        observed_lock_packages=_package_pairs(values, "observed_lock_packages"),
        prohibited_packages=tuple(
            sorted(
                name.lower().replace("_", "-")
                for name in _string_list(values, "prohibited_packages")
            )
        ),
        blockers=_string_list(values, "runtime_blockers"),
        asset_license_gate_status=_required_string(values, "asset_license_gate_status"),
        requires_cuda=_required_bool(values, "requires_cuda"),
        schema_version=_required_string(values, "schema_version"),
        python_implementation=_required_string(values, "python_implementation"),
        platform_intent=_required_string(values, "platform_intent"),
        resolver_name=_required_string(values, "resolver_name"),
        resolver_version=_optional_string(values, "resolver_version"),
        upstream_revision=_optional_string(values, "upstream_revision"),
    )


def load_runtime_profiles(_repository_root: Path | None = None) -> dict[str, RuntimeProfileSpec]:
    """从安装包资源加载画像闭集,不推断或读取 checkout。"""

    try:
        payload = cast(object, json.loads(_resource_text()))
    except (json.JSONDecodeError, TypeError) as exc:
        raise RuntimeEnvironmentError(
            "PROFILE_PARSE_ERROR", "packaged runtime profile descriptor is invalid JSON"
        ) from exc
    root = _string_object(payload, "profile resource shape is invalid")
    _require_exact_fields(root, _REGISTRY_FIELDS, label="registry")
    if root["schema_version"] != "autovla.runtime_profile_registry.v2":
        raise RuntimeEnvironmentError("PROFILE_INVALID", "unsupported runtime profile registry")
    raw_profiles = _object_list(root.get("profiles"), "profile resource shape is invalid")
    profiles: dict[str, RuntimeProfileSpec] = {}
    for raw_profile in raw_profiles:
        profile = _profile(_string_object(raw_profile, "profile record must be an object"))
        if profile.profile_id in profiles:
            raise RuntimeEnvironmentError("PROFILE_DUPLICATE", profile.profile_id)
        profiles[profile.profile_id] = profile
    if tuple(sorted(profiles)) != tuple(sorted(EXPECTED_PROFILE_IDS)):
        raise RuntimeEnvironmentError(
            "PROFILE_SET_INVALID", "runtime profile ids do not match the M11 closed set"
        )
    runtime_pi = profiles["pi0_5_runtime"]
    if not {"jax", "flax", "orbax", "orbax-checkpoint"}.issubset(runtime_pi.prohibited_packages):
        raise RuntimeEnvironmentError(
            "PI_RUNTIME_DEPENDENCY_POLICY_INVALID",
            "Pi0.5 training runtime must prohibit JAX, Flax, and Orbax",
        )
    if profiles["pi0_5_conversion"].is_training_runtime:
        raise RuntimeEnvironmentError(
            "CONVERSION_TRAINING_FORBIDDEN", "Pi0.5 conversion cannot be a training runtime"
        )
    return profiles


__all__ = [
    "EXPECTED_PROFILE_IDS",
    "PROFILE_RESOURCE",
    "load_runtime_profiles",
    "runtime_profile_descriptor_sha256",
]
