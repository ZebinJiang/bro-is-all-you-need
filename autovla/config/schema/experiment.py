"""AutoVLA 唯一实验顶层配置结构。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import cast

from autovla.config.schema.acceleration import AccelerationConfig
from autovla.config.schema.assets import AssetConfig
from autovla.config.schema.base import (
    BaseConfig,
    require_int,
    require_non_empty_str,
    require_schema_version,
)
from autovla.config.schema.data import DataConfig
from autovla.config.schema.deployment import DeploymentConfig
from autovla.config.schema.environment import EnvironmentConfig
from autovla.config.schema.model import ModelConfig
from autovla.config.schema.runner import RunnerBackend, RunnerConfig
from autovla.config.schema.training import TrainingConfig

_STRATEGY_TO_RUNNER_BACKEND = {
    "single_gpu": RunnerBackend.LOCAL,
    "distributed_data_parallel": RunnerBackend.DDP,
    "deepspeed": RunnerBackend.DEEPSPEED,
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
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    assets: AssetConfig = field(default_factory=AssetConfig)
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
        environment = cast(object, self.environment)
        assets = cast(object, self.assets)
        data = cast(object, self.data)
        training = cast(object, self.training)
        deployment = cast(object, self.deployment)
        if not isinstance(model, ModelConfig):
            raise ValueError("model must be a ModelConfig")
        if not isinstance(environment, EnvironmentConfig):
            raise ValueError("environment must be an EnvironmentConfig")
        if not isinstance(assets, AssetConfig):
            raise ValueError("assets must be an AssetConfig")
        if not isinstance(data, DataConfig):
            raise ValueError("data must be a DataConfig")
        if not isinstance(training, TrainingConfig):
            raise ValueError("training must be a TrainingConfig")
        if not isinstance(deployment, DeploymentConfig):
            raise ValueError("deployment must be a DeploymentConfig")
        if training.distributed.device != environment.device:
            raise ValueError("training device must match the production environment")
        if training.precision.mode != environment.precision:
            raise ValueError("training precision must match the production environment")

    @property
    def global_batch_size(self) -> int:
        """返回 micro-batch x accumulation x data-parallel world-size。"""

        return (
            self.data.loader.batch_size
            * self.training.gradient_accumulation_steps
            * self.training.distributed.world_size
        )

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
            device=self.training.distributed.device,
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
        """返回保留本地资产根且可重载旧视图的 resolved 载荷。"""
        payload = asdict(self)
        payload.pop("_runner_compatibility", None)
        runner = asdict(self.runner)
        runner["backend"] = self.runner.backend.value
        if self.training.max_steps is None:
            runner.pop("max_steps", None)
        payload["runner"] = runner
        payload["acceleration"] = asdict(self.acceleration)
        return payload

    def to_semantic_dict(self) -> dict[str, object]:
        """返回排除本机资产 store 绝对根的跨机器语义载荷。"""

        payload = self.to_resolved_dict()
        assets = payload.get("assets")
        if not isinstance(assets, dict):
            raise TypeError("resolved assets config must be a mapping")
        store = cast(dict[str, object], assets).get("store")
        if not isinstance(store, dict):
            raise TypeError("resolved asset store config must be a mapping")
        cast(dict[str, object], store).pop("root", None)
        return payload

    @property
    def fingerprint(self) -> str:
        """返回环境无关、字段排序稳定的 SHA256 配置指纹。"""
        payload = json.dumps(
            self.to_semantic_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
