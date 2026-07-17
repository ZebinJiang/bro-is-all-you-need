"""AutoVLA 隔离运行时画像命令行入口。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from autovla.runtime_profiles import RuntimeEnvironmentError, RuntimeEnvironmentManager

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def build_parser() -> argparse.ArgumentParser:
    """构造 list/inspect/create/verify/exec 封闭命令集。"""

    parser = argparse.ArgumentParser(prog="autovla-env")
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="列举四个静态画像")
    inspect_parser = subparsers.add_parser("inspect", help="检查描述和 lock 身份")
    inspect_parser.add_argument("profile")
    create_parser = subparsers.add_parser("create", help="显式离线创建锁定环境")
    create_parser.add_argument("profile")
    create_parser.add_argument("--allow-create", action="store_true")
    verify_parser = subparsers.add_parser("verify", help="只验证现有环境")
    verify_parser.add_argument("profile")
    exec_parser = subparsers.add_parser("exec", help="只在验证通过后执行命令")
    exec_parser.add_argument("profile")
    exec_parser.add_argument("profile_command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行环境命令并以稳定 JSON/退出码返回。"""

    arguments = build_parser().parse_args(argv)
    manager = RuntimeEnvironmentManager(REPOSITORY_ROOT)
    try:
        if arguments.action == "list":
            payload: object = [profile.to_dict() for profile in manager.list_profiles()]
            return_code = 0
        elif arguments.action == "inspect":
            payload = manager.inspect(arguments.profile)
            return_code = 0
        elif arguments.action == "create":
            payload = manager.create(arguments.profile, allow_create=arguments.allow_create)
            return_code = 0
        elif arguments.action == "verify":
            report = manager.verify(arguments.profile)
            payload = report.to_dict()
            return_code = 0 if report.is_compatible else 2
        elif arguments.action == "exec":
            command = tuple(item for item in arguments.profile_command if item != "--")
            return manager.exec(arguments.profile, command)
        else:  # pragma: no cover - argparse 已封闭命令集合
            raise AssertionError(arguments.action)
    except RuntimeEnvironmentError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message}}))
        return 2
    print(json.dumps({"ok": True, "result": payload}, ensure_ascii=False, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
