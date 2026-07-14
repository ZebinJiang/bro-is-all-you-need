"""AutoVLA 生产训练组件的轻量懒注册表。"""

from __future__ import annotations

from dataclasses import dataclass
from importlib import import_module
from typing import Protocol, cast

from autovla.core.registry import ComponentRegistry, ImportStringFactory
from autovla.training.contracts import ActionPolicy, BatchAdapter, CheckpointAdapter, LossAdapter


@dataclass(frozen=True, slots=True)
class TrainingComponentRegistration:
    """保存生产组件的规范键和延迟工厂。"""

    key: str
    factory: ImportStringFactory[object]


class TrainingStrategyRegistry(ComponentRegistry[TrainingComponentRegistration]):
    """保存显式训练策略,不选择默认策略。"""


class OptimizerRegistry(ComponentRegistry[TrainingComponentRegistration]):
    """保存优化器构造函数。"""


class LearningRateSchedulerRegistry(ComponentRegistry[TrainingComponentRegistration]):
    """保存学习率调度器构造函数。"""


class CallbackRegistry(ComponentRegistry[TrainingComponentRegistration]):
    """保存生产 callback 构造函数。"""


def _entry(key: str, factory_path: str) -> TrainingComponentRegistration:
    """构造仅含导入字符串的轻量注册项。"""
    return TrainingComponentRegistration(key, ImportStringFactory(factory_path))


def build_training_strategy_registry() -> TrainingStrategyRegistry:
    """构造 single-GPU、DDP 和一个 DeepSpeed 策略注册表。"""
    registry = TrainingStrategyRegistry("autovla-training-strategies")
    registry.register(
        "single_gpu",
        _entry("single_gpu", "autovla.training.strategy:SingleGpuStrategy"),
        aliases=("single_device",),
    )
    registry.register(
        "distributed_data_parallel",
        _entry(
            "distributed_data_parallel",
            "autovla.training.strategy:DistributedDataParallelStrategy",
        ),
        aliases=("ddp",),
    )
    registry.register(
        "deepspeed",
        _entry("deepspeed", "autovla.training.strategy:DeepSpeedStrategy"),
    )
    return registry


def build_optimizer_registry() -> OptimizerRegistry:
    """构造显式 AdamW 优化器注册表。"""
    registry = OptimizerRegistry("autovla-optimizers")
    registry.register("adamw", _entry("adamw", "autovla.training.optimization:create_adamw"))
    return registry


def build_scheduler_registry() -> LearningRateSchedulerRegistry:
    """构造常量与余弦共用的调度器工厂注册表。"""
    registry = LearningRateSchedulerRegistry("autovla-learning-rate-schedulers")
    factory = _entry("scheduler", "autovla.training.optimization:create_scheduler")
    registry.register("constant", factory)
    registry.register("cosine", factory)
    return registry


def build_callback_registry() -> CallbackRegistry:
    """构造日志与进度 callback 注册表。"""
    registry = CallbackRegistry("autovla-training-callbacks")
    registry.register(
        "logging",
        _entry("logging", "autovla.training.callbacks:LoggingCallback"),
    )
    registry.register(
        "progress",
        _entry("progress", "autovla.training.callbacks:ProgressCallback"),
    )
    return registry


TrainingStrategyFactory = ImportStringFactory[object]
OptimizerFactory = ImportStringFactory[object]
LearningRateSchedulerFactory = ImportStringFactory[object]
CallbackFactory = ImportStringFactory[object]


class _TestingRegistryModule(Protocol):
    """描述测试注册表的懒兼容工厂。"""

    def create_batch_adapter(
        self, key: str, *, action_horizon: int, action_dim: int
    ) -> BatchAdapter: ...

    def create_checkpoint_adapter(self, key: str) -> CheckpointAdapter: ...

    def create_action_policy(self, key: str, *, seed: int) -> ActionPolicy: ...

    def create_loss_adapter(self, key: str) -> LossAdapter: ...


def _testing_registry() -> _TestingRegistryModule:
    """仅在历史 test-double 工厂被调用时导入测试注册表。"""
    return cast(
        _TestingRegistryModule,
        import_module("autovla.testing.training.registry"),
    )


def create_batch_adapter(key: str, *, action_horizon: int, action_dim: int) -> BatchAdapter:
    """懒委托历史 BatchAdapter 工厂并保留公开位置。"""
    return _testing_registry().create_batch_adapter(
        key,
        action_horizon=action_horizon,
        action_dim=action_dim,
    )


def create_checkpoint_adapter(key: str) -> CheckpointAdapter:
    """懒委托历史 CheckpointAdapter 工厂并保留公开位置。"""
    return _testing_registry().create_checkpoint_adapter(key)


def create_action_policy(key: str, *, seed: int) -> ActionPolicy:
    """懒委托历史 ActionPolicy 工厂。"""
    return _testing_registry().create_action_policy(key, seed=seed)


def create_loss_adapter(key: str) -> LossAdapter:
    """懒委托历史 LossAdapter 工厂。"""
    return _testing_registry().create_loss_adapter(key)


__all__ = [
    "CallbackFactory",
    "CallbackRegistry",
    "LearningRateSchedulerFactory",
    "LearningRateSchedulerRegistry",
    "OptimizerFactory",
    "OptimizerRegistry",
    "TrainingComponentRegistration",
    "TrainingStrategyFactory",
    "TrainingStrategyRegistry",
    "build_callback_registry",
    "build_optimizer_registry",
    "build_scheduler_registry",
    "build_training_strategy_registry",
    "create_action_policy",
    "create_batch_adapter",
    "create_checkpoint_adapter",
    "create_loss_adapter",
]
