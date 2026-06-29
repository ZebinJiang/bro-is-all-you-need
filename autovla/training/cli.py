"""M3 本地 runner dry-run CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from autovla.training.cli_execution import run_local_smoke
from autovla.training.config import (
    LocalRunnerConfigError,
    LocalRunnerDryRunConfig,
    load_local_runner_dry_run_config,
)
from autovla.training.execution_manifest import LOCAL_SMOKE_MODE
from autovla.training.microloop import MICROLOOP_MODE, run_microloop
from autovla.training.readiness import READINESS_MODE, run_readiness
from autovla.training.run_manifest import write_dry_run_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造 legacy flag CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.cli",
        description="AutoVLA deterministic local runner CLI.",
        epilog="commands: readiness, microloop",
    )
    parser.add_argument("--config", required=True, help="strict JSON dry-run config path")
    parser.add_argument("--dry-run", action="store_true", help="enable local dry-run mode")
    parser.add_argument(
        "--local-smoke",
        action="store_true",
        help="execute deterministic local-only smoke",
    )
    parser.add_argument("--output-dir", help="override config output_dir")
    return parser


def build_readiness_parser() -> argparse.ArgumentParser:
    """构造 readiness 子命令参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.cli readiness",
        description="AutoVLA deterministic runner readiness smoke.",
    )
    parser.add_argument("--config", required=True, help="strict JSON readiness config path")
    parser.add_argument("--output-dir", help="override config output_dir")
    return parser


def build_microloop_parser() -> argparse.ArgumentParser:
    """构造 microloop 子命令参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.cli microloop",
        description="AutoVLA deterministic CPU compute microloop.",
    )
    parser.add_argument("--config", required=True, help="strict JSON microloop config path")
    parser.add_argument("--output-dir", help="override config output_dir")
    parser.add_argument("--resume-from", help="checkpoint manifest to validate before running")
    parser.add_argument(
        "--require-compute-node",
        action="store_true",
        help="fail unless compute-node validation environment is present",
    )
    return parser


def _load_config(config_path: str, output_dir: str | None) -> LocalRunnerDryRunConfig:
    """加载配置并应用可选 output_dir 覆盖。"""
    config = load_local_runner_dry_run_config(Path(config_path))
    if output_dir is not None:
        config = config.with_output_dir(output_dir)
    return config


def _readiness_main(argv: Sequence[str]) -> int:
    """执行 readiness 子命令。"""
    parser = build_readiness_parser()
    args = parser.parse_args(argv)
    try:
        config = _load_config(cast(str, args.config), cast(str | None, args.output_dir))
        result = run_readiness(config)
    except (LocalRunnerConfigError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "checkpoint_manifest_path": str(result.checkpoint_manifest_path),
                "execution_manifest_path": str(result.execution_manifest_path),
                "mode": READINESS_MODE,
                "readiness": True,
                "readiness_manifest_path": str(result.readiness_manifest_path),
                "resumed_step": result.resumed_step,
            },
            sort_keys=True,
        )
    )
    return 0


def _microloop_main(argv: Sequence[str]) -> int:
    """执行 microloop 子命令。"""
    parser = build_microloop_parser()
    args = parser.parse_args(argv)
    try:
        config = _load_config(cast(str, args.config), cast(str | None, args.output_dir))
        raw_resume_from = cast(str | None, args.resume_from)
        resume_from = Path(raw_resume_from) if raw_resume_from is not None else None
        result = run_microloop(
            config,
            resume_from=resume_from,
            require_compute_node=bool(cast(bool, args.require_compute_node)),
        )
    except (LocalRunnerConfigError, OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "checkpoint_manifest_path": str(result.checkpoint_manifest_path),
                "microloop": True,
                "microloop_manifest_path": str(result.microloop_manifest_path),
                "mode": MICROLOOP_MODE,
                "resumed_step": result.resumed_step,
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    """执行 strict JSON dry-run CLI, 返回进程退出码。"""
    actual_argv = list(sys.argv[1:] if argv is None else argv)
    if actual_argv and actual_argv[0] == READINESS_MODE:
        return _readiness_main(actual_argv[1:])
    if actual_argv and actual_argv[0] == MICROLOOP_MODE:
        return _microloop_main(actual_argv[1:])

    parser = build_parser()
    args = parser.parse_args(actual_argv)
    dry_run = bool(cast(bool, args.dry_run))
    local_smoke = bool(cast(bool, args.local_smoke))
    if dry_run == local_smoke:
        print("error: exactly one of --dry-run or --local-smoke is required", file=sys.stderr)
        return 2

    try:
        config = _load_config(cast(str, args.config), cast(str | None, args.output_dir))
        if dry_run:
            manifest_path = write_dry_run_manifest(config)
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "manifest_path": str(manifest_path),
                        "mode": config.mode,
                    },
                    sort_keys=True,
                )
            )
            return 0
        result = run_local_smoke(config)
    except (LocalRunnerConfigError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

    print(
        json.dumps(
            {
                "checkpoint_manifest_path": str(result.checkpoint_manifest_path),
                "execution_manifest_path": str(result.execution_manifest_path),
                "local_smoke": True,
                "mode": LOCAL_SMOKE_MODE,
                "resumed_step": result.resumed_step,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
