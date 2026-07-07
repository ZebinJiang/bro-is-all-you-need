"""GPU200 训练桥接 Slurm 渲染 surface。"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from autovla.training.metrics import stable_json_dumps
from autovla.training.telemetry.bridge_runtime import build_bridge_plan_payload
from autovla.training.telemetry.config import TelemetryConfig


@dataclass(frozen=True, slots=True)
class SlurmRenderResult:
    """渲染后的 Slurm 产物索引。"""

    script_path: Path
    plan_path: Path


def _render_sbatch_script(config: TelemetryConfig) -> str:
    """构造 bridge-ready sbatch 脚本文本。"""
    lines = [
        "#!/usr/bin/env bash",
        f"#SBATCH --job-name={config.run_id}",
        f"#SBATCH --partition={config.slurm_partition}",
        f"#SBATCH --cpus-per-task={config.cpus_per_task}",
        f"#SBATCH --mem={config.memory}",
        f"#SBATCH --time={config.time_limit}",
        f"#SBATCH --gres={config.gres}",
        "set -euo pipefail",
        "export WANDB_MODE=offline",
        "export HF_HUB_OFFLINE=1",
        "export TRANSFORMERS_OFFLINE=1",
        "export HF_DATASETS_OFFLINE=1",
        f'{config.python_executable} -m autovla.training.telemetry bridge-run --config "$1"',
    ]
    if config.slurm_account:
        lines.insert(4, f"#SBATCH --account={config.slurm_account}")
    return "\n".join(lines) + "\n"


def render_slurm_wrapper(config: TelemetryConfig, output_dir: Path) -> SlurmRenderResult:
    """写出 compute-ready 的 sbatch 脚本与桥接计划 JSON。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    script_path = output_dir / "autovla_gr00t_gpu200_multiformat.sbatch"
    plan_path = output_dir / "telemetry_bridge_plan.json"
    script_path.write_text(_render_sbatch_script(config), encoding="utf-8")
    plan_payload = build_bridge_plan_payload(config)
    plan_payload.update(
        {
            "script_path": str(script_path),
            "slurm_partition": config.slurm_partition,
            "slurm_account": config.slurm_account,
            "cpus_per_task": config.cpus_per_task,
            "memory": config.memory,
            "time_limit": config.time_limit,
        }
    )
    plan_path.write_text(stable_json_dumps(plan_payload), encoding="utf-8")
    return SlurmRenderResult(script_path=script_path, plan_path=plan_path)
