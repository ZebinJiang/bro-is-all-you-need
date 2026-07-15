"""GPU200 训练桥接与遥测 CLI。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from autovla.training.telemetry.bridge_manifest import write_base_model_manifest
from autovla.training.telemetry.bridge_runtime import run_bridge
from autovla.training.telemetry.config import load_telemetry_config
from autovla.training.telemetry.reporting import build_step_sample, write_telemetry_outputs
from autovla.training.telemetry.samplers import CpuIoSampler, NvidiaSmiSampler
from autovla.training.telemetry.slurm import render_slurm_wrapper


def _build_parser() -> argparse.ArgumentParser:
    """构造训练桥接 CLI。"""
    parser = argparse.ArgumentParser(
        prog="python -m autovla.training.telemetry",
        description="AutoVLA bounded GR00T GPU200 telemetry and bridge surface.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser(
        "validate-config",
        help="validate bridge-ready telemetry config",
    )
    validate.add_argument("--config", required=True)

    render = subparsers.add_parser(
        "render-slurm",
        help="render compute-ready bridge sbatch wrapper",
    )
    render.add_argument("--config", required=True)
    render.add_argument("--output-dir", required=True)

    manifest = subparsers.add_parser(
        "write-base-model-manifest",
        help="write the AutoVLA-owned local base-model provenance manifest",
    )
    manifest.add_argument("--config", required=True)

    bridge = subparsers.add_parser(
        "bridge-run",
        help="launch the real bounded Isaac bridge on a compute allocation",
    )
    bridge.add_argument("--config", required=True)

    run = subparsers.add_parser("run-governed", help="emit bounded metadata-only telemetry files")
    run.add_argument("--config", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """执行训练桥接/遥测子命令。"""
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_telemetry_config(Path(args.config))
        if args.command == "validate-config":
            print(json.dumps(config.to_json_dict(), sort_keys=True))
            return 0
        if args.command == "render-slurm":
            result = render_slurm_wrapper(config, Path(args.output_dir))
            print(
                json.dumps(
                    {"plan_path": str(result.plan_path), "script_path": str(result.script_path)},
                    sort_keys=True,
                )
            )
            return 0
        if args.command == "write-base-model-manifest":
            manifest_path = write_base_model_manifest(config)
            print(json.dumps({"manifest_path": str(manifest_path)}, sort_keys=True))
            return 0
        if args.command == "bridge-run":
            return run_bridge(config)

        cpu_sampler = CpuIoSampler()
        gpu_sampler = NvidiaSmiSampler()
        step_samples = tuple(
            build_step_sample(
                step=step,
                gpu_snapshot=gpu_sampler.sample(),
                cpu_io_snapshot=cpu_sampler.sample(),
            )
            for step in range(1, config.max_steps + 1, config.sampling_interval_steps)
        )
        files = write_telemetry_outputs(config, step_samples)
        print(json.dumps({name: str(path) for name, path in files.items()}, sort_keys=True))
        return 0
    except (OSError, RuntimeError, TypeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
