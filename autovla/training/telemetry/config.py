"""多格式 GPU200 训练桥接配置契约。"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast

import yaml


def _require_non_empty_text(value: str, name: str) -> str:
    """校验非空文本字段。"""
    text = str(value).strip()
    if not text:
        raise ValueError(f"{name} must not be empty")
    return text


def _require_exact_int(value: object, name: str, expected: int) -> int:
    """校验严格 int 且命中预期值。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value != expected:
        raise ValueError(f"{name} must be exactly {expected}")
    return value


def _require_positive_int(value: object, name: str) -> int:
    """校验正整数且拒绝 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int")
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


def _require_non_negative_int_or_null(value: object, name: str) -> int:
    """校验非负整数, 允许 0, 不允许 bool。"""
    if type(value) is not int:
        raise TypeError(f"{name} must be an int or null")
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _require_bool(value: object, name: str) -> bool:
    """校验严格布尔字段。"""
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool")
    return value


def _require_mapping(value: object) -> Mapping[str, object]:
    """校验 YAML 顶层对象为映射。"""
    if not isinstance(value, Mapping):
        raise ValueError("telemetry config must be a mapping")
    raw_mapping = cast(Mapping[object, object], value)
    normalized: dict[str, object] = {}
    for key, item in raw_mapping.items():
        normalized[str(key)] = item
    return normalized


def _require_text_field(payload: Mapping[str, object], key: str) -> str:
    """读取必填文本字段。"""
    if key not in payload:
        raise ValueError(f"missing required field: {key}")
    return _require_non_empty_text(str(payload[key]), key)


def _require_int_field(payload: Mapping[str, object], key: str) -> int:
    """读取必填整数字段。"""
    if key not in payload:
        raise ValueError(f"missing required field: {key}")
    return _require_positive_int(payload[key], key)


def _require_bool_field(payload: Mapping[str, object], key: str) -> bool:
    """读取必填布尔字段。"""
    if key not in payload:
        raise ValueError(f"missing required field: {key}")
    return _require_bool(payload[key], key)


def _optional_text_field(payload: Mapping[str, object], key: str) -> str | None:
    """读取可选文本字段。"""
    value = payload.get(key)
    if value is None:
        return None
    return _require_non_empty_text(str(value), key)


def _optional_non_negative_int_field(payload: Mapping[str, object], key: str) -> int | None:
    """读取可选非负整数字段, 允许 null。"""
    if key not in payload:
        return None
    value = payload[key]
    if value is None:
        return None
    return _require_non_negative_int_or_null(value, key)


@dataclass(frozen=True, slots=True)
class TelemetryConfig:
    """有界 GR00T GPU200 训练桥接配置。"""

    run_id: str
    model_family_key: str
    model_registry_key: str
    env_profile: str
    datastore_name: str
    candidate_store_root: str
    sample_window_manifest_path: str
    sample_window_manifest_fingerprint: str
    dataset_fingerprint: str
    transform_fingerprint: str
    statistics_fingerprint: str
    isaac_project_root: str
    isaac_entrypoint_path: str
    python_executable: str
    base_model_root: str
    base_model_manifest_path: str
    checkpoint_manifest_path: str
    output_dir: Path
    logs_root: Path
    table_output_root: Path
    max_steps: int
    sampling_interval_steps: int
    slurm_partition: str
    slurm_account: str | None
    cpus_per_task: int
    memory: str
    time_limit: str
    gres: str
    num_gpus: int
    wandb_mode: str
    hf_hub_offline: bool
    transformers_offline: bool
    hf_datasets_offline: bool
    allow_network: bool
    allow_checkpoint_download: bool
    require_compute_node: bool
    embodiment_tag: str
    modality_config_path: str | None
    global_batch_size: int | None
    dataloader_num_workers: int | None

    def __post_init__(self) -> None:
        """保持本 tranche 的有界桥接合同。"""
        object.__setattr__(self, "run_id", _require_non_empty_text(self.run_id, "run_id"))
        if self.model_family_key != "gr00t-n1d6":
            raise ValueError("model_family_key must be gr00t-n1d6")
        if self.model_registry_key != "gr00t-n1d6":
            raise ValueError("model_registry_key must be gr00t-n1d6")
        if self.env_profile != "model-gr00t-n1d6":
            raise ValueError("env_profile must be model-gr00t-n1d6")
        for field_name in (
            "datastore_name",
            "candidate_store_root",
            "sample_window_manifest_path",
            "sample_window_manifest_fingerprint",
            "dataset_fingerprint",
            "transform_fingerprint",
            "statistics_fingerprint",
            "isaac_project_root",
            "isaac_entrypoint_path",
            "python_executable",
            "base_model_root",
            "base_model_manifest_path",
            "checkpoint_manifest_path",
            "slurm_partition",
            "memory",
            "time_limit",
            "gres",
            "wandb_mode",
            "embodiment_tag",
        ):
            object.__setattr__(
                self,
                field_name,
                _require_non_empty_text(cast(str, getattr(self, field_name)), field_name),
            )
        if self.modality_config_path is not None:
            object.__setattr__(
                self,
                "modality_config_path",
                _require_non_empty_text(self.modality_config_path, "modality_config_path"),
            )
        if self.gres == "none":
            raise ValueError("gres must not be none")
        object.__setattr__(self, "max_steps", _require_exact_int(self.max_steps, "max_steps", 200))
        object.__setattr__(self, "num_gpus", _require_exact_int(self.num_gpus, "num_gpus", 1))
        object.__setattr__(
            self,
            "sampling_interval_steps",
            _require_positive_int(self.sampling_interval_steps, "sampling_interval_steps"),
        )
        object.__setattr__(
            self, "cpus_per_task", _require_positive_int(self.cpus_per_task, "cpus_per_task")
        )
        if self.global_batch_size is not None:
            object.__setattr__(
                self,
                "global_batch_size",
                _require_positive_int(self.global_batch_size, "global_batch_size"),
            )
        if self.dataloader_num_workers is not None:
            object.__setattr__(
                self,
                "dataloader_num_workers",
                _require_non_negative_int_or_null(
                    self.dataloader_num_workers,
                    "dataloader_num_workers",
                ),
            )
        if self.wandb_mode not in {"offline", "disabled"}:
            raise ValueError("wandb_mode must be offline or disabled")
        if not self.hf_hub_offline:
            raise ValueError("hf_hub_offline must be true")
        if not self.transformers_offline:
            raise ValueError("transformers_offline must be true")
        if not self.hf_datasets_offline:
            raise ValueError("hf_datasets_offline must be true")
        if self.allow_network:
            raise ValueError("allow_network must be false")
        if self.allow_checkpoint_download:
            raise ValueError("allow_checkpoint_download must be false")
        if not self.require_compute_node:
            raise ValueError("require_compute_node must be true")
        for path_field in ("output_dir", "logs_root", "table_output_root"):
            path_value = cast(Path, getattr(self, path_field))
            if path_value.exists() and not path_value.is_dir():
                raise ValueError(f"{path_field} must be a directory")

    def to_json_dict(self) -> dict[str, object]:
        """返回稳定 JSON 摘要。"""
        return {
            "allow_checkpoint_download": self.allow_checkpoint_download,
            "allow_network": self.allow_network,
            "base_model_manifest_path": self.base_model_manifest_path,
            "base_model_root": self.base_model_root,
            "candidate_store_root": self.candidate_store_root,
            "checkpoint_manifest_path": self.checkpoint_manifest_path,
            "cpus_per_task": self.cpus_per_task,
            "dataloader_num_workers": self.dataloader_num_workers,
            "dataset_fingerprint": self.dataset_fingerprint,
            "datastore_name": self.datastore_name,
            "embodiment_tag": self.embodiment_tag,
            "env_profile": self.env_profile,
            "global_batch_size": self.global_batch_size,
            "gres": self.gres,
            "hf_datasets_offline": self.hf_datasets_offline,
            "hf_hub_offline": self.hf_hub_offline,
            "isaac_entrypoint_path": self.isaac_entrypoint_path,
            "isaac_project_root": self.isaac_project_root,
            "logs_root": str(self.logs_root),
            "max_steps": self.max_steps,
            "memory": self.memory,
            "modality_config_path": self.modality_config_path,
            "model_family_key": self.model_family_key,
            "model_registry_key": self.model_registry_key,
            "model_runtime_status": "bridge_ready_unverified",
            "num_gpus": self.num_gpus,
            "output_dir": str(self.output_dir),
            "python_executable": self.python_executable,
            "require_compute_node": self.require_compute_node,
            "run_id": self.run_id,
            "sample_window_manifest_fingerprint": self.sample_window_manifest_fingerprint,
            "sample_window_manifest_path": self.sample_window_manifest_path,
            "sampling_interval_steps": self.sampling_interval_steps,
            "slurm_account": self.slurm_account,
            "slurm_partition": self.slurm_partition,
            "statistics_fingerprint": self.statistics_fingerprint,
            "table_output_root": str(self.table_output_root),
            "time_limit": self.time_limit,
            "transform_fingerprint": self.transform_fingerprint,
            "transformers_offline": self.transformers_offline,
            "wandb_mode": self.wandb_mode,
        }


def load_telemetry_config(path: Path) -> TelemetryConfig:
    """从 YAML 读取 bridge-ready telemetry 配置。"""
    payload = _require_mapping(yaml.safe_load(path.read_text(encoding="utf-8")))
    return TelemetryConfig(
        run_id=_require_text_field(payload, "run_id"),
        model_family_key=_require_text_field(payload, "model_family_key"),
        model_registry_key=_require_text_field(payload, "model_registry_key"),
        env_profile=_require_text_field(payload, "env_profile"),
        datastore_name=_require_text_field(payload, "datastore_name"),
        candidate_store_root=_require_text_field(payload, "candidate_store_root"),
        sample_window_manifest_path=_require_text_field(payload, "sample_window_manifest_path"),
        sample_window_manifest_fingerprint=_require_text_field(
            payload, "sample_window_manifest_fingerprint"
        ),
        dataset_fingerprint=_require_text_field(payload, "dataset_fingerprint"),
        transform_fingerprint=_require_text_field(payload, "transform_fingerprint"),
        statistics_fingerprint=_require_text_field(payload, "statistics_fingerprint"),
        isaac_project_root=_require_text_field(payload, "isaac_project_root"),
        isaac_entrypoint_path=_require_text_field(payload, "isaac_entrypoint_path"),
        python_executable=_require_text_field(payload, "python_executable"),
        base_model_root=_require_text_field(payload, "base_model_root"),
        base_model_manifest_path=_require_text_field(payload, "base_model_manifest_path"),
        checkpoint_manifest_path=_require_text_field(payload, "checkpoint_manifest_path"),
        output_dir=Path(_require_text_field(payload, "output_dir")),
        logs_root=Path(_require_text_field(payload, "logs_root")),
        table_output_root=Path(_require_text_field(payload, "table_output_root")),
        max_steps=cast(int, payload["max_steps"]),
        sampling_interval_steps=_require_int_field(payload, "sampling_interval_steps"),
        slurm_partition=_require_text_field(payload, "slurm_partition"),
        slurm_account=_optional_text_field(payload, "slurm_account"),
        cpus_per_task=_require_int_field(payload, "cpus_per_task"),
        memory=_require_text_field(payload, "memory"),
        time_limit=_require_text_field(payload, "time_limit"),
        gres=_require_text_field(payload, "gres"),
        num_gpus=cast(int, payload["num_gpus"]),
        wandb_mode=_require_text_field(payload, "wandb_mode"),
        hf_hub_offline=_require_bool_field(payload, "hf_hub_offline"),
        transformers_offline=_require_bool_field(payload, "transformers_offline"),
        hf_datasets_offline=_require_bool_field(payload, "hf_datasets_offline"),
        allow_network=_require_bool_field(payload, "allow_network"),
        allow_checkpoint_download=_require_bool_field(payload, "allow_checkpoint_download"),
        require_compute_node=_require_bool_field(payload, "require_compute_node"),
        embodiment_tag=_require_text_field(payload, "embodiment_tag"),
        modality_config_path=_optional_text_field(payload, "modality_config_path"),
        global_batch_size=(
            _require_int_field(payload, "global_batch_size")
            if "global_batch_size" in payload
            else None
        ),
        dataloader_num_workers=(
            _optional_non_negative_int_field(payload, "dataloader_num_workers")
        ),
    )
