"""AutoVLA uv 环境 profile 的只读治理工具。

该脚本只解析仓库内的 env profile 和 fine-tune 环境选择块, 不执行依赖
安装、模型加载、网络下载或训练。`sync-profile` 默认 fail-closed, 只有显式
传入 `--allow-sync` 且 profile 允许同步时才会打印后续人工命令。
"""

from __future__ import annotations

import argparse
import json
import sys
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
}


@dataclass(frozen=True)
class EnvProfile:
    """描述一个可审计的 uv 环境 profile。"""

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
        missing = sorted(REQUIRED_PROFILE_FIELDS - values.keys())
        if missing:
            raise ValueError(f"profile missing required fields: {', '.join(missing)}")
        profile_id = _require_string(values, "profile_id")
        if profile_id in FORBIDDEN_PROFILE_IDS:
            raise ValueError("all-model-zoo profile is forbidden")
        dependency_tier = _require_string(values, "dependency_tier")
        if dependency_tier not in {"core", "data", "model", "training", "asset-acquisition"}:
            raise ValueError(f"unsupported dependency_tier: {dependency_tier}")
        dependency_risk = _require_string(values, "dependency_risk")
        requires_manual_authorization = _require_bool(values, "requires_manual_authorization")
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
        """返回稳定 JSON 结构, 供 CLI 和测试比较。"""

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
    value = values[field]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_bool(values: dict[str, Any], field: str) -> bool:
    value = values[field]
    if not isinstance(value, bool):
        raise ValueError(f"{field} must be a boolean")
    return value


def _require_string_list(values: dict[str, Any], field: str) -> list[str]:
    value = values[field]
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise ValueError(f"{field} must be a string list")
    return value


def _parse_scalar(raw: str) -> str | bool:
    text = raw.strip()
    if text in {"true", "false"}:
        return text == "true"
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    return text


def parse_simple_yaml(path: Path) -> dict[str, Any]:
    """解析受控 profile/config YAML 子集。

    支持顶层 key、一个嵌套 mapping、以及 `- item` 字符串列表。这个解析器故意
    很小, 避免为治理 profile 引入运行时依赖。
    """

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
            list_key = key if isinstance(current[key], list) else None
            if raw_value.strip() == "[]":
                current[key] = []
                list_key = key
    return result


def load_profiles() -> dict[str, EnvProfile]:
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
    if profile_id in FORBIDDEN_PROFILE_IDS:
        raise ValueError("all-model-zoo profile is forbidden")
    if profile.dependency_tier in {"model", "training", "asset-acquisition"} and not (
        profile.requires_manual_authorization
    ):
        raise ValueError("high-risk runtime profile must require manual authorization")
    if profile.install_status not in {"not_installed", "manual_only", "installed"}:
        raise ValueError("unknown dependency install status")
    if env["uv_project"] != profile.uv_project:
        raise ValueError("environment.uv_project must match profile")
    if env["sync_policy"] != "manual":
        raise ValueError("environment.sync_policy must be manual")
    if env["locked"] is not True:
        raise ValueError("environment.locked must be true")
    if env["offline"] is not True:
        raise ValueError("environment.offline must be true")
    prefix = env["command_prefix"]
    if not isinstance(prefix, list) or any(not isinstance(item, str) for item in prefix):
        raise ValueError("environment.command_prefix must be a string list")
    return {"environment": env, "profile": profile.as_json()}


def render_command(profile: EnvProfile, command: list[str]) -> list[str]:
    if not command:
        raise ValueError("command is required")
    if command[0] in profile.forbidden_commands:
        raise ValueError(f"command is forbidden for profile {profile.profile_id}: {command[0]}")
    return ["uv", "run", "--project", profile.uv_project, "--locked", *command]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list-profiles")
    show = sub.add_parser("show-profile")
    show.add_argument("profile")
    check = sub.add_parser("check-profile")
    check.add_argument("profile")
    render = sub.add_parser("render-command")
    render.add_argument("profile")
    render.add_argument("profile_command", nargs=argparse.REMAINDER)
    validate = sub.add_parser("validate-finetune-config")
    validate.add_argument("config")
    sync = sub.add_parser("sync-profile")
    sync.add_argument("profile")
    sync.add_argument("--allow-sync", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        profiles = load_profiles()
        if args.command == "list-profiles":
            print(json.dumps(sorted(profiles), indent=2))
            return 0
        if args.command == "show-profile":
            print(json.dumps(profiles[args.profile].as_json(), indent=2, sort_keys=True))
            return 0
        if args.command == "check-profile":
            profiles[args.profile]
            print(json.dumps({"profile": args.profile, "status": "ok"}, sort_keys=True))
            return 0
        if args.command == "render-command":
            command = [item for item in args.profile_command if item != "--"]
            print(json.dumps(render_command(profiles[args.profile], command), indent=2))
            return 0
        if args.command == "validate-finetune-config":
            result = validate_finetune_config(Path(args.config), profiles)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        if args.command == "sync-profile":
            profile = profiles[args.profile]
            if not args.allow_sync:
                raise ValueError("sync-profile requires explicit --allow-sync")
            if profile.requires_manual_authorization:
                raise ValueError("profile requires separate manual authorization before sync")
            print(json.dumps({"profile": profile.profile_id, "sync": "manual command required"}))
            return 0
    except KeyError as exc:
        print(f"unknown profile: {exc.args[0]}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
