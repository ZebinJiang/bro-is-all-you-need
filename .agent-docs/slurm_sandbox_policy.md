# Slurm Sandbox Policy

## Purpose

This project is expected to run on a Slurm cluster. The sandbox policy allows real job submission but prevents unmanaged cluster usage, cluster-policy modification, accidental output sprawl, and interference with other users.

## Slurm configuration discovery

Active Slurm configs live under `configs/slurm/`. If the active config contains `TO_FILL` for `approved_cluster` or `partition`, the Manager must run node/partition discovery before any formal submission:

```bash
python3 -S scripts/slurm/discover_slurm_environment.py \
  --config configs/slurm/default_sandbox.json \
  --run-id slurm-discovery-<yyyymmddhhmmss> \
  --write-config
```

This discovery may read Slurm metadata through permitted commands such as `sinfo`, `scontrol`, `sbatch --version`, and `srun --version`. It must not modify cluster policy. Once a config is filled, the Manager reads it as the source of truth and must not update it again unless the user explicitly requests a refresh or replacement.

## Login-node and compute-node policy

Login nodes are resource-limited. They may be used only for lightweight repository checks, JSON validation, static checks, and command generation. Real debug, tests, evaluation, training, inference serving, dataset conversion, and other compute-heavy work must run on compute nodes.

For interactive compute-node debug, use the project helper:

```bash
scripts/slurm/request_compute_debug.sh \
  --profile h800-gpu \
  --run-id debug-<task-id>-<yyyymmddhhmmss> \
  --dry-run
```

After inspecting the command, remove `--dry-run` to request the allocation. The `h800-gpu` profile corresponds to the user-provided debug shape:

```bash
srun -p h800 -c 16 --mem=64G --gres=gpu:1 --time=01:00:00 --pty bash
```

Default debug resources are intentionally small: 1 CPU and 4G memory. Increase only when the task requires it.

## Required sequence

For Slurm-dependent tasks, the Manager must follow this sequence:

1. Run lightweight local/static validation for repository structure and command generation.
2. Ensure the active Slurm config is filled; if it contains `TO_FILL`, run environment discovery and fill it.
3. Run compute-node debug/test/evaluation through the project `srun` helper or a formal preflight job when relevant.
4. Run the Slurm wrapper with `--dry-run` and inspect the generated `sbatch` command.
5. Submit one or more formal Slurm jobs through `scripts/slurm/submit_sandbox_job.sh` on an approved cluster.
6. Record accepted job id(s), logs, outputs, metrics, and run manifests under `runs/slurm/<run_id>/`.
7. Review logs before setting `passes: true`.

## Allowed Slurm submission paths

Formal jobs use:

```bash
scripts/slurm/submit_sandbox_job.sh \
  --config configs/slurm/default_sandbox.json \
  --experiment-config configs/experiments/example_experiment.json \
  --job-script scripts/slurm/template_job.sbatch \
  --run-id <safe_run_id>
```

Interactive debug allocations use:

```bash
scripts/slurm/request_compute_debug.sh --profile <profile> --run-id <safe_run_id>
```

Use `--dry-run` before formal submission or allocation. Removing `--dry-run` is allowed after the Manager has inspected the generated command and local/static checks have passed.

## Wrapper versus raw Slurm commands

Manager and subagents must use project wrappers/helpers for Slurm work. This is required because the wrappers create run directories, set environment variables, route logs, record resources, and write reproducible command manifests.

For user convenience, each wrapper writes the equivalent raw `sbatch` or `srun` command into the run logs. A human user may manually reproduce a run from that logged command. Agents may not switch to raw `sbatch`, `srun`, or `scancel` unless the user explicitly authorizes a one-off exception and the exception is recorded.

## Disallowed cluster behavior

- Do not modify Slurm cluster config, partitions, QoS, accounting, modules, cgroups, prolog/epilog scripts, or scheduler policy.
- Do not cancel, reprioritize, requeue, inspect private details, or interfere with another user's jobs.
- Do not bypass Slurm scheduling, cgroups, GPU/CPU/memory limits, or site accounting.
- Do not run long unmanaged workloads on login nodes.
- Do not use raw `sbatch`, `srun`, or `scancel` for project work unless the user explicitly authorizes a one-off exception and the exception is recorded.
- Do not write outputs outside the project-local `runs/` tree unless explicitly authorized.

## Run directory contract

Each formal Slurm run must use:

```text
runs/slurm/<run_id>/
  logs/
  outputs/
  tmp/
  home/
```

Each compute-node debug allocation must record its command and manifest under:

```text
runs/slurm_debug/<run_id>/
  logs/
  outputs/
  tmp/
  home/
```

Run directories may contain small manifests or references to datasets. They must not contain full copied datasets unless explicitly justified and authorized.

## Required evidence

For a Slurm-dependent task to be accepted, record:

- Slurm config discovery evidence if the config was previously `TO_FILL`;
- compute-node debug/test evidence when relevant;
- wrapper dry-run output;
- formal submission command or submission manifest;
- Slurm job id(s);
- stdout/stderr logs;
- output manifest;
- metrics or validation result;
- failure analysis if the job failed;
- Manager review note in `.agent-docs/progress.txt`.
