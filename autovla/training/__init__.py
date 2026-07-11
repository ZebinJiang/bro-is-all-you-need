"""AutoVLA M5 生产接口及弃用兼容/测试名称的轻量懒导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

_EXPORTS = {
    "ActionPolicy": "autovla.training.contracts",
    "BatchAdapter": "autovla.training.contracts",
    "CallbackRegistry": "autovla.training.registry",
    "CheckpointAdapter": "autovla.training.contracts",
    "CheckpointCompatibilitySpec": "autovla.training.checkpointing",
    "CheckpointManifest": "autovla.training.checkpoint",
    "CheckpointManager": "autovla.training.checkpointing",
    "DeterministicActionFramework": "autovla.training.testing",
    "EfficiencyTelemetry": "autovla.training.efficiency",
    "EnvProfile": "autovla.training.runtime",
    "LearningRateSchedulerRegistry": "autovla.training.registry",
    "LocalRunner": "autovla.training.local_runner",
    "LocalRunnerConfig": "autovla.training.local_runner",
    "LocalRunnerState": "autovla.training.local_runner",
    "LossAdapter": "autovla.training.contracts",
    "MaskedActionLoss": "autovla.training.losses",
    "MetricLogger": "autovla.training.telemetry.logger",
    "ModularDryRunResult": "autovla.training.runner",
    "OptimizerRegistry": "autovla.training.registry",
    "PrecisionPolicy": "autovla.training.precision",
    "ResumeSpec": "autovla.training.checkpoint",
    "RuntimePlan": "autovla.training.runtime",
    "TrainablePolicy": "autovla.training.contracts",
    "TrainingBatch": "autovla.core.types.training",
    "TrainingCallback": "autovla.training.callbacks",
    "TrainingCheckpointManifest": "autovla.training.checkpointing",
    "TrainingContext": "autovla.training.context",
    "TrainingEngine": "autovla.training.engine",
    "TrainingState": "autovla.training.state",
    "TrainingStepOutput": "autovla.training.step",
    "TrainingStrategy": "autovla.training.strategy",
    "TrainingStrategyRegistry": "autovla.training.registry",
    "build_callback_registry": "autovla.training.registry",
    "build_optimizer_registry": "autovla.training.registry",
    "build_scheduler_registry": "autovla.training.registry",
    "build_tiny_training_batch": "autovla.training.fixtures",
    "build_training_strategy_registry": "autovla.training.registry",
    "collated_batch_to_model_input": "autovla.training.adapter",
    "masked_action_mse": "autovla.training.losses",
    "read_checkpoint_manifest": "autovla.training.checkpoint",
    "run_modular_training_dry_run": "autovla.training.runner",
    "validate_action_mask": "autovla.training.losses",
    "write_backend_parity_evidence": "autovla.training.runner",
    "write_checkpoint_manifest": "autovla.training.checkpoint",
}

__all__: list[str] = []
if not TYPE_CHECKING:
    __all__.extend(sorted(_EXPORTS))


def __getattr__(name: str) -> object:
    """按需解析生产或弃用兼容对象并避免包导入触发 torch。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共名称,其中部分仅为弃用兼容/测试入口。"""
    return sorted(set(globals()) | set(__all__))
