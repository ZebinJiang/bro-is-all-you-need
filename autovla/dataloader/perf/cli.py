"""DataLoader 性能 Harness CLI。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, cast

from autovla.dataloader.perf.benchmark import run_benchmark
from autovla.dataloader.perf.config import (
    BenchmarkMode,
    PerfBenchmarkConfig,
    load_perf_benchmark_config,
)


def _parser() -> argparse.ArgumentParser:
    """构造 CLI parser。"""
    parser = argparse.ArgumentParser(prog="python -m autovla.dataloader.perf")
    subparsers = parser.add_subparsers(dest="command", required=True)
    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--config")
    benchmark.add_argument("--adapter")
    benchmark.add_argument("--dataset")
    benchmark.add_argument("--output-dir")
    benchmark.add_argument(
        "--mode",
        choices=("metadata-only", "bounded-decode", "training-view"),
        default="metadata-only",
    )
    benchmark.add_argument("--max-episodes", type=int, default=4)
    benchmark.add_argument("--max-samples", type=int, default=512)
    benchmark.add_argument("--max-decode-seconds", type=int, default=300)
    return parser


def _config_from_args(args: argparse.Namespace) -> PerfBenchmarkConfig:
    """从 CLI 参数构造配置。"""
    if args.config:
        return load_perf_benchmark_config(Path(str(args.config)))
    if not args.adapter or not args.dataset or not args.output_dir:
        raise ValueError("--adapter, --dataset, and --output-dir are required without --config")
    return PerfBenchmarkConfig(
        adapter=str(args.adapter),
        dataset=Path(str(args.dataset)),
        output_dir=Path(str(args.output_dir)),
        max_decode_seconds=int(args.max_decode_seconds),
        max_episodes=int(args.max_episodes),
        max_samples=int(args.max_samples),
        mode=cast(BenchmarkMode, str(args.mode)),
    )


def main(argv: Sequence[str] | None = None) -> int:
    """运行 CLI 并返回进程退出码。"""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command != "benchmark":
            raise ValueError(f"unsupported command: {args.command}")
        config = _config_from_args(args)
        result = run_benchmark(config)
    except Exception as exc:
        print(f"config/benchmark error: {exc}", file=sys.stderr)
        return 2
    print((result.output_dir / "perf_report.json").as_posix())
    print(f"classification={result.classification.classification}")
    return 0
