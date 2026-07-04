"""训练 runner dry-run 的轻量循环入口。"""

from __future__ import annotations

from autovla.training.runner import DryRunConfig, DryRunResult, run_training_dry_run


def run_cpu_dryrun_loop(config: DryRunConfig) -> DryRunResult:
    """执行 CPU-only dry-run loop, 作为后续真实 runner 的窄入口。"""
    return run_training_dry_run(config)
