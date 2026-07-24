"""模型资产离线检查与显式获取 CLI。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence, cast

from autovla.assets import (
    DEFAULT_MODEL_ASSET_REGISTRY,
    DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY,
    DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY,
    HuggingFaceModelAssetProvider,
    ModelAssetConfigurationError,
    ModelAssetError,
    ModelAssetStore,
)


def build_parser() -> argparse.ArgumentParser:
    """构造资产清单、族状态与显式资产操作子命令解析器。"""

    parser = argparse.ArgumentParser(prog="autovla-assets")
    parser.add_argument("--root", type=Path, help="显式绝对模型资产根")
    parser.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="列出已注册资产")
    subcommands.add_parser("bundles", help="列出三个活跃家族资产包注册")
    bundle = subcommands.add_parser("bundle", help="检查一个精确家族资产包注册")
    bundle.add_argument("family_key")
    families = subcommands.add_parser("families", help="列出模型族资产门状态")
    families.add_argument("--include-deferred", action="store_true")
    status = subcommands.add_parser("status", help="检查一个模型族的资产门状态")
    status.add_argument("key")
    for name in ("inspect", "verify", "path"):
        command = subcommands.add_parser(name)
        command.add_argument("key")
    fetch = subcommands.add_parser("fetch")
    fetch.add_argument("key")
    fetch.add_argument(
        "--revision",
        help="可选精确 revision;必须与 registry 固定 pin 完全一致",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行资产命令;只有 fetch 分支可能调用网络 provider。"""

    arguments = build_parser().parse_args(argv)
    try:
        store = ModelAssetStore(arguments.root)
        if arguments.command == "list":
            payload: object = [
                {
                    "key": spec.key,
                    "family_key": spec.family_key,
                    "provider": spec.provider,
                    "source_url": spec.source_url,
                    "public_identifier": spec.public_identifier,
                    "repository": spec.repository,
                    "revision": spec.revision,
                    "license": spec.license_name,
                }
                for spec in DEFAULT_MODEL_ASSET_REGISTRY.list()
            ]
        elif arguments.command == "bundles":
            payload = [
                registration.to_json_dict()
                for registration in DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY.list()
            ]
        elif arguments.command == "bundle":
            payload = DEFAULT_MODEL_FAMILY_ASSET_BUNDLE_REGISTRY.require(
                arguments.family_key
            ).to_json_dict()
        elif arguments.command == "families":
            payload = [
                {
                    "family_key": status.family_key,
                    "state": status.state.value,
                    "registered_asset_keys": status.registered_asset_keys,
                    "first_blocker": status.first_blocker,
                    "runtime_authorized": status.runtime_authorized,
                }
                for status in DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY.list(
                    include_deferred=arguments.include_deferred
                )
            ]
        elif arguments.command == "status":
            status = DEFAULT_MODEL_FAMILY_ASSET_STATUS_REGISTRY.require(arguments.key)
            payload = {
                "family_key": status.family_key,
                "state": status.state.value,
                "registered_asset_keys": status.registered_asset_keys,
                "first_blocker": status.first_blocker,
                "runtime_authorized": status.runtime_authorized,
            }
        else:
            spec = DEFAULT_MODEL_ASSET_REGISTRY.require(arguments.key)
            if arguments.command == "inspect":
                payload = {
                    "key": spec.key,
                    "family_key": spec.family_key,
                    "provider": spec.provider,
                    "source_url": spec.source_url,
                    "public_identifier": spec.public_identifier,
                    "repository": spec.repository,
                    "revision": spec.revision,
                    "license": spec.license_name,
                    "license_file_path": spec.license_file_path,
                    "use_limitation": spec.use_limitation,
                    "redistribution": spec.redistribution,
                    "checksum_policy": spec.checksum_policy,
                    "asset_roles": spec.asset_roles,
                    "remote_code_required": spec.remote_code_required,
                    "files": [
                        {
                            "path": item.path,
                            "size": item.size,
                            "sha256": item.sha256,
                            "role": item.role,
                        }
                        for item in spec.files
                    ],
                    "path": str(store.asset_path(spec)),
                }
            elif arguments.command == "fetch":
                requested_revision = arguments.revision
                if requested_revision is not None and requested_revision != spec.revision:
                    raise ModelAssetConfigurationError(
                        "fetch revision must exactly match the immutable registry pin"
                    )
                provider = HuggingFaceModelAssetProvider(store.provider_cache_root("huggingface"))
                resolved = store.fetch(spec, provider)
                payload = _resolved_payload(resolved)
            elif arguments.command == "verify":
                payload = _resolved_payload(store.verify(spec))
            elif arguments.command == "path":
                payload = {"key": spec.key, "path": str(store.verify(spec).root)}
            else:  # pragma: no cover - argparse 已封闭命令集合
                raise AssertionError(f"unreachable command: {arguments.command}")
    except ModelAssetError as exc:
        message = str(exc)
        if arguments.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
        else:
            print(f"ERROR: {message}")
        return 2
    except (OSError, TypeError, ValueError):
        message = "asset command failed without publishing a final asset"
        if arguments.json:
            print(json.dumps({"ok": False, "error": message}, ensure_ascii=False))
        else:
            print(f"ERROR: {message}")
        return 2
    if arguments.json:
        print(json.dumps({"ok": True, "result": payload}, ensure_ascii=False, sort_keys=True))
    else:
        _print_human(payload)
    return 0


def _resolved_payload(resolved: object) -> dict[str, object]:
    """把已验证资产结果转换为稳定 CLI 载荷。"""

    from autovla.assets import ResolvedModelAsset

    if not isinstance(resolved, ResolvedModelAsset):
        raise TypeError("resolved asset has an invalid type")
    return {
        "key": resolved.manifest.key,
        "path": str(resolved.root),
        "identity": resolved.identity,
        "revision": resolved.manifest.revision,
        "license": resolved.manifest.license_name,
        "verification_state": resolved.manifest.verification_state,
        "acquired_at_utc": resolved.manifest.acquired_at_utc,
        "provider_version": resolved.manifest.provider_version,
        "downloader_version": resolved.manifest.downloader_version,
    }


def _print_human(payload: object) -> None:
    """用紧凑 JSON 展示嵌套字段,避免人类输出丢失许可信息。"""

    if isinstance(payload, list):
        for item in cast(list[object], payload):
            if isinstance(item, dict):
                record = cast(dict[str, object], item)
                if "key" in record:
                    print(
                        f"{record['key']}\t{record['provider']}\t"
                        f"{record['revision']}\t{record['license']}"
                    )
                elif "state" in record:
                    print(
                        f"{record['family_key']}\t{record['state']}\t" f"{record['first_blocker']}"
                    )
                else:
                    print(
                        f"{record['family_key']}\t{record['lifecycle_state']}\t"
                        f"{','.join(cast(list[str], record['blockers']))}"
                    )
        return
    if isinstance(payload, dict):
        for key, value in cast(dict[object, object], payload).items():
            rendered = json.dumps(value, ensure_ascii=False, sort_keys=True)
            print(f"{key}: {rendered}")


if __name__ == "__main__":
    raise SystemExit(main())
