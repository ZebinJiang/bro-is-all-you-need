"""AutoVLA 解析后配置导出。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from autovla.config.schema import ExperimentConfig


def to_resolved_dict(config: ExperimentConfig) -> dict[str, Any]:
    """将实验配置转换为可序列化普通字典。

    Args:
        config: 已校验的实验配置。

    Returns:
        使用字符串后端值的普通字典。
    """
    return {
        "schema_version": config.schema_version,
        "name": config.name,
        "seed": config.seed,
        "model": {
            "schema_version": config.model.schema_version,
            "name": config.model.name,
            "registry_key": config.model.registry_key,
        },
        "data": {
            "schema_version": config.data.schema_version,
            "name": config.data.name,
            "root": config.data.root,
            "required_modalities": list(config.data.required_modalities),
            "backend": config.data.backend,
        },
        "runner": {
            "schema_version": config.runner.schema_version,
            "backend": config.runner.backend.value,
            "batch_size": config.runner.batch_size,
            "max_steps": config.runner.max_steps,
            "device": config.runner.device,
            "learning_rate": config.runner.learning_rate,
            "grad_accumulation_steps": config.runner.grad_accumulation_steps,
            "action_horizon": config.runner.action_horizon,
            "action_dim": config.runner.action_dim,
            "timeout": config.runner.timeout,
            "batch_adapter": config.runner.batch_adapter,
            "policy": config.runner.policy,
            "loss": config.runner.loss,
            "checkpoint_adapter": config.runner.checkpoint_adapter,
            "runtime_plan": config.runner.runtime_plan,
            "deployment_hook": config.runner.deployment_hook,
        },
        "deployment": {
            "schema_version": config.deployment.schema_version,
            "enabled": config.deployment.enabled,
            "timeout": config.deployment.timeout,
        },
        "acceleration": {
            "schema_version": config.acceleration.schema_version,
            "enabled": config.acceleration.enabled,
            "mixed_precision": config.acceleration.mixed_precision,
        },
    }


def resolved_config_fingerprint(config: ExperimentConfig) -> str:
    """返回解析后配置的稳定 SHA256 指纹。"""
    payload = json.dumps(
        to_resolved_dict(config),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def export_resolved_yaml(config: ExperimentConfig, path: str | Path) -> None:
    """将解析后的实验配置导出为 YAML。

    Args:
        config: 已校验的实验配置。
        path: 输出 YAML 路径。
    """
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(OmegaConf.create(to_resolved_dict(config)), output_path)
