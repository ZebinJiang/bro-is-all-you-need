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
    load_local_runner_dry_run_config,
)
from autovla.training.execution_manifest import LOCAL_SMOKE_MODE
from autovla.training.run_manifest import write_dry_run_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造 dry-run CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.cli",
        description="AutoVLA deterministic local runner dry-run scaffold.",
    )
    parser.add_argument("--config", required=True, help="strict JSON dry-run config path")
    parser.add_argument("--dry-run", action="store_true", help="enable local dry-run mode")
    parser.add_argument(
        "--local-smoke",
        action="store_true",
        help="execute deterministic local-smoke without real training",
    )
    parser.add_argument("--output-dir", help="override config output_dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行 strict JSON dry-run CLI, 返回进程退出码。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    dry_run = bool(cast(bool, args.dry_run))
    local_smoke = bool(cast(bool, args.local_smoke))
    if dry_run == local_smoke:
        print("error: exactly one of --dry-run or --local-smoke is required", file=sys.stderr)
        return 2

    try:
        config = load_local_runner_dry_run_config(Path(cast(str, args.config)))
        output_dir = cast(str | None, args.output_dir)
        if output_dir is not None:
            config = config.with_output_dir(output_dir)
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
