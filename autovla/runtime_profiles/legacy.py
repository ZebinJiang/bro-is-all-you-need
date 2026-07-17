"""M8/M10 环境 profile 读取接口的只读兼容层。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILE_DIR = REPO_ROOT / "configs" / "env" / "profiles"
FORBIDDEN_PROFILE_IDS = {"all-model-zoo", "model-zoo-all", "autovla-all-models"}
REQUIRED_PROFILE_FIELDS = {
    "profile_id",
    "uv_project",
    "python_version",
    "dependency_tier",
    "default_sync",
    "requires_manual_authorization",
    "allowed_commands",
    "forbidden_commands",
    "expected_assets",
    "dependency_risk",
    "lock_status",
    "install_status",
    "notes",
}
REQUIRED_ENVIRONMENT_FIELDS = {
    "manager",
    "profile",
    "uv_project",
    "uv_environment",
    "sync_policy",
    "locked",
    "offline",
    "command_prefix",
}
LIST_FIELDS = {
    "allowed_commands",
    "forbidden_commands",
    "expected_assets",
    "command_prefix",
    "exact_packages",
    "prohibited_packages",
    "runtime_blockers",
}


@dataclass(frozen=True)
class EnvProfile:
    """保留旧配置测试需要的环境画像字段。"""

    profile_id: str
    uv_project: str
    python_version: str
    dependency_tier: str
    default_sync: str
    requires_manual_authorization: bool
    allowed_commands: tuple[str, ...]
    forbidden_commands: tuple[str, ...]
    expected_assets: tuple[str, ...]
    dependency_risk: str
    lock_status: str
    install_status: str
    notes: str

    @classmethod
    def from_mapping(cls, values: dict[str, Any]) -> "EnvProfile":
        """从旧 YAML 顶层字段构造兼容对象。"""

        missing = sorted(REQUIRED_PROFILE_FIELDS - values.keys())
        if missing:
            raise ValueError(f"profile missing required fields: {', '.join(missing)}")
        profile_id = _require_string(values, "profile_id")
        if profile_id in FORBIDDEN_PROFILE_IDS:
            raise ValueError("all-model-zoo profile is forbidden")
        dependency_tier = _require_string(values, "dependency_tier")
        requires_manual_authorization = _require_bool(values, "requires_manual_authorization")
        dependency_risk = _require_string(values, "dependency_risk")
        if dependency_tier in {"model", "training", "asset-acquisition"} and not (
            requires_manual_authorization
        ):
            raise ValueError(f"{dependency_tier} profile must require manual authorization")
        if dependency_risk == "high" and not requires_manual_authorization:
            raise ValueError("high-risk profile must require manual authorization")
        return cls(
            profile_id=profile_id,
            uv_project=_require_string(values, "uv_project"),
            python_version=_require_string(values, "python_version"),
            dependency_tier=dependency_tier,
            default_sync=_require_string(values, "default_sync"),
            requires_manual_authorization=requires_manual_authorization,
            allowed_commands=tuple(_require_string_list(values, "allowed_commands")),
            forbidden_commands=tuple(_require_string_list(values, "forbidden_commands")),
            expected_assets=tuple(_require_string_list(values, "expected_assets")),
            dependency_risk=dependency_risk,
            lock_status=_require_string(values, "lock_status"),
            install_status=_require_string(values, "install_status"),
            notes=_require_string(values, "notes"),
        )

    def as_json(self) -> dict[str, Any]:
        """返回旧 CLI 使用的稳定 JSON。"""

        return {
            "profile_id": self.profile_id,
            "uv_project": self.uv_project,
            "python_version": self.python_version,
            "dependency_tier": self.dependency_tier,
            "default_sync": self.default_sync,
            "requires_manual_authorization": self.requires_manual_authorization,
            "allowed_commands": list(self.allowed_commands),
            "forbidden_commands": list(self.forbidden_commands),
            "expected_assets": list(self.expected_assets),
            "dependency_risk": self.dependency_risk,
            "lock_status": self.lock_status,
            "install_status": self.install_status,
            "notes": self.notes,
        }


def _require_string(values: dict[str, Any], field: str) -> str:
    """读取旧配置非空字符串。"""

    value = values[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_bool(values: dict[str, Any], field: str) -> bool:
    """读取旧配置布尔值。"""

    value = values[field]
    if type(value) is not bool:
        raise ValueError(f"{field} must be a boolean")
    return value


def _require_string_list(values: dict[str, Any], field: str) -> list[str]:
    """读取旧配置字符串列表。"""

    value = values[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string list")
    return value


def _parse_scalar(raw: str) -> str | bool:
    """解析受控 YAML 标量。"""

    text = raw.strip()
    if text in {"true", "false"}:
        return text == "true"
    if len(text) >= 2 and text[0] == text[-1] and text[0] in {'"', "'"}:
        return text[1:-1]
    return text


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    """解析旧 profile/fine-tune 配置需要的两层 YAML 子集。"""

    result: dict[str, Any] = {}
    stack: list[dict[str, Any]] = [result]
    list_key: str | None = None
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        line = raw_line.strip()
        if line.startswith("- "):
            if list_key is None:
                raise ValueError(f"list item without key in {path}")
            current_list = stack[-1].setdefault(list_key, [])
            if not isinstance(current_list, list):
                raise ValueError(f"{list_key} is not a list in {path}")
            current_list.append(str(_parse_scalar(line[2:])))
            continue
        if ":" not in line:
            raise ValueError(f"unsupported YAML line in {path}: {line}")
        key, raw_value = line.split(":", 1)
        if indent == 0:
            stack = [result]
        elif indent == 2:
            if len(stack) == 1:
                parent_key = next(reversed(result))
                nested = result.setdefault(parent_key, {})
                if not isinstance(nested, dict):
                    raise ValueError(f"{parent_key} is not a mapping in {path}")
                stack = [result, nested]
        else:
            raise ValueError(f"unsupported indentation in {path}: {raw_line}")
        current = stack[-1]
        if raw_value.strip() == "":
            current[key] = [] if key in LIST_FIELDS else {}
            list_key = key
        else:
            current[key] = _parse_scalar(raw_value)
            list_key = None
            if raw_value.strip() == "[]":
                current[key] = []
                list_key = key
    return result


def load_profiles() -> dict[str, EnvProfile]:
    """加载旧 profile 集合;M11 新闭集由独立注册表拥有。"""

    profiles: dict[str, EnvProfile] = {}
    for path in sorted(PROFILE_DIR.glob("*.yaml")):
        profile = EnvProfile.from_mapping(parse_simple_yaml(path))
        if profile.profile_id in profiles:
            raise ValueError(f"duplicate profile: {profile.profile_id}")
        profiles[profile.profile_id] = profile
    if not profiles:
        raise ValueError("no env profiles found")
    return profiles


def validate_finetune_config(path: Path, profiles: dict[str, EnvProfile]) -> dict[str, Any]:
    """保留旧 fine-tune 环境选择器的 fail-closed 校验。"""

    data = parse_simple_yaml(path)
    env = data.get("environment")
    if not isinstance(env, dict):
        raise ValueError("environment block is required")
    missing = sorted(REQUIRED_ENVIRONMENT_FIELDS - env.keys())
    if missing:
        raise ValueError(f"environment missing required fields: {', '.join(missing)}")
    if env["manager"] != "uv":
        raise ValueError("environment.manager must be uv")
    profile_id = _require_string(env, "profile")
    if profile_id not in profiles:
        raise ValueError(f"unknown profile: {profile_id}")
    profile = profiles[profile_id]
    if env["uv_project"] != profile.uv_project:
        raise ValueError("environment.uv_project must match profile")
    if env["sync_policy"] != "manual" or env["locked"] is not True or env["offline"] is not True:
        raise ValueError("environment must be manual, locked, and offline")
    prefix = env["command_prefix"]
    if not isinstance(prefix, list) or any(not isinstance(item, str) for item in prefix):
        raise ValueError("environment.command_prefix must be a string list")
    return {"environment": env, "profile": profile.as_json()}


def render_command(profile: EnvProfile, command: list[str]) -> list[str]:
    """保留旧 locked uv 命令渲染,不执行命令。"""

    if not command:
        raise ValueError("command is required")
    if command[0] in profile.forbidden_commands:
        raise ValueError(f"command is forbidden for profile {profile.profile_id}: {command[0]}")
    return ["uv", "run", "--project", profile.uv_project, "--locked", *command]


__all__ = [
    "FORBIDDEN_PROFILE_IDS",
    "EnvProfile",
    "load_profiles",
    "parse_simple_yaml",
    "render_command",
    "validate_finetune_config",
]
