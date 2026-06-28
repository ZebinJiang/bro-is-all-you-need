"""M3 本地 runner dry-run manifest。"""

from __future__ import annotations

import json
from pathlib import Path

from autovla.training.config import LocalRunnerDryRunConfig

DRY_RUN_MANIFEST_SCHEMA_VERSION = "m3-runner-config-cli-dry-run.v1"
DRY_RUN_MANIFEST_FILENAME = "dry_run_manifest.json"


def build_dry_run_manifest(config: LocalRunnerDryRunConfig) -> dict[str, object]:
    """构造不含环境依赖字段的 dry-run manifest。"""
    local_config = config.to_local_runner_config()
    return {
        "action": {
            "dim": config.action_dim,
            "horizon": config.action_horizon,
        },
        "dry_run": True,
        "external_effects": {
            "checkpoint_weight_load": False,
            "endpoint": False,
            "external_dataset": False,
            "gpu": False,
            "hf": False,
            "network": False,
            "real_model": False,
            "real_training": False,
            "robot": False,
            "slurm": False,
            "wandb": False,
        },
        "local_runner_config": {
            "dataset_fingerprint": local_config.dataset_fingerprint,
            "max_steps": local_config.max_steps,
            "model_registry_key": local_config.model_registry_key,
            "run_id": local_config.run_id,
            "run_root": ".",
            "seed": local_config.seed,
            "statistics_fingerprint": local_config.statistics_fingerprint,
            "transform_fingerprint": local_config.transform_fingerprint,
        },
        "mode": config.mode,
        "planned_outputs": {
            "checkpoint_dir": f"{config.run_id}/checkpoints",
            "checkpoint_manifest": None,
            "run_dir": config.run_id,
        },
        "schema_version": DRY_RUN_MANIFEST_SCHEMA_VERSION,
    }


def write_dry_run_manifest(config: LocalRunnerDryRunConfig) -> Path:
    """写入稳定排序的 dry-run manifest。"""
    output_path = config.output_dir / config.run_id / DRY_RUN_MANIFEST_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_dry_run_manifest(config),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path
