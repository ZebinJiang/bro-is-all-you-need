"""GR00T 本地基座模型 provenance manifest。"""

from __future__ import annotations

import subprocess
from pathlib import Path

from autovla.training.metrics import stable_json_dumps
from autovla.training.telemetry.config import TelemetryConfig

TASK_ID = "AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001"
SCHEMA_VERSION = "autovla.training.telemetry.base_model_manifest.v1"
REQUIRED_FILES = (
    "README.md",
    "LICENSE",
    "config.json",
    "processor_config.json",
    "model.safetensors.index.json",
    "model-00001-of-00002.safetensors",
    "model-00002-of-00002.safetensors",
    "embodiment_id.json",
    "statistics.json",
)


def _git_head_or_unknown(repo_root: Path) -> str:
    """读取本地 git HEAD, 失败时返回稳定占位值。"""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=True,
            cwd=repo_root,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown_not_git"
    return result.stdout.strip() or "unknown_not_git"


def build_base_model_manifest_payload(config: TelemetryConfig) -> dict[str, object]:
    """构造本地 base-model manifest 负载。"""
    base_model_root = Path(config.base_model_root)
    required_presence = {
        file_name: (base_model_root / file_name).is_file() for file_name in REQUIRED_FILES
    }
    weight_inventory = {
        file_name: {
            "present": (base_model_root / file_name).is_file(),
            "size_bytes": (
                (base_model_root / file_name).stat().st_size
                if (base_model_root / file_name).is_file()
                else None
            ),
        }
        for file_name in REQUIRED_FILES
        if file_name.endswith(".safetensors") or file_name.endswith(".index.json")
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "model_family_key": config.model_family_key,
        "model_registry_key": config.model_registry_key,
        "support_status_at_launch": "bridge_ready_unverified",
        "source_repo_root": config.isaac_project_root,
        "source_repo_head": _git_head_or_unknown(Path(config.isaac_project_root)),
        "base_model_root": config.base_model_root,
        "path_policy": {
            "read_only": True,
            "local_only": True,
            "no_download": True,
            "no_cache_probe": True,
            "no_mutation": True,
            "hf_online": False,
        },
        "required_files": list(REQUIRED_FILES),
        "required_file_presence": required_presence,
        "weight_inventory": weight_inventory,
        "license_and_card": {
            "license_present": required_presence["LICENSE"],
            "readme_present": required_presence["README.md"],
        },
        "runtime_offline_env": {
            "wandb_mode": config.wandb_mode,
            "hf_hub_offline": config.hf_hub_offline,
            "transformers_offline": config.transformers_offline,
            "hf_datasets_offline": config.hf_datasets_offline,
        },
        "claim_boundary": {
            "runnable_bounded_telemetry_only": True,
            "checkpoint_correctness_validated": False,
            "training_readiness_validated": False,
            "model_compatibility_validated": False,
            "tokenizer_processor_validated": False,
        },
    }


def write_base_model_manifest(config: TelemetryConfig) -> Path:
    """写出 AutoVLA-owned base-model provenance manifest。"""
    manifest_path = Path(config.base_model_manifest_path)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        stable_json_dumps(build_base_model_manifest_payload(config)),
        encoding="utf-8",
    )
    return manifest_path
