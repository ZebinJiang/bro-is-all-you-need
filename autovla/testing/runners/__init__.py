"""集中导出测试与基准专用运行器。"""

from autovla.testing.runners.local_runner import LocalRunner, LocalRunnerConfig, LocalRunnerState
from autovla.testing.runners.runner import (
    DryRunConfig,
    DryRunResult,
    ModularDryRunResult,
    run_modular_training_dry_run,
    run_training_dry_run,
    write_backend_parity_evidence,
)

__all__ = [
    "DryRunConfig",
    "DryRunResult",
    "LocalRunner",
    "LocalRunnerConfig",
    "LocalRunnerState",
    "ModularDryRunResult",
    "run_modular_training_dry_run",
    "run_training_dry_run",
    "write_backend_parity_evidence",
]
