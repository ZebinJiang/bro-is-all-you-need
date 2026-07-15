"""GPU200 多格式训练桥接 surface 测试。"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from autovla.training.telemetry import (
    load_telemetry_config,
    render_slurm_wrapper,
    write_base_model_manifest,
)


def _write_base_model_fixture(root: Path) -> Path:
    """写出最小本地 base model 目录夹具。"""
    root.mkdir(parents=True, exist_ok=True)
    for name in (
        "README.md",
        "LICENSE",
        "config.json",
        "processor_config.json",
        "model.safetensors.index.json",
        "model-00001-of-00002.safetensors",
        "model-00002-of-00002.safetensors",
        "embodiment_id.json",
        "statistics.json",
    ):
        (root / name).write_text(f"{name}\n", encoding="utf-8")
    return root


def _write_bridge_config(
    path: Path,
    output_root: Path,
    *,
    dataloader_num_workers: str = "4",
) -> Path:
    """写出 bridge-ready telemetry YAML 配置。"""
    base_model_root = _write_base_model_fixture(output_root / "base_model")
    isaac_root = output_root / "isaac_project"
    isaac_root.mkdir(parents=True, exist_ok=True)
    entrypoint_path = isaac_root / "gr00t" / "experiment" / "launch_finetune_n1d6.py"
    entrypoint_path.parent.mkdir(parents=True, exist_ok=True)
    entrypoint_path.write_text("print('placeholder')\n", encoding="utf-8")
    config_text = "\n".join(
        [
            "run_id: gr00t-gpu200-webdataset",
            "model_family_key: gr00t-n1d6",
            "model_registry_key: gr00t-n1d6",
            "env_profile: model-gr00t-n1d6",
            "datastore_name: zjh_webdataset_tar",
            f"candidate_store_root: {output_root / 'candidate_store'}",
            f"sample_window_manifest_path: {output_root / 'manifest.json'}",
            "sample_window_manifest_fingerprint: manifest-fp",
            "dataset_fingerprint: ds-fp",
            "transform_fingerprint: tf-fp",
            "statistics_fingerprint: stats-fp",
            f"isaac_project_root: {isaac_root}",
            f"isaac_entrypoint_path: {entrypoint_path}",
            f"python_executable: {sys.executable}",
            f"base_model_root: {base_model_root}",
            f"base_model_manifest_path: {output_root / 'manifests' / 'base_model_manifest.json'}",
            f"checkpoint_manifest_path: {output_root / 'manifests' / 'checkpoint_manifest.json'}",
            f"output_dir: {output_root / 'outputs'}",
            f"logs_root: {output_root / 'logs'}",
            f"table_output_root: {output_root / 'tables'}",
            "max_steps: 200",
            "sampling_interval_steps: 1",
            "slurm_partition: a100",
            "slurm_account: null",
            "cpus_per_task: 16",
            "memory: 64G",
            "time_limit: 00:30:00",
            "gres: gpu:1",
            "num_gpus: 1",
            "wandb_mode: offline",
            "hf_hub_offline: true",
            "transformers_offline: true",
            "hf_datasets_offline: true",
            "allow_network: false",
            "allow_checkpoint_download: false",
            "require_compute_node: true",
            "embodiment_tag: new_embodiment",
            f"modality_config_path: {output_root / 'modality_config.py'}",
            "global_batch_size: 8",
            f"dataloader_num_workers: {dataloader_num_workers}",
        ]
    )
    (output_root / "candidate_store").mkdir(parents=True, exist_ok=True)
    (output_root / "manifest.json").write_text("{}", encoding="utf-8")
    (output_root / "modality_config.py").write_text("# placeholder\n", encoding="utf-8")
    path.write_text(config_text + "\n", encoding="utf-8")
    return path


def test_validate_config_cli_should_accept_bridge_ready_gpu200_contract(tmp_path: Path) -> None:
    """验证 validate-config 接受真实桥接所需的有界合同。"""
    config_path = _write_bridge_config(tmp_path / "telemetry.yaml", tmp_path / "runtime")

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "autovla.training.telemetry",
            "validate-config",
            "--config",
            str(config_path),
        ],
        capture_output=True,
        check=False,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["max_steps"] == 200
    assert payload["num_gpus"] == 1
    assert payload["gres"] == "gpu:1"
    assert payload["require_compute_node"] is True
    assert payload["model_runtime_status"] == "bridge_ready_unverified"


def test_load_telemetry_config_should_reject_metadata_only_gpu_contract(tmp_path: Path) -> None:
    """验证旧的 metadata-only `gres: none` 合同被拒绝。"""
    config_path = _write_bridge_config(tmp_path / "telemetry.yaml", tmp_path / "runtime")
    config_path.write_text(
        config_path.read_text(encoding="utf-8").replace("gres: gpu:1", "gres: none"),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="gres must not be none"):
        load_telemetry_config(config_path)


def test_write_base_model_manifest_should_render_deterministic_local_only_provenance(
    tmp_path: Path,
) -> None:
    """验证 base-model manifest 稳定记录本地只读 provenance。"""
    config = load_telemetry_config(
        _write_bridge_config(tmp_path / "telemetry.yaml", tmp_path / "runtime")
    )

    manifest_path = write_base_model_manifest(config)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == "autovla.training.telemetry.base_model_manifest.v1"
    assert payload["task_id"] == "AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001"
    assert payload["path_policy"]["local_only"] is True
    assert payload["path_policy"]["no_download"] is True
    assert payload["claim_boundary"]["runnable_bounded_telemetry_only"] is True
    assert payload["claim_boundary"]["training_readiness_validated"] is False
    assert payload["required_file_presence"]["statistics.json"] is True


def test_render_slurm_wrapper_should_target_bridge_entry_and_real_gpu_intent(
    tmp_path: Path,
) -> None:
    """验证 Slurm wrapper 指向桥接入口而非旧 metadata-only 路径。"""
    config = load_telemetry_config(
        _write_bridge_config(tmp_path / "telemetry.yaml", tmp_path / "runtime")
    )

    render = render_slurm_wrapper(config, tmp_path / "slurm")

    script_text = render.script_path.read_text(encoding="utf-8")
    plan_payload = json.loads(render.plan_path.read_text(encoding="utf-8"))

    assert "autovla.training.telemetry bridge-run" in script_text
    assert "--gres=gpu:1" in script_text
    assert "WANDB_MODE=offline" in script_text
    assert "HF_HUB_OFFLINE=1" in script_text
    assert plan_payload["command_argv"][0].endswith("/python")
    output_index = plan_payload["command_argv"].index("--output-dir")
    assert plan_payload["command_argv"][output_index + 1] == str(config.output_dir)
    assert plan_payload["isaac_entrypoint_path"] == config.isaac_entrypoint_path
    assert plan_payload["external_effects"]["real_training"] is False
    assert plan_payload["max_steps"] == 200


def test_load_telemetry_config_should_accept_single_process_dataloader_mode(
    tmp_path: Path,
) -> None:
    """验证 `dataloader_num_workers: 0` 可作为单进程重试表达。"""
    config = load_telemetry_config(
        _write_bridge_config(
            tmp_path / "telemetry.yaml",
            tmp_path / "runtime",
            dataloader_num_workers="0",
        )
    )

    assert config.dataloader_num_workers == 0


def test_render_bridge_command_should_preserve_zero_worker_override(tmp_path: Path) -> None:
    """验证桥接命令会保留 `--dataloader-num-workers 0`。"""
    config = load_telemetry_config(
        _write_bridge_config(
            tmp_path / "telemetry.yaml",
            tmp_path / "runtime",
            dataloader_num_workers="0",
        )
    )

    render = render_slurm_wrapper(config, tmp_path / "slurm")
    plan_payload = json.loads(render.plan_path.read_text(encoding="utf-8"))
    worker_index = plan_payload["command_argv"].index("--dataloader-num-workers")

    assert plan_payload["command_argv"][worker_index + 1] == "0"


def test_load_telemetry_config_should_reject_negative_dataloader_workers(
    tmp_path: Path,
) -> None:
    """验证负数 dataloader worker 仍然被拒绝。"""
    config_path = _write_bridge_config(
        tmp_path / "telemetry.yaml",
        tmp_path / "runtime",
        dataloader_num_workers="-1",
    )

    with pytest.raises(ValueError, match="dataloader_num_workers must not be negative"):
        load_telemetry_config(config_path)


def test_load_telemetry_config_should_reject_bool_dataloader_workers(tmp_path: Path) -> None:
    """验证布尔值 dataloader worker 仍然被拒绝。"""
    config_path = _write_bridge_config(
        tmp_path / "telemetry.yaml",
        tmp_path / "runtime",
        dataloader_num_workers="true",
    )

    with pytest.raises(TypeError, match="dataloader_num_workers must be an int or null"):
        load_telemetry_config(config_path)
