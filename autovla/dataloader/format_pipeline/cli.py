"""AutoVLA 数据格式流水线 CLI。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Sequence

from autovla.dataloader.format_pipeline.contracts import FormatPipelineConfig, normalize_candidates
from autovla.dataloader.format_pipeline.pipeline import (
    benchmark_format_pipeline,
    build_format_pipeline,
    build_validate_benchmark_pipeline,
    validate_format_pipeline,
)


def main(argv: Sequence[str] | None = None) -> int:
    """运行数据格式流水线 CLI。"""
    parser = argparse.ArgumentParser(description="AutoVLA data-format pipeline suite")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("build", "validate", "benchmark", "build-validate-benchmark"):
        sub = subparsers.add_parser(name)
        _add_common_args(sub)
    args = parser.parse_args(argv)
    config = FormatPipelineConfig(
        batch_size=int(args.batch_size),
        candidates=normalize_candidates(args.candidate),
        materializer=str(args.materializer),
        max_episodes=int(args.max_episodes),
        max_samples=int(args.max_samples),
        measured_batches=int(args.measured_batches),
        output_dir=args.output_dir,
        samples_per_shard=int(args.samples_per_shard),
        seed=int(args.seed),
        source_dataset=args.source_dataset,
        warmup_batches=int(args.warmup_batches),
        worker_count=int(args.worker_count),
        working_root=args.working_root,
    )
    if args.command == "build":
        result = build_format_pipeline(config)
    elif args.command == "validate":
        result = validate_format_pipeline(config)
    elif args.command == "benchmark":
        result = benchmark_format_pipeline(config)
    else:
        result = build_validate_benchmark_pipeline(config)
    print(result.result_json.as_posix())
    return 0


def _add_common_args(parser: argparse.ArgumentParser) -> None:
    """添加共享命令行参数。"""
    parser.add_argument("--source-dataset", required=True, type=Path)
    parser.add_argument("--working-root", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--max-episodes", default=4, type=int)
    parser.add_argument("--max-samples", default=512, type=int)
    parser.add_argument("--samples-per-shard", default=128, type=int)
    parser.add_argument("--seed", default=11, type=int)
    parser.add_argument("--worker-count", default=8, type=int)
    parser.add_argument("--batch-size", default=1, type=int)
    parser.add_argument("--warmup-batches", default=1, type=int)
    parser.add_argument("--measured-batches", default=8, type=int)
    parser.add_argument("--materializer", choices=("ffmpeg", "synthetic"), default="ffmpeg")
    parser.add_argument(
        "--candidate",
        action="append",
        choices=(
            "raw_zjh_lerobot_v21_baseline",
            "webdataset_native",
            "robodm_style",
            "lerobot_v3",
        ),
    )
