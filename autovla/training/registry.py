"""AutoVLA 生产训练组件的轻量懒注册表。"""

from __future__ import annotations

from dataclasses import dataclass

from autovla.core.registry import ComponentRegistry, ImportStringFactory


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
    """构造 SingleDevice、DDP 和 FSDP2 策略注册表。"""
    registry = TrainingStrategyRegistry("autovla-training-strategies")
    registry.register(
        "single_device",
        _entry("single_device", "autovla.training.strategy:SingleDeviceStrategy"),
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
        "fully_sharded_data_parallel",
        _entry(
            "fully_sharded_data_parallel",
            "autovla.training.strategy:FullyShardedDataParallelStrategy",
        ),
        aliases=("fsdp2",),
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
]
