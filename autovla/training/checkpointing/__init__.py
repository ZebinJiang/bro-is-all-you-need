"""生产 checkpoint 包及 M4 只读兼容导出。"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from autovla.training.checkpointing.compatibility_m4 import (
    CheckpointCompatibilitySpec,
    TrainingCheckpointManifest,
)
from autovla.training.checkpointing.identity import (
    checkpoint_compatibility_fingerprint,
    checkpoint_compatibility_projection,
)
from autovla.training.checkpointing.manifest import (
    DATA_STATE_SCHEMA,
    LEGACY_PRODUCTION_CHECKPOINT_SCHEMAS,
    PRODUCTION_CHECKPOINT_SCHEMA,
    RANK_RUNTIME_STATE_SCHEMA,
    ProductionCheckpointManifest,
)

if TYPE_CHECKING:
    from autovla.training.checkpointing.manager import CheckpointManager

__all__ = [
    "DATA_STATE_SCHEMA",
    "LEGACY_PRODUCTION_CHECKPOINT_SCHEMAS",
    "PRODUCTION_CHECKPOINT_SCHEMA",
    "RANK_RUNTIME_STATE_SCHEMA",
    "CheckpointCompatibilitySpec",
    "CheckpointManager",
    "ProductionCheckpointManifest",
    "TrainingCheckpointManifest",
    "checkpoint_compatibility_fingerprint",
    "checkpoint_compatibility_projection",
]


def __getattr__(name: str) -> object:
    """仅在请求生产 manager 时导入 Torch 依赖。"""

    if name != "CheckpointManager":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module("autovla.training.checkpointing.manager"), name)
    globals()[name] = value
    return value
