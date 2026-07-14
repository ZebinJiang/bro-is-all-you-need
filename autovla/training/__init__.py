"""AutoVLA M5 生产接口及弃用兼容/测试名称的轻量懒导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.core.types.training import TrainingBatch as TrainingBatch
    from autovla.training.adapter import (
        collated_batch_to_model_input as collated_batch_to_model_input,
    )
    from autovla.training.callbacks import TrainingCallback as TrainingCallback
    from autovla.training.checkpoint import CheckpointManifest as CheckpointManifest
    from autovla.training.checkpoint import ResumeSpec as ResumeSpec
    from autovla.training.checkpoint import (
        read_checkpoint_manifest as read_checkpoint_manifest,
    )
    from autovla.training.checkpoint import (
        write_checkpoint_manifest as write_checkpoint_manifest,
    )
    from autovla.training.checkpointing import (
        CheckpointCompatibilitySpec as CheckpointCompatibilitySpec,
    )
    from autovla.training.checkpointing import CheckpointManager as CheckpointManager
    from autovla.training.checkpointing import (
        TrainingCheckpointManifest as TrainingCheckpointManifest,
    )
    from autovla.training.context import TrainingContext as TrainingContext
    from autovla.training.contracts import ActionPolicy as ActionPolicy
    from autovla.training.contracts import BatchAdapter as BatchAdapter
    from autovla.training.contracts import CheckpointAdapter as CheckpointAdapter
    from autovla.training.contracts import LossAdapter as LossAdapter
    from autovla.training.contracts import TrainablePolicy as TrainablePolicy
    from autovla.training.efficiency import EfficiencyTelemetry as EfficiencyTelemetry
    from autovla.training.engine import TrainingEngine as TrainingEngine
    from autovla.training.fixtures import build_tiny_training_batch as build_tiny_training_batch
    from autovla.training.local_runner import LocalRunner as LocalRunner
    from autovla.training.local_runner import LocalRunnerConfig as LocalRunnerConfig
    from autovla.training.local_runner import LocalRunnerState as LocalRunnerState
    from autovla.training.losses import MaskedActionLoss as MaskedActionLoss
    from autovla.training.losses import masked_action_mse as masked_action_mse
    from autovla.training.losses import validate_action_mask as validate_action_mask
    from autovla.training.precision import PrecisionPolicy as PrecisionPolicy
    from autovla.training.registry import CallbackRegistry as CallbackRegistry
    from autovla.training.registry import (
        LearningRateSchedulerRegistry as LearningRateSchedulerRegistry,
    )
    from autovla.training.registry import OptimizerRegistry as OptimizerRegistry
    from autovla.training.registry import (
        TrainingStrategyRegistry as TrainingStrategyRegistry,
    )
    from autovla.training.registry import build_callback_registry as build_callback_registry
    from autovla.training.registry import build_optimizer_registry as build_optimizer_registry
    from autovla.training.registry import build_scheduler_registry as build_scheduler_registry
    from autovla.training.registry import (
        build_training_strategy_registry as build_training_strategy_registry,
    )
    from autovla.training.runner import ModularDryRunResult as ModularDryRunResult
    from autovla.training.runner import (
        run_modular_training_dry_run as run_modular_training_dry_run,
    )
    from autovla.training.runner import (
        write_backend_parity_evidence as write_backend_parity_evidence,
    )
    from autovla.training.runtime import EnvProfile as EnvProfile
    from autovla.training.runtime import RuntimePlan as RuntimePlan
    from autovla.training.state import TrainingState as TrainingState
    from autovla.training.step import TrainingStepOutput as TrainingStepOutput
    from autovla.training.strategy import TrainingStrategy as TrainingStrategy
    from autovla.training.telemetry.logger import MetricLogger as MetricLogger
    from autovla.training.testing import (
        DeterministicActionFramework as DeterministicActionFramework,
    )

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
