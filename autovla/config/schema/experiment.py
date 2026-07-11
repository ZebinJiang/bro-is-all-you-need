"""AutoVLA 唯一实验顶层配置结构。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
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
from autovla.config.schema.runner import RunnerBackend, RunnerConfig
from autovla.config.schema.training import TrainingConfig

_STRATEGY_TO_RUNNER_BACKEND = {
    "single_device": RunnerBackend.LOCAL,
    "distributed_data_parallel": RunnerBackend.DDP,
    "fully_sharded_data_parallel": RunnerBackend.FSDP,
}


@dataclass(frozen=True, slots=True)
class ExperimentConfig(BaseConfig):
    """组合模型、数据与运行器的顶层实验配置。

    Args:
        schema_version: 顶层配置版本。M1 仅接受 ``"1.0"``。
        name: 实验名称,不能为空。
        seed: 随机种子,必须为非负整数。
        model: 模型身份配置。
        data: 数据身份配置。
        training: 训练生命周期配置。
        deployment: 部署占位配置。
    """

    name: str = "unconfigured_experiment"
    seed: int = 7
    model: ModelConfig = field(default_factory=ModelConfig)
    data: DataConfig = field(default_factory=DataConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    _runner_compatibility: RunnerConfig = field(
        default_factory=RunnerConfig,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """校验顶层实验配置构造器不变量。"""
        require_schema_version(self.schema_version, "schema_version")
        require_non_empty_str(self.name, "name")
        seed = require_int(self.seed, "seed")
        if seed < 0:
            raise ValueError("seed must be non-negative")
        model = cast(object, self.model)
        data = cast(object, self.data)
        training = cast(object, self.training)
        deployment = cast(object, self.deployment)
        if not isinstance(model, ModelConfig):
            raise ValueError("model must be a ModelConfig")
        if not isinstance(data, DataConfig):
            raise ValueError("data must be a DataConfig")
        if not isinstance(training, TrainingConfig):
            raise ValueError("training must be a TrainingConfig")
        if not isinstance(deployment, DeploymentConfig):
            raise ValueError("deployment must be a DeploymentConfig")

    @property
    def runner(self) -> RunnerConfig:
        """返回由规范配置派生的只读旧运行器视图。

        批大小、步数、学习率、累积步数和执行策略始终来自规范 Data/Training
        配置。仅旧动作适配器等尚无规范归属的字段读取冻结兼容状态。
        """
        try:
            backend = _STRATEGY_TO_RUNNER_BACKEND[self.training.distributed.strategy_key]
        except KeyError as exc:
            raise ValueError(
                "canonical distributed strategy has no legacy runner view: "
                f"{self.training.distributed.strategy_key}"
            ) from exc
        compatibility = self._runner_compatibility
        return RunnerConfig(
            schema_version=compatibility.schema_version,
            backend=backend,
            batch_size=self.data.loader.batch_size,
            max_steps=self.training.max_steps or RunnerConfig().max_steps,
            device=compatibility.device,
            learning_rate=self.training.optimization.learning_rate,
            grad_accumulation_steps=self.training.gradient_accumulation_steps,
            action_horizon=compatibility.action_horizon,
            action_dim=compatibility.action_dim,
            timeout=compatibility.timeout,
            batch_adapter=compatibility.batch_adapter,
            policy=compatibility.policy,
            loss=compatibility.loss,
            checkpoint_adapter=compatibility.checkpoint_adapter,
            runtime_plan=compatibility.runtime_plan,
            deployment_hook=compatibility.deployment_hook,
        )

    @property
    def acceleration(self) -> AccelerationConfig:
        """返回由规范精度模式派生的只读旧加速视图。"""
        mode = self.training.precision.mode
        if mode == "float32":
            return AccelerationConfig(enabled=False, mixed_precision="none")
        if mode == "bfloat16":
            return AccelerationConfig(enabled=True, mixed_precision="bf16")
        if mode == "float16":
            return AccelerationConfig(enabled=True, mixed_precision="fp16")
        raise ValueError(f"canonical precision has no legacy acceleration view: {mode}")

    def to_resolved_dict(self) -> dict[str, object]:
        """返回同时可重载旧视图的稳定指纹载荷。"""
        payload = asdict(self)
        payload.pop("_runner_compatibility", None)
        runner = asdict(self.runner)
        runner["backend"] = self.runner.backend.value
        if self.training.max_steps is None:
            runner.pop("max_steps", None)
        payload["runner"] = runner
        payload["acceleration"] = asdict(self.acceleration)
        return payload

    @property
    def fingerprint(self) -> str:
        """返回环境无关、字段排序稳定的 SHA256 配置指纹。"""
        payload = json.dumps(
            self.to_resolved_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
