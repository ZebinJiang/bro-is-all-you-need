# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Data Execute Wave 12 Packet

Role: `30-OWNER · Data`

## Runtime Override

- Use model: `gpt-5.5`
- Use thinking: `high`
- Do not use DevSpace MCP.

## Workspace

- Worktree:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Expected branch:
  `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- Expected HEAD:
  `3573930421a2f9be66b222d602db680a77aadf3f`

Stop and report `BLOCKED_WORKSPACE` if workspace verification fails.

## Required Inputs

Read these before writing:

1. `AGENTS.md`
2. `boundaries.txt`
3. `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
4. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/manager-summary.md`
5. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave8.md`
6. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave11.md`
7. `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.json`
8. `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.csv`
9. `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.md`
10. `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
11. `docs/benchmarks/README.md`
12. `README.md`

## Objective

Synthesize the now-complete Wave 8 store benchmark and Wave 11 real bounded
GR00T GPU200 telemetry into the publication-facing benchmark surfaces.

This is a documentation/table synthesis wave, not a new benchmark run and not a
training implementation wave.

## Allowed Writes

- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- `docs/benchmarks/README.md`
- `README.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**` only for
  task-local derived table artifacts if needed
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave12.md`

## Forbidden Writes

- no source changes
- no test changes
- no config changes
- no Slurm wrapper changes
- no dependency changes
- no dataset source mutation
- no generated checkpoint/model artifact staging
- no commit, push, PR mutation, merge, or branch deletion
- no new compute runs
- no DevSpace MCP

## Required Synthesis

Update publication-facing text and tables so they honestly reflect:

1. All four mandatory candidates appear in a numeric load benchmark table.
2. The load benchmark numbers are sourced from
   `runs/tmp/.../store-benchmark/load-benchmark.*`.
3. Wave 11 real GR00T GPU200 telemetry is now available for:
   - `zjh_lerobot_v21_raw`
   - `zjh_lerobot_v3_local`
4. Wave 11 telemetry dispositions:
   - `zjh_lerobot_v21_raw`: `PASS_200_STEP_TELEMETRY`
   - `zjh_lerobot_v3_local`: `PASS_200_STEP_TELEMETRY`
   - `zjh_webdataset_tar`: `NOT_RUN_MINIMUM_MATRIX_SECOND_BEST_OUTSIDE_10_PERCENT`
   - `zjh_robodm_container_v1`: `NOT_RUN_MINIMUM_MATRIX_RANKED_BELOW_REQUIRED_SET`
5. Wave 11 measured telemetry values:
   - `zjh_lerobot_v21_raw`
     - `train_runtime`: `88.1449`
     - `train_steps_per_second`: `2.269`
     - `train_loss`: `1.128048825263977`
   - `zjh_lerobot_v3_local`
     - `train_runtime`: `88.8496`
     - `train_steps_per_second`: `2.251`
     - `train_loss`: `1.1281476402282715`
6. README/docs must not paste raw logs.
7. README/docs must not claim:
   - final backend winner
   - long training readiness
   - model-quality result
   - deployment readiness
   - W&B/HF/endpoint/robot behavior
8. README/docs should state that Wave 11 used bounded 200-step local/offline
   telemetry and `dataloader_num_workers: 0` to avoid the Wave 9
   multiprocessing socket-path blocker.

## Suggested Shape

- In `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`:
  - replace stale bridge-ready-only language with measured Wave 11 status
  - add or update a combined candidate table with load metrics and telemetry
    disposition
  - add a short evidence table with report paths/result paths
  - keep boundary/non-goal section explicit
- In `docs/benchmarks/README.md`:
  - update the active dashboard summary so it no longer says real measured
    telemetry is absent
- In root `README.md`:
  - update the current evidence bullet that still says the telemetry surface is
    `bridge_ready_unverified`
  - keep no-final-winner and no-real-training-authorization boundaries

## Validation

Run:

1. `git diff --check`
2. `git diff -- docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md docs/benchmarks/README.md README.md`
3. If you create task-local derived table files, list them and verify they are
   under `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/`.

Do not run compute. Do not run broad gates in this wave.

## Owner Report

Write:

`coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave12.md`

Include:

- workspace verification
- files modified
- data sources consumed
- table values published
- boundary statements preserved
- validation commands and results
- DevSpace MCP compliance
- subagent retirement ledger
- conclusion: `PASS`, `BLOCKED_WORKSPACE`, `BLOCKED_SCOPE`, `BLOCKED_VALIDATION`, or `FAIL`
