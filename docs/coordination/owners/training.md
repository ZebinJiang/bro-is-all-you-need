# 20-OWNER · Training

## Authority

Training Owner owns runner systems, checkpoint management, optimizer and scheduler lifecycle, distributed training integration, resume semantics, and training/evaluation loop contracts.

## Primary write scope

- `genesisvla/training/**`
- `tests/training/**`
- training-related docs and examples
- `coordination/reports/**` for assigned training reports

## Review duties

Training Owner reviews changes that affect `BaseRunner`, `FSDPRunner`, `DDPRunner`, `DeepSpeedRunner`, checkpoint manifests, resume behavior, optimizer state, scheduler state, RNG state, and training metrics.

## Required report fields

Every Training Owner report must include runner lifecycle impact, checkpoint/resume impact, distributed behavior, required commands, skipped GPU/Slurm evidence, and rollback notes.
