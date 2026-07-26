"""AutoVLA 隔离运行时画像命令行入口。"""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from autovla.runtime_profiles import (
    CudaCompatibilityIntent,
    ResolvedRuntimeLock,
    RuntimeEnvironmentError,
    RuntimeEnvironmentManager,
    RuntimeEnvironmentReceipt,
)


def _load_json_object(
    path: Path,
    *,
    label: str,
    repository_root: Path,
) -> dict[str, object]:
    """从 checkout 内显式规范路径读取严格 JSON 对象。"""

    expanded = path.expanduser()
    if (
        expanded.is_absolute()
        or expanded.as_posix() != path.as_posix()
        or any(part in {"", ".", ".."} for part in expanded.parts)
    ):
        raise RuntimeEnvironmentError(
            "RUNTIME_RECEIPT_PATH_INVALID",
            f"{label} must be a canonical checkout-relative path",
        )
    absolute = repository_root / expanded
    current = repository_root
    for part in expanded.parts:
        current = current / part
        if current.is_symlink():
            raise RuntimeEnvironmentError(
                "RUNTIME_RECEIPT_PATH_INVALID",
                f"{label} path must not traverse symbolic links",
            )
    if not absolute.is_file():
        raise RuntimeEnvironmentError(
            "RUNTIME_RECEIPT_PATH_INVALID", f"{label} must be a readable non-symlink file"
        )
    try:
        payload = cast(object, json.loads(absolute.read_text(encoding="utf-8")))
    except (OSError, json.JSONDecodeError, TypeError) as exc:
        raise RuntimeEnvironmentError(
            "RUNTIME_RECEIPT_INVALID", f"{label} is not valid JSON"
        ) from exc
    if not isinstance(payload, dict):
        raise RuntimeEnvironmentError(
            "RUNTIME_RECEIPT_INVALID", f"{label} must contain one JSON object"
        )
    raw_payload = cast("dict[object, object]", payload)
    if not all(isinstance(key, str) for key in raw_payload):
        raise RuntimeEnvironmentError(
            "RUNTIME_RECEIPT_INVALID", f"{label} must contain one JSON object"
        )
    return cast("dict[str, object]", raw_payload)


def _profile_command(values: Sequence[str]) -> tuple[str, ...]:
    """只消费 argparse 命令前的第一个分隔符并保留其余参数。"""

    command = tuple(values)
    if command and command[0] == "--":
        return command[1:]
    return command


def build_parser() -> argparse.ArgumentParser:
    """构造 list/inspect/resolve/cache/create/verify/exec 封闭命令集。"""

    parser = argparse.ArgumentParser(prog="autovla-env")
    parser.add_argument(
        "--checkout-root",
        type=Path,
        help="显式 checkout 根; resolve/cache/create/verify/exec 必需",
    )
    parser.add_argument(
        "--workspace-root",
        type=Path,
        help="显式 workspace 物理根; cache/create/verify/exec 必需",
    )
    subparsers = parser.add_subparsers(dest="action", required=True)
    subparsers.add_parser("list", help="列举四个静态画像")
    inspect_parser = subparsers.add_parser("inspect", help="检查描述和 lock 身份")
    inspect_parser.add_argument("profile")
    resolve_parser = subparsers.add_parser("resolve", help="解析提交内 uv.lock")
    resolve_parser.add_argument("profile")
    resolve_parser.add_argument("--cuda-intent-receipt", type=Path, required=True)
    cache_parser = subparsers.add_parser("cache", help="显式联网填充 workspace UV cache")
    cache_parser.add_argument("profile")
    cache_parser.add_argument("--lock-receipt", type=Path, required=True)
    cache_parser.add_argument("--allow-network", action="store_true")
    create_parser = subparsers.add_parser("create", help="从显式精确 lock 离线创建环境")
    create_parser.add_argument("profile")
    create_parser.add_argument("--lock-receipt", type=Path, required=True)
    create_parser.add_argument("--nonce", required=True)
    create_parser.add_argument("--allow-create", action="store_true")
    verify_parser = subparsers.add_parser("verify", help="只验证现有环境")
    verify_parser.add_argument("profile")
    verify_parser.add_argument("--lock-receipt", type=Path, required=True)
    exec_parser = subparsers.add_parser("exec", help="只在验证通过后执行命令")
    exec_parser.add_argument("profile")
    exec_parser.add_argument("--lock-receipt", type=Path, required=True)
    exec_parser.add_argument("--environment-receipt", type=Path, required=True)
    exec_parser.add_argument("--asset-fingerprint", required=True)
    exec_parser.add_argument("--topology-fingerprint", required=True)
    exec_parser.add_argument("--evidence-path", required=True)
    exec_parser.add_argument("--operation", required=True)
    exec_parser.add_argument("profile_command", nargs=argparse.REMAINDER)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行环境命令并以稳定 JSON/退出码返回。"""

    arguments = build_parser().parse_args(argv)
    try:
        manager = RuntimeEnvironmentManager(
            arguments.checkout_root,
            workspace_root=arguments.workspace_root,
        )
        if arguments.action == "list":
            payload: object = [profile.to_dict() for profile in manager.list_profiles()]
            return_code = 0
        elif arguments.action == "inspect":
            payload = manager.inspect(arguments.profile)
            return_code = 0
        elif arguments.action == "resolve":
            if manager.repository_root is None:
                raise RuntimeEnvironmentError(
                    "CHECKOUT_ROOT_REQUIRED", "resolve requires an explicit checkout root"
                )
            cuda_compatibility = CudaCompatibilityIntent.from_dict(
                _load_json_object(
                    arguments.cuda_intent_receipt,
                    label="CUDA intent receipt",
                    repository_root=manager.repository_root,
                )
            )
            payload = manager.resolve(arguments.profile, cuda_compatibility).to_dict()
            return_code = 0
        elif arguments.action == "cache":
            if manager.repository_root is None:
                raise RuntimeEnvironmentError(
                    "CHECKOUT_ROOT_REQUIRED", "cache requires an explicit checkout root"
                )
            if arguments.workspace_root is None:
                raise RuntimeEnvironmentError(
                    "WORKSPACE_ROOT_REQUIRED", "cache requires an explicit workspace root"
                )
            lock = ResolvedRuntimeLock.from_dict(
                _load_json_object(
                    arguments.lock_receipt,
                    label="lock receipt",
                    repository_root=manager.repository_root,
                )
            )
            payload = manager.cache(
                arguments.profile,
                lock,
                allow_network=arguments.allow_network,
            )
            return_code = 0
        elif arguments.action == "create":
            if manager.repository_root is None:
                raise RuntimeEnvironmentError(
                    "CHECKOUT_ROOT_REQUIRED", "create requires an explicit checkout root"
                )
            if arguments.workspace_root is None:
                raise RuntimeEnvironmentError(
                    "WORKSPACE_ROOT_REQUIRED", "create requires an explicit workspace root"
                )
            lock = ResolvedRuntimeLock.from_dict(
                _load_json_object(
                    arguments.lock_receipt,
                    label="lock receipt",
                    repository_root=manager.repository_root,
                )
            )
            receipt = manager.create(
                arguments.profile,
                lock,
                nonce=arguments.nonce,
                allow_create=arguments.allow_create,
            )
            payload = receipt.to_dict()
            return_code = 0
        elif arguments.action == "verify":
            if manager.repository_root is None:
                raise RuntimeEnvironmentError(
                    "CHECKOUT_ROOT_REQUIRED", "verify requires an explicit checkout root"
                )
            if arguments.workspace_root is None:
                raise RuntimeEnvironmentError(
                    "WORKSPACE_ROOT_REQUIRED", "verify requires an explicit workspace root"
                )
            lock = ResolvedRuntimeLock.from_dict(
                _load_json_object(
                    arguments.lock_receipt,
                    label="lock receipt",
                    repository_root=manager.repository_root,
                )
            )
            receipt = manager.verify(arguments.profile, lock)
            payload = receipt.to_dict()
            return_code = 0
        elif arguments.action == "exec":
            if manager.repository_root is None:
                raise RuntimeEnvironmentError(
                    "CHECKOUT_ROOT_REQUIRED", "exec requires an explicit checkout root"
                )
            if arguments.workspace_root is None:
                raise RuntimeEnvironmentError(
                    "WORKSPACE_ROOT_REQUIRED", "exec requires an explicit workspace root"
                )
            lock = ResolvedRuntimeLock.from_dict(
                _load_json_object(
                    arguments.lock_receipt,
                    label="lock receipt",
                    repository_root=manager.repository_root,
                )
            )
            environment = RuntimeEnvironmentReceipt.from_dict(
                _load_json_object(
                    arguments.environment_receipt,
                    label="environment receipt",
                    repository_root=manager.repository_root,
                )
            )
            command = _profile_command(arguments.profile_command)
            execution = manager.exec(
                arguments.profile,
                lock,
                environment,
                command,
                asset_fingerprint=arguments.asset_fingerprint,
                topology_fingerprint=arguments.topology_fingerprint,
                evidence_path=arguments.evidence_path,
                operation=arguments.operation,
            )
            payload = execution.to_dict()
            return_code = 0 if execution.status == "pass" else 2
        else:  # pragma: no cover - argparse 已封闭命令集合
            raise AssertionError(arguments.action)
    except RuntimeEnvironmentError as exc:
        print(json.dumps({"ok": False, "error": {"code": exc.code, "message": exc.message}}))
        return 2
    print(json.dumps({"ok": True, "result": payload}, ensure_ascii=False, indent=2, sort_keys=True))
    return return_code


if __name__ == "__main__":
    raise SystemExit(main())
