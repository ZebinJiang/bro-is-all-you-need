"""AutoVLA 唯一严格分层实验配置。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, replace
from typing import cast

from autovla.config.schema.acceleration import AccelerationConfig
from autovla.config.schema.assets import AssetConfig
from autovla.config.schema.base import BaseConfig, require_schema_version
from autovla.config.schema.checkpoint import CheckpointConfig
from autovla.config.schema.data import DataConfig
from autovla.config.schema.deployment import DeploymentConfig
from autovla.config.schema.environment import EnvironmentConfig
from autovla.config.schema.inference import InferenceConfig
from autovla.config.schema.model import ModelConfig
from autovla.config.schema.optimization import OptimizationConfig
from autovla.config.schema.run import RunConfig
from autovla.config.schema.runner import RunnerBackend, RunnerConfig
from autovla.config.schema.telemetry import TelemetryConfig
from autovla.config.schema.topology import TopologyConfig
from autovla.config.schema.training import TrainingConfig
from autovla.config.schema.transforms import TransformsConfig

_STRATEGY_TO_RUNNER_BACKEND = {
    "single_gpu": RunnerBackend.LOCAL,
    "distributed_data_parallel": RunnerBackend.DDP,
    "deepspeed_zero_1": RunnerBackend.DEEPSPEED,
    "deepspeed_zero_2": RunnerBackend.DEEPSPEED,
    "deepspeed_zero_3": RunnerBackend.DEEPSPEED,
}


@dataclass(frozen=True, slots=True)
class ExperimentConfig(BaseConfig):
    """组合十一组生产配置并提供单向旧读取视图。"""

    run: RunConfig = field(default_factory=RunConfig)
    data: DataConfig = field(default_factory=DataConfig)
    model: ModelConfig = field(default_factory=ModelConfig)
    transforms: TransformsConfig = field(default_factory=TransformsConfig)
    topology: TopologyConfig = field(default_factory=TopologyConfig)
    training: TrainingConfig = field(default_factory=TrainingConfig)
    optimization: OptimizationConfig = field(default_factory=OptimizationConfig)
    checkpoint: CheckpointConfig = field(default_factory=CheckpointConfig)
    telemetry: TelemetryConfig = field(default_factory=TelemetryConfig)
    inference: InferenceConfig = field(default_factory=InferenceConfig)
    deployment: DeploymentConfig = field(default_factory=DeploymentConfig)
    _assets_compatibility: AssetConfig = field(
        default_factory=AssetConfig,
        repr=False,
        compare=False,
    )
    _runner_compatibility: RunnerConfig = field(
        default_factory=RunnerConfig,
        repr=False,
        compare=False,
    )

    def __post_init__(self) -> None:
        """校验版本并让旧 TrainingContext 始终消费 canonical 组。"""
        require_schema_version(self.schema_version, "schema_version")
        runtime_training = replace(
            self.training,
            optimization=self.optimization,
            distributed=self.topology.distributed,
            precision=self.topology.precision,
            checkpoint=self.checkpoint,
            logging=self.telemetry.logging,
        )
        object.__setattr__(self, "training", runtime_training)

    @property
    def name(self) -> str:
        """返回旧调用所需的 canonical 运行名称。"""
        return self.run.name

    @property
    def seed(self) -> int:
        """返回旧调用所需的 canonical 随机种子。"""
        return self.run.seed

    @property
    def assets(self) -> AssetConfig:
        """返回仅供本地资产解析的冻结兼容视图。"""
        return self._assets_compatibility

    @property
    def environment(self) -> EnvironmentConfig:
        """返回 GPU-only 环境兼容视图。"""
        return EnvironmentConfig(precision=self.topology.precision.mode)

    @property
    def global_batch_size(self) -> int:
        """返回 micro-batch x accumulation x data-parallel world-size。"""
        return (
            self.data.loader.batch_size
            * self.training.gradient_accumulation_steps
            * self.topology.distributed.world_size
        )

    @property
    def runner(self) -> RunnerConfig:
        """从 canonical 组派生只读旧运行器视图。"""
        backend = _STRATEGY_TO_RUNNER_BACKEND[self.topology.distributed.strategy_key]
        compatibility = self._runner_compatibility
        return RunnerConfig(
            schema_version=compatibility.schema_version,
            backend=backend,
            batch_size=self.data.loader.batch_size,
            max_steps=self.training.max_steps or RunnerConfig().max_steps,
            device=self.topology.distributed.device,
            learning_rate=self.optimization.learning_rate,
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
        """从 canonical 精度派生只读旧加速视图。"""
        mode = self.topology.precision.mode
        if mode == "float32":
            return AccelerationConfig(enabled=False, mixed_precision="none")
        return AccelerationConfig(
            enabled=True,
            mixed_precision="bf16" if mode == "bfloat16" else "fp16",
        )

    def to_resolved_dict(self) -> dict[str, object]:
        """返回仅包含十一组 canonical 配置的稳定载荷。"""
        payload = asdict(self)
        payload.pop("_assets_compatibility", None)
        payload.pop("_runner_compatibility", None)
        training = payload["training"]
        if not isinstance(training, dict):
            raise TypeError("resolved training config must be a mapping")
        training_payload = cast(dict[str, object], training)
        for duplicate in ("optimization", "distributed", "precision", "checkpoint", "logging"):
            training_payload.pop(duplicate, None)
        return payload

    def to_semantic_dict(self) -> dict[str, object]:
        """返回 fingerprint 载荷; 本地路径保留以保证精确实验身份。"""
        return self.to_resolved_dict()

    @property
    def fingerprint(self) -> str:
        """返回确定性 SHA-256 配置指纹。"""
        encoded = json.dumps(
            self.to_semantic_dict(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


__all__ = ["ExperimentConfig"]
