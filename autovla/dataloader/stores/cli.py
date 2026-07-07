"""多格式 datastore bakeoff 命令行入口。"""

from __future__ import annotations

import argparse
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import cast

import yaml

from autovla.dataloader.stores.benchmark import run_multiformat_datastore_bakeoff
from autovla.dataloader.stores.common import MultiformatDatastoreConfig


def main(argv: Sequence[str] | None = None) -> int:
    """解析 CLI 参数并执行 bounded bakeoff。"""
    parser = argparse.ArgumentParser(prog="python -m autovla.dataloader.stores")
    subparsers = parser.add_subparsers(dest="command", required=True)
    run_parser = subparsers.add_parser("run", help="执行多格式 datastore bakeoff")
    run_parser.add_argument("--config", type=Path, required=True, help="YAML 配置路径")
    args = parser.parse_args(list(argv) if argv is not None else None)
    if args.command == "run":
        config = load_datastore_config(args.config)
        run_multiformat_datastore_bakeoff(config)
        return 0
    raise ValueError(f"unsupported command: {args.command}")


def load_datastore_config(path: Path) -> MultiformatDatastoreConfig:
    """从 YAML 读取 datastore bakeoff 配置。"""
    payload = _require_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))
    return MultiformatDatastoreConfig(
        source_dataset=Path(_require_str(payload.get("source_dataset"), "source_dataset")),
        working_root=Path(_require_str(payload.get("working_root"), "working_root")),
        output_dir=Path(_require_str(payload.get("output_dir"), "output_dir")),
        readonly_root=_optional_path(payload.get("readonly_root")),
        max_episodes=_require_int(payload.get("max_episodes", 4), "max_episodes"),
        max_samples=_require_int(payload.get("max_samples", 512), "max_samples"),
        seed=_require_int(payload.get("seed", 11), "seed"),
        window_size=_require_int(payload.get("window_size", 1), "window_size"),
        action_horizon=_require_int(payload.get("action_horizon", 1), "action_horizon"),
        batch_size=_require_int(payload.get("batch_size", 1), "batch_size"),
        measured_batches=_require_int(payload.get("measured_batches", 4), "measured_batches"),
        samples_per_shard=_require_int(payload.get("samples_per_shard", 128), "samples_per_shard"),
    )


def _optional_path(value: object) -> Path | None:
    """读取可选路径。"""
    if value in (None, ""):
        return None
    return Path(_require_str(value, "readonly_root"))


def _require_mapping(value: object) -> Mapping[str, object]:
    """把 YAML 根对象收窄为 mapping。"""
    if not isinstance(value, Mapping):
        raise ValueError("config root must be a mapping")
    return cast(Mapping[str, object], value)


def _require_str(value: object, field_name: str) -> str:
    """读取非空字符串字段。"""
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _require_int(value: object, field_name: str) -> int:
    """读取整数配置字段。"""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
