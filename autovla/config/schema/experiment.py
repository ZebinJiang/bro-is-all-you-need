"""AutoVLA 实验顶层配置结构。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from autovla.config.schema.acceleration import AccelerationConfig
from autovla.config.schema.base import (
    BaseConfig,
    require_int,
    require_non_empty_str,
    require_schema_version,
)
from autovla.config.schema.data import DataConfig
from autovla.config.schema.deployment import DeploymentConfig
from autovla.config.schema.model import ModelConfig
from autovla.config.schema.runner import RunnerConfig


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

    def __post_init__(self) -> None:
        """校验顶层实验配置构造器不变量。"""
        require_schema_version(self.schema_version, "schema_version")
        require_non_empty_str(self.name, "name")
        seed = require_int(self.seed, "seed")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        model = cast(object, self.model)
        data = cast(object, self.data)
        runner = cast(object, self.runner)
        deployment = cast(object, self.deployment)
        acceleration = cast(object, self.acceleration)
        if not isinstance(model, ModelConfig):
            raise ValueError("model must be a ModelConfig")
        if not isinstance(data, DataConfig):
            raise ValueError("data must be a DataConfig")
        if not isinstance(runner, RunnerConfig):
            raise ValueError("runner must be a RunnerConfig")
        if not isinstance(deployment, DeploymentConfig):
            raise ValueError("deployment must be a DeploymentConfig")
        if not isinstance(acceleration, AccelerationConfig):
            raise ValueError("acceleration must be an AccelerationConfig")
