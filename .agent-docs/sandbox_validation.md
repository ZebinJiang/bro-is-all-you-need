# Sandbox Validation

## Lightweight local baseline commands

```bash
bash scripts/init.sh
bash scripts/smoke_test.sh
```

These validate the sandbox structure, required files, JSON configs, local wrapper behavior, Slurm dry-run generation, and compute-debug dry-run generation.

They are not acceptance evidence for real VLA training, evaluation, inference, serving, dataset conversion, robot behavior, or cluster-only behavior.

## Slurm config discovery validation

If a Slurm config contains `TO_FILL`, run discovery on the target Slurm environment:

```bash
python3 -S scripts/slurm/discover_slurm_environment.py --config configs/slurm/default_sandbox.json --run-id slurm-discovery-<timestamp> --write-config
```

Record the inventory path and resulting config in `.agent-docs/progress.txt`.

## Compute-node debug validation

Use compute nodes for real debug, tests, evaluation, training, inference serving, dataset conversion, and other compute-heavy work when runtime resources are required:

```bash
scripts/slurm/request_compute_debug.sh --profile h800-gpu --run-id debug-<task-id>-<timestamp> --dry-run
```

After dry-run review, remove `--dry-run` to request the allocation.

## Real task validation

A real VLA task must add task-specific validation. Examples:

- unit tests for changed modules;
- integration tests for baseline and experimental paths;
- shape/memory checks for neural-network changes;
- dataset manifest and conversion checks;
- tokenizer and action-head compatibility checks;
- inference latency/throughput checks;
- compute-node debug/test evidence;
- Slurm dry-run;
- formal Slurm submission;
- log/output review.

## Acceptance boundary

Local smoke test is not acceptance evidence for cluster-only behavior. Slurm-dependent work needs formal submitted job evidence.
