"""DataLoader 性能 Harness CLI。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Sequence, cast

from autovla.dataloader.perf.bakeoff import DataBackendBakeoffConfig, run_backend_bakeoff
from autovla.dataloader.perf.benchmark import run_benchmark
from autovla.dataloader.perf.config import (
    BenchmarkMode,
    BuildScope,
    PerfBenchmarkConfig,
    load_perf_benchmark_config,
)
from autovla.dataloader.perf.synthetic import (
    SyntheticDataloaderBenchmarkConfig,
    parse_table_formats,
    run_synthetic_dataloader_benchmark,
)


def _parser() -> argparse.ArgumentParser:
    """构造 CLI parser。"""
    parser = argparse.ArgumentParser(prog="python -m autovla.dataloader.perf")
    subparsers = parser.add_subparsers(dest="command", required=True)
    benchmark = subparsers.add_parser("benchmark")
    benchmark.add_argument("--backend", choices=("adapter", "synthetic"), default="adapter")
    benchmark.add_argument("--fixture", default="tiny")
    benchmark.add_argument("--config")
    benchmark.add_argument("--adapter")
    benchmark.add_argument("--dataset")
    benchmark.add_argument("--output-dir")
    benchmark.add_argument("--batch-size", type=int, default=4)
    benchmark.add_argument("--table-format", default="json,csv,md")
    benchmark.add_argument(
        "--mode",
        choices=(
            "bounded-decode",
            "metadata-only",
            "pfs-training-store-build",
            "pfs-training-store-build-webdataset",
            "pfs-training-store-read",
            "pfs-training-store-read-webdataset",
            "store-build-bounded",
            "store-plan",
            "store-read-benchmark",
            "training-view",
        ),
        default="metadata-only",
    )
    benchmark.add_argument("--max-episodes", type=int, default=4)
    benchmark.add_argument("--max-samples", type=int, default=512)
    benchmark.add_argument("--max-decode-seconds", type=int, default=300)
    benchmark.add_argument("--training-store-dir")
    benchmark.add_argument(
        "--build-scope",
        choices=("bounded", "budgeted_partial", "full", "full-or-budgeted"),
        default="bounded",
    )
    bakeoff = subparsers.add_parser("bakeoff")
    bakeoff.add_argument("--backend", required=True)
    bakeoff.add_argument("--input-root", required=True)
    bakeoff.add_argument("--output-dir", required=True)
    bakeoff.add_argument("--max-samples", type=int, default=64)
    bakeoff.add_argument("--max-files", type=int, default=256)
    bakeoff.add_argument("--max-bytes-read", type=int, default=1048576)
    bakeoff.add_argument("--table-format", default="json,csv,md")
    bakeoff.add_argument("--allow-missing-input-root", action="store_true")
    bakeoff.add_argument("--read-media", action="store_true")
    bakeoff.add_argument("--decode-media", action="store_true")
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
        training_store_dir=(
            Path(str(args.training_store_dir)) if args.training_store_dir is not None else None
        ),
        build_scope=cast(BuildScope, str(args.build_scope)),
    )


def _run_synthetic_from_args(args: argparse.Namespace) -> Path:
    """运行 synthetic backend 并返回 JSON 表路径。"""
    if args.config:
        raise ValueError("--config is not supported for synthetic backend")
    if not args.output_dir:
        raise ValueError("--output-dir is required for synthetic backend")
    result = run_synthetic_dataloader_benchmark(
        SyntheticDataloaderBenchmarkConfig(
            fixture=str(args.fixture),
            max_samples=int(args.max_samples),
            batch_size=int(args.batch_size),
            output_dir=Path(str(args.output_dir)),
            table_formats=parse_table_formats(str(args.table_format)),
        )
    )
    return result.files.get("json", next(iter(result.files.values())))


def _run_bakeoff_from_args(args: argparse.Namespace) -> Path:
    """运行 DataBackend bakeoff 并返回 raw JSON 路径。"""
    result = run_backend_bakeoff(
        DataBackendBakeoffConfig(
            backends=tuple(item.strip() for item in str(args.backend).split(",") if item.strip()),
            input_root=Path(str(args.input_root)),
            max_samples=int(args.max_samples),
            max_files=int(args.max_files),
            max_bytes_read=int(args.max_bytes_read),
            output_dir=Path(str(args.output_dir)),
            table_format=parse_table_formats(str(args.table_format)),
            allow_missing_input_root=bool(args.allow_missing_input_root),
            read_media=bool(args.read_media),
            decode_media=bool(args.decode_media),
        )
    )
    return result.output_dir / "backend_bakeoff_raw.json"


def main(argv: Sequence[str] | None = None) -> int:
    """运行 CLI 并返回进程退出码。"""
    parser = _parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "bakeoff":
            output_path = _run_bakeoff_from_args(args)
            print(output_path.as_posix())
            print("classification=METADATA_ONLY_BAKEOFF")
            return 0
        if args.command != "benchmark":
            raise ValueError(f"unsupported command: {args.command}")
        if args.backend == "synthetic":
            output_path = _run_synthetic_from_args(args)
            print(output_path.as_posix())
            print("classification=SYNTHETIC_ONLY")
            return 0
        config = _config_from_args(args)
        result = run_benchmark(config)
    except Exception as exc:
        print(f"config/benchmark error: {exc}", file=sys.stderr)
        return 2
    print((result.output_dir / "perf_report.json").as_posix())
    print(f"classification={result.classification.classification}")
    return 0
