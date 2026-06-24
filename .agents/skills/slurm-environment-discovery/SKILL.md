---
name: slurm-environment-discovery
description: Discover and fill Slurm cluster/partition config when active config contains TO_FILL.
---

Use this skill when `configs/slurm/default_sandbox.json` or another active Slurm config contains `TO_FILL` for cluster identity or partition.

## Required workflow

1. Run Slurm discovery on the target cluster using `scripts/slurm/discover_slurm_environment.py`.
2. Collect partition/node inventory and cluster identity.
3. Fill the active config only if it still contains `TO_FILL`.
4. Record the discovery run id and inventory path in `docs/progress.txt`.
5. Do not update an already-filled config unless the user explicitly requests refresh.

## Allowed commands

- `sinfo`;
- `scontrol show config`;
- `scontrol show partition`;
- `sbatch --version`;
- `srun --version`.

## Hard limits

- Do not modify Slurm cluster policy.
- Do not inspect private user job details.
- Do not cancel, requeue, or reprioritize jobs.
- Do not bypass cgroups/resource/accounting limits.
