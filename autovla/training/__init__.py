"""AutoVLA M3 训练 smoke 公共入口。"""

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

__all__ = [
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
