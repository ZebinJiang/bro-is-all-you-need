---
description: Load these instructions when tasks depend on Python environment, optional extras, GPU, Slurm, datasets, or runtime-specific conditions.
---

# Environment and Runtime Instructions

## Environment

- Use the active environment unless the task requires a change.
- Do not assume optional extras, developer tools, external services, GPU, Slurm, or network access are available.
- Check environment-dependent requirements before running related validation.

## StarVLA repository layout

- Do not assume a template-owned `src/` directory.
- Inspect the actual StarVLA engineering-base layout before choosing source locations.
- Avoid creating duplicate source paths that compete with the upstream layout.

## GPU and Slurm

- Treat CUDA/NVML/GPU detection failures as environment-access issues first, not immediate proof of a code bug.
- Login nodes may run only lightweight checks. Real debug, tests, evaluation, training, inference, dataset conversion, and other compute-heavy work should use compute-node allocation or formal Slurm jobs.
- If Slurm config has `TO_FILL`, run environment discovery before formal submission.
- Use project Slurm helpers/wrappers for formal project jobs and compute-node debug allocation.
- If validation is blocked by environment, state what ran, what was unavailable, and the remaining risk.
