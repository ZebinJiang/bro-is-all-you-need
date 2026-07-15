"""GR00T 有界桥接运行时表面。"""

from __future__ import annotations

import os
import subprocess

from autovla.training.metrics import stable_json_dumps
from autovla.training.telemetry.bridge_manifest import write_base_model_manifest
from autovla.training.telemetry.config import TelemetryConfig


def render_bridge_command(config: TelemetryConfig) -> list[str]:
    """渲染后续真实 200-step bounded run 的 Isaac argv。"""
    command = [
        config.python_executable,
        config.isaac_entrypoint_path,
        "--base-model-path",
        config.base_model_root,
        "--dataset-path",
        config.candidate_store_root,
        "--embodiment-tag",
        config.embodiment_tag,
        "--num-gpus",
        str(config.num_gpus),
        "--output-dir",
        str(config.output_dir),
        "--max-steps",
        str(config.max_steps),
    ]
    if config.modality_config_path is not None:
        command.extend(["--modality-config-path", config.modality_config_path])
    if config.global_batch_size is not None:
        command.extend(["--global-batch-size", str(config.global_batch_size)])
    if config.dataloader_num_workers is not None:
        command.extend(["--dataloader-num-workers", str(config.dataloader_num_workers)])
    return command


def build_bridge_plan_payload(config: TelemetryConfig) -> dict[str, object]:
    """构造桥接运行计划负载。"""
    manifest_path = write_base_model_manifest(config)
    output_log_path = config.logs_root / f"{config.run_id}.stdout.log"
    error_log_path = config.logs_root / f"{config.run_id}.stderr.log"
    return {
        "schema_version": "autovla.training.telemetry.bridge_plan.v1",
        "run_id": config.run_id,
        "model_family_key": config.model_family_key,
        "model_registry_key": config.model_registry_key,
        "isaac_entrypoint_path": config.isaac_entrypoint_path,
        "base_model_manifest_path": str(manifest_path),
        "checkpoint_manifest_path": config.checkpoint_manifest_path,
        "dataset_fingerprint": config.dataset_fingerprint,
        "transform_fingerprint": config.transform_fingerprint,
        "statistics_fingerprint": config.statistics_fingerprint,
        "sample_window_manifest_path": config.sample_window_manifest_path,
        "sample_window_manifest_fingerprint": config.sample_window_manifest_fingerprint,
        "command_argv": render_bridge_command(config),
        "rendered_command": " ".join(render_bridge_command(config)),
        "output_dir": str(config.output_dir),
        "logs_root": str(config.logs_root),
        "table_output_root": str(config.table_output_root),
        "output_log_path": str(output_log_path),
        "error_log_path": str(error_log_path),
        "runtime_offline_env": {
            "WANDB_MODE": config.wandb_mode,
            "HF_HUB_OFFLINE": "1" if config.hf_hub_offline else "0",
            "TRANSFORMERS_OFFLINE": "1" if config.transformers_offline else "0",
            "HF_DATASETS_OFFLINE": "1" if config.hf_datasets_offline else "0",
        },
        "external_effects": {
            "real_training": False,
            "wandb_online": False,
            "hf_network": False,
            "checkpoint_download": False,
        },
        "claim_boundary": {
            "runnable_bounded_telemetry_only": True,
            "training_readiness_validated": False,
            "model_compatibility_validated": False,
        },
        "max_steps": config.max_steps,
        "num_gpus": config.num_gpus,
        "gres": config.gres,
    }


def run_bridge(config: TelemetryConfig) -> int:
    """在受控 compute node 上启动 Isaac bounded bridge。"""
    if config.require_compute_node and "SLURM_JOB_ID" not in os.environ:
        raise RuntimeError("bridge-run requires a compute node allocation")
    write_base_model_manifest(config)
    config.logs_root.mkdir(parents=True, exist_ok=True)
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.table_output_root.mkdir(parents=True, exist_ok=True)
    stdout_path = config.logs_root / f"{config.run_id}.stdout.log"
    stderr_path = config.logs_root / f"{config.run_id}.stderr.log"
    with (
        stdout_path.open("w", encoding="utf-8") as stdout_file,
        stderr_path.open("w", encoding="utf-8") as stderr_file,
    ):
        env = os.environ.copy()
        env.update(
            {
                "WANDB_MODE": config.wandb_mode,
                "HF_HUB_OFFLINE": "1",
                "TRANSFORMERS_OFFLINE": "1",
                "HF_DATASETS_OFFLINE": "1",
            }
        )
        result = subprocess.run(
            render_bridge_command(config),
            check=False,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
            text=True,
        )
    bridge_result_path = config.output_dir / "bridge_runtime_result.json"
    bridge_result_path.write_text(
        stable_json_dumps(
            {
                "schema_version": "autovla.training.telemetry.bridge_runtime_result.v1",
                "returncode": result.returncode,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
            }
        ),
        encoding="utf-8",
    )
    return result.returncode
