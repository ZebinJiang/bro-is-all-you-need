"""M3 本地 runner dry-run CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import cast

from genesisvla.training.config import (
    LocalRunnerConfigError,
    load_local_runner_dry_run_config,
)
from genesisvla.training.run_manifest import write_dry_run_manifest


def build_parser() -> argparse.ArgumentParser:
    """构造 dry-run CLI 参数解析器。"""
    parser = argparse.ArgumentParser(
        prog="python -m genesisvla.training.cli",
        description="GenesisVLA deterministic local runner dry-run scaffold.",
    )
    parser.add_argument("--config", required=True, help="strict JSON dry-run config path")
    parser.add_argument("--dry-run", action="store_true", help="enable local dry-run mode")
    parser.add_argument("--output-dir", help="override config output_dir")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """执行 strict JSON dry-run CLI, 返回进程退出码。"""
    parser = build_parser()
    args = parser.parse_args(argv)
    dry_run = bool(cast(bool, args.dry_run))
    if not dry_run:
        print("error: --dry-run is required", file=sys.stderr)
        return 2

    try:
        config = load_local_runner_dry_run_config(Path(cast(str, args.config)))
        output_dir = cast(str | None, args.output_dir)
        if output_dir is not None:
            config = config.with_output_dir(output_dir)
        manifest_path = write_dry_run_manifest(config)
    except (LocalRunnerConfigError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2

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


if __name__ == "__main__":
    raise SystemExit(main())
