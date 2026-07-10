"""AutoVLA 训练公共接口的轻量懒加载导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from autovla.training.adapter import collated_batch_to_model_input
    from autovla.training.checkpoint import (
        CheckpointManifest,
        ResumeSpec,
        read_checkpoint_manifest,
        write_checkpoint_manifest,
    )
    from autovla.training.checkpointing import (
        CheckpointCompatibilitySpec,
        TrainingCheckpointManifest,
    )
    from autovla.training.contracts import (
        ActionPolicy,
        BatchAdapter,
        CheckpointAdapter,
        LossAdapter,
        TrainablePolicy,
        TrainingBatch,
    )
    from autovla.training.efficiency import EfficiencyTelemetry
    from autovla.training.fixtures import build_tiny_training_batch
    from autovla.training.local_runner import LocalRunner, LocalRunnerConfig, LocalRunnerState
    from autovla.training.losses import MaskedActionLoss, masked_action_mse, validate_action_mask
    from autovla.training.runner import (
        ModularDryRunResult,
        run_modular_training_dry_run,
        write_backend_parity_evidence,
    )
    from autovla.training.runtime import EnvProfile, RuntimePlan
    from autovla.training.testing import DeterministicActionFramework

_EXPORTS = {
    "ActionPolicy": "autovla.training.contracts",
    "BatchAdapter": "autovla.training.contracts",
    "CheckpointAdapter": "autovla.training.contracts",
    "CheckpointCompatibilitySpec": "autovla.training.checkpointing",
    "CheckpointManifest": "autovla.training.checkpoint",
    "DeterministicActionFramework": "autovla.training.testing",
    "EfficiencyTelemetry": "autovla.training.efficiency",
    "EnvProfile": "autovla.training.runtime",
    "LocalRunner": "autovla.training.local_runner",
    "LocalRunnerConfig": "autovla.training.local_runner",
    "LocalRunnerState": "autovla.training.local_runner",
    "LossAdapter": "autovla.training.contracts",
    "MaskedActionLoss": "autovla.training.losses",
    "ModularDryRunResult": "autovla.training.runner",
    "ResumeSpec": "autovla.training.checkpoint",
    "RuntimePlan": "autovla.training.runtime",
    "TrainablePolicy": "autovla.training.contracts",
    "TrainingBatch": "autovla.training.contracts",
    "TrainingCheckpointManifest": "autovla.training.checkpointing",
    "build_tiny_training_batch": "autovla.training.fixtures",
    "collated_batch_to_model_input": "autovla.training.adapter",
    "masked_action_mse": "autovla.training.losses",
    "read_checkpoint_manifest": "autovla.training.checkpoint",
    "run_modular_training_dry_run": "autovla.training.runner",
    "validate_action_mask": "autovla.training.losses",
    "write_backend_parity_evidence": "autovla.training.runner",
    "write_checkpoint_manifest": "autovla.training.checkpoint",
}

__all__ = [
    "ActionPolicy",
    "BatchAdapter",
    "CheckpointAdapter",
    "CheckpointCompatibilitySpec",
    "CheckpointManifest",
    "DeterministicActionFramework",
    "EfficiencyTelemetry",
    "EnvProfile",
    "LocalRunner",
    "LocalRunnerConfig",
    "LocalRunnerState",
    "LossAdapter",
    "MaskedActionLoss",
    "ModularDryRunResult",
    "ResumeSpec",
    "RuntimePlan",
    "TrainablePolicy",
    "TrainingBatch",
    "TrainingCheckpointManifest",
    "build_tiny_training_batch",
    "collated_batch_to_model_input",
    "masked_action_mse",
    "read_checkpoint_manifest",
    "run_modular_training_dry_run",
    "validate_action_mask",
    "write_backend_parity_evidence",
    "write_checkpoint_manifest",
]


def __getattr__(name: str) -> object:
    """按需解析训练公共导出并保持对象身份。"""
    module_name = _EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """返回稳定公共导出名称。"""
    return sorted(set(globals()) | set(__all__))
