"""AutoVLA 环境 CLI 薄入口,并保留旧只读 helper 导入。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

if __name__ == "__main__" and __package__ is None:
    # 直接脚本调用改用模块入口,避免修改 sys.path 或 site-packages。
    os.chdir(Path(__file__).resolve().parents[2])
    os.execv(sys.executable, [sys.executable, "-m", "scripts.env.autovla_env", *sys.argv[1:]])

from autovla.cli.env import main as runtime_main
from autovla.runtime_profiles.legacy import (
    FORBIDDEN_PROFILE_IDS,
    EnvProfile,
    load_profiles,
    render_command,
    validate_finetune_config,
)

_LEGACY_COMMANDS = {
    "list-profiles",
    "show-profile",
    "check-profile",
    "render-command",
    "validate-finetune-config",
    "sync-profile",
}


def _legacy_main(argv: list[str]) -> int:
    """保留 M8/M10 无副作用命令;同步仍默认关闭。"""

    parser = argparse.ArgumentParser(prog="autovla_env.py")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list-profiles")
    show = subparsers.add_parser("show-profile")
    show.add_argument("profile")
    check = subparsers.add_parser("check-profile")
    check.add_argument("profile")
    render = subparsers.add_parser("render-command")
    render.add_argument("profile")
    render.add_argument("profile_command", nargs=argparse.REMAINDER)
    validate = subparsers.add_parser("validate-finetune-config")
    validate.add_argument("config")
    sync = subparsers.add_parser("sync-profile")
    sync.add_argument("profile")
    sync.add_argument("--allow-sync", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        profiles = load_profiles()
        if arguments.command == "list-profiles":
            print(json.dumps(sorted(profiles), indent=2))
        elif arguments.command == "show-profile":
            print(json.dumps(profiles[arguments.profile].as_json(), indent=2, sort_keys=True))
        elif arguments.command == "check-profile":
            profiles[arguments.profile]
            print(json.dumps({"profile": arguments.profile, "status": "ok"}, sort_keys=True))
        elif arguments.command == "render-command":
            command = [item for item in arguments.profile_command if item != "--"]
            print(json.dumps(render_command(profiles[arguments.profile], command), indent=2))
        elif arguments.command == "validate-finetune-config":
            payload = validate_finetune_config(Path(arguments.config), profiles)
            print(json.dumps(payload, indent=2, sort_keys=True))
        elif arguments.command == "sync-profile":
            profile = profiles[arguments.profile]
            if not arguments.allow_sync:
                raise ValueError("sync-profile requires explicit --allow-sync")
            if profile.requires_manual_authorization:
                raise ValueError("profile requires separate manual authorization before sync")
            print(json.dumps({"profile": profile.profile_id, "sync": "manual command required"}))
        return 0
    except KeyError as exc:
        print(f"unknown profile: {exc.args[0]}", file=sys.stderr)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
    return 2


def main(argv: list[str] | None = None) -> int:
    """按命令名分派 M11 CLI 或旧只读兼容命令。"""

    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments and arguments[0] in _LEGACY_COMMANDS:
        return _legacy_main(arguments)
    return runtime_main(arguments)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FORBIDDEN_PROFILE_IDS",
    "EnvProfile",
    "load_profiles",
    "main",
    "render_command",
    "validate_finetune_config",
]
