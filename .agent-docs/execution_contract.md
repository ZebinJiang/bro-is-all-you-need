# Execution Contract

## Lightweight local execution

Local execution is limited to repository-structure checks, JSON validation, command generation, and tiny mock tasks. It must stay inside the repository and write generated outputs under `runs/local/<run_id>/`.

Use:

```bash
scripts/sandbox/run_local_sandbox.sh --run-id <run_id> -- <command> [args...]
```

Local smoke output is not acceptance evidence for real VLA training, evaluation, inference, serving, dataset conversion, robot behavior, or cluster-only behavior.

## Project-local temporary files

Ad-hoc Manager/subagent temporary files that are not part of a specific run must use:

```text
runs/tmp/
```

Run-specific temporary files remain under the run directory:

```text
runs/local/<run_id>/tmp/
runs/slurm/<run_id>/tmp/
runs/slurm_debug/<run_id>/tmp/
```

Do not write temporary files to the repository root. Avoid system `/tmp` except when a tool cannot be redirected, and record that exception if it matters. This temp policy is project-local execution hygiene, not an external transfer.

## Compute-node debug execution

Debug, tests, evaluation, training, inference serving, dataset conversion, and other compute-heavy work should run on Slurm compute nodes when they require real runtime resources.

Use:

```bash
scripts/slurm/request_compute_debug.sh --profile <profile> --run-id <run_id> [--dry-run]
```

The helper creates:

```text
runs/slurm_debug/<run_id>/logs/
runs/slurm_debug/<run_id>/outputs/
runs/slurm_debug/<run_id>/tmp/
runs/slurm_debug/<run_id>/home/
```

## Formal Slurm execution

Slurm execution must use:

```bash
scripts/slurm/submit_sandbox_job.sh --config <slurm_config> --experiment-config <experiment_config> --job-script <script> --run-id <run_id>
```

The wrapper creates:

```text
runs/slurm/<run_id>/logs/
runs/slurm/<run_id>/outputs/
runs/slurm/<run_id>/tmp/
runs/slurm/<run_id>/home/
```

## Slurm config discovery execution

If an active Slurm config contains `TO_FILL`, run:

```bash
python3 -S scripts/slurm/discover_slurm_environment.py --config <slurm_config> --run-id <run_id> --write-config
```

Discovery outputs go under:

```text
runs/slurm_inventory/<run_id>/
```

## External path transfer execution

For user-authorized one-time external transfers, use:

```bash
scripts/data/transfer_explicit_path.sh --run-id <run_id> --direction <inbound|outbound> --source <path> --destination <path> --dry-run
```

Use `--execute` only after user authorization and Manager audit.

## Run-id contract

Run ids must match:

```text
[A-Za-z0-9._-]+
```

Recommended format:

```text
vla-fw-<task-id>-<mode>-<yyyymmddhhmmss>
```

## Output contract

Outputs must include at least one small manifest or result file under the run directory. Dataset references should be stored as paths/checksums/manifests, not copied datasets.
