# AutoVLA Modular Core Skeleton

## Implemented Path

The M4 composition root is `autovla.training.runner`. It resolves a strict
tracked config, creates typed components from `autovla.core.registry.Registry`,
opens one explicit data backend, emits canonical `TrainingBatch` values, adapts
them for the `test_double` family, computes deterministic predictions and
strict masked loss, records synthetic telemetry by stage, and writes a
metadata-only checkpoint manifest.

`TrainingBatch` is owned by `autovla.core.types.training` and is identity
re-exported from `autovla.training.contracts`. `RuntimePlan` and `EnvProfile`
are owned by `autovla.core.runtime` and identity re-exported from
`autovla.training.runtime`. `CollatedBatch` remains internal to Data.

## Runtime Boundary

The executable profile is `test_double`. `gr00t_n1d6_metadata`, `pi0_metadata`,
and `pi05_metadata` provide processor, backbone, action-head, normalization,
family, and license metadata without importing their heavy runtimes. Metadata
profiles reject execution.

This local dry-run performs no real training, gradients, model/checkpoint/
tokenizer load, HF/W&B/network call, GPU/Slurm work, endpoint access, robot
action, throughput measurement, or production-readiness validation.

## Backend Decision

The canonical keys are `webdataset_tar` and `robodm_container_v1`.
`robodm_style` is an explicit alias. Both are retained candidates and neither
is inferred or selected by path or benchmark result. Decision:
`NO_BACKEND_WINNER`.
