"""GenesisVLA 实验顶层配置结构。"""

from __future__ import annotations

from dataclasses import dataclass, field

from genesisvla.config.schema.acceleration import AccelerationConfig
from genesisvla.config.schema.base import BaseConfig
from genesisvla.config.schema.data import DataConfig
from genesisvla.config.schema.deployment import DeploymentConfig
from genesisvla.config.schema.model import ModelConfig
from genesisvla.config.schema.runner import RunnerConfig


@dataclass(frozen=True, slots=True)
class ExperimentConfig(BaseConfig):
    """组合模型、数据与运行器的顶层实验配置。

    Args:
        schema_version: 顶层配置版本。M1 仅接受 ``"1.0"``。
        name: 实验名称,不能为空。
        seed: 随机种子,必须为非负整数。
        model: 模型身份配置。
        data: 数据身份配置。
        runner: 运行器配置。
        deployment: 部署占位配置。
        acceleration: 加速占位配置。
    """

    name: str = "local_debug"
    seed: int = 7
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    runner: RunnerConfig = field(default_factory=RunnerConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    acceleration: AccelerationConfig = field(default_factory=AccelerationConfig)
