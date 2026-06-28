"""M3 CLI local-smoke execution manifest。"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from pathlib import Path

from autovla.training.config import LocalRunnerDryRunConfig

LOCAL_SMOKE_MODE = "local-smoke"
EXECUTION_MANIFEST_SCHEMA_VERSION = "m3-cli-local-smoke-execution.v1"
EXECUTION_MANIFEST_FILENAME = "execution_manifest.json"


def _stable_metrics(metrics: Mapping[str, float]) -> dict[str, float]:
    """返回按 key 稳定排序的有限 float 指标。"""
    output: dict[str, float] = {}
    for key in sorted(metrics):
        value = metrics[key]
        if isinstance(value, bool):
            raise TypeError(f"metric {key} must be numeric")
        number = float(value)
        if not math.isfinite(number):
            raise ValueError(f"metric {key} must be finite")
        output[str(key)] = number
    return output


def _relative_to_output(config: LocalRunnerDryRunConfig, path: Path) -> str:
    """把输出路径收窄为相对 output_dir 的稳定路径。"""
    try:
        return path.relative_to(config.output_dir).as_posix()
    except ValueError as exc:
        raise ValueError("execution output must stay under output_dir") from exc


def build_execution_manifest(
    config: LocalRunnerDryRunConfig,
    *,
    train_metrics: Mapping[str, float],
    eval_metrics: Mapping[str, float],
    checkpoint_manifest_path: Path,
    resumed_step: int,
) -> dict[str, object]:
    """构造 deterministic local-smoke execution manifest。"""
    local_config = config.to_local_runner_config()
    execution_manifest_path = config.output_dir / config.run_id / EXECUTION_MANIFEST_FILENAME
    checkpoint_relative_path = _relative_to_output(config, checkpoint_manifest_path)
    return {
        "action": {
            "dim": config.action_dim,
            "horizon": config.action_horizon,
        },
        "artifacts": {
            "checkpoint_manifest": checkpoint_relative_path,
            "execution_manifest": _relative_to_output(config, execution_manifest_path),
        },
        "config": {
            "dataset_fingerprint": local_config.dataset_fingerprint,
            "max_steps": local_config.max_steps,
            "model_registry_key": local_config.model_registry_key,
            "run_id": local_config.run_id,
            "run_root": ".",
            "seed": local_config.seed,
            "statistics_fingerprint": local_config.statistics_fingerprint,
            "transform_fingerprint": local_config.transform_fingerprint,
        },
        "dry_run": False,
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
        "local_smoke": True,
        "metrics": {
            "eval": _stable_metrics(eval_metrics),
            "train": _stable_metrics(train_metrics),
        },
        "mode": LOCAL_SMOKE_MODE,
        "resume": {
            "checkpoint_manifest": checkpoint_relative_path,
            "compatible": True,
            "resumed_step": resumed_step,
        },
        "schema_version": EXECUTION_MANIFEST_SCHEMA_VERSION,
    }


def write_execution_manifest(
    config: LocalRunnerDryRunConfig,
    *,
    train_metrics: Mapping[str, float],
    eval_metrics: Mapping[str, float],
    checkpoint_manifest_path: Path,
    resumed_step: int,
) -> Path:
    """写入稳定排序的 local-smoke execution manifest。"""
    output_path = config.output_dir / config.run_id / EXECUTION_MANIFEST_FILENAME
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            build_execution_manifest(
                config,
                train_metrics=train_metrics,
                eval_metrics=eval_metrics,
                checkpoint_manifest_path=checkpoint_manifest_path,
                resumed_step=resumed_step,
            ),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return output_path
