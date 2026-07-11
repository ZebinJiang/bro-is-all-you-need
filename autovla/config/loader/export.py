"""AutoVLA 解析后配置导出。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from omegaconf import OmegaConf

from autovla.config.schema import ExperimentConfig


def to_resolved_dict(config: ExperimentConfig) -> dict[str, Any]:
    """导出规范配置和由其派生的只读旧兼容视图。"""
    return config.to_resolved_dict()


def resolved_config_fingerprint(config: ExperimentConfig) -> str:
    """返回实验配置自身的稳定 SHA256 指纹。"""
    return config.fingerprint


def export_resolved_yaml(config: ExperimentConfig, path: str | Path) -> None:
    """将解析后的实验配置写入显式本地 YAML 路径。"""
    output_path = Path(path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    OmegaConf.save(OmegaConf.create(to_resolved_dict(config)), output_path)


__all__ = ["export_resolved_yaml", "resolved_config_fingerprint", "to_resolved_dict"]
