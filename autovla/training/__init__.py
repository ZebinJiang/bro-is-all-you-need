"""AutoVLA M3 训练 smoke 公共入口。"""

from autovla.training.adapter import collated_batch_to_model_input
from autovla.training.checkpoint import (
    CheckpointManifest,
    ResumeSpec,
    read_checkpoint_manifest,
    write_checkpoint_manifest,
)
from autovla.training.local_runner import LocalRunner, LocalRunnerConfig, LocalRunnerState
from autovla.training.losses import MaskedActionLoss, masked_action_mse, validate_action_mask
from autovla.training.testing import DeterministicActionFramework

__all__ = [
    "CheckpointManifest",
    "DeterministicActionFramework",
    "LocalRunner",
    "LocalRunnerConfig",
    "LocalRunnerState",
    "MaskedActionLoss",
    "ResumeSpec",
    "collated_batch_to_model_input",
    "masked_action_mse",
    "read_checkpoint_manifest",
    "validate_action_mask",
    "write_checkpoint_manifest",
]
