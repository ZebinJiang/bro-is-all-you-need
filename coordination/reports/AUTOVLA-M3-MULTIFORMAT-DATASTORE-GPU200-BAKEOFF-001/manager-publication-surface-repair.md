# Manager Publication Surface Repair

Task: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`

## Runtime Override

- Follow-up Owner dispatch model: `gpt-5.5`
- Follow-up Owner dispatch thinking: `high`
- `thinking=max` used: no

## Repair Scope

This repair addresses final-review `REQUEST_CHANGES` findings only. It does not
change training behavior, datastore behavior, Slurm behavior, dependency
declarations, generated evidence, checkpoints, datasets, or runtime outputs.

Changed files:

- `coordination/PROGRAM_STATE.yaml`
- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`

## Repairs Applied

1. Restored `coordination_rules.active_model_label` to `gpt-5.5` so the task
   state matches the user's active dispatch override.
2. Replaced the benchmark dashboard's previous structured-output wording with
   a Wave 11 output-surface section that matches observed evidence:
   `bridge_runtime_result.json`, stdout/stderr logs, experiment configuration,
   processor artifacts, and task-local `checkpoint-200/**` runtime output.
3. Reframed `telemetry_*` tables/manifests as a future reporting contract, not
   as files emitted by Wave 11.

## Publication Decision

The linked dashboard
`docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md` remains intentionally
ignored by the broad docs ignore rule:

- `.gitignore:235:*/**/*.md`

For this task's publication, Manager will include this exact dashboard with a
narrow force-add pathspec during the final publication step:

```bash
git add -f -- docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md
```

No generated run outputs, logs, checkpoints, datasets, `runs/tmp/**`, or
`runs/slurm_debug/**` evidence will be staged to repair this issue.

## Local Checks

- `git diff --check`: PASS
- dashboard false structured-output claim scan: PASS
- `coordination/PROGRAM_STATE.yaml` active model label: `gpt-5.5`

## Rereview Request

Architecture, Product/Spec, Compute/HPC, Tooling, and Quality should rereview
only this narrow repair and the explicit force-add publication decision.
