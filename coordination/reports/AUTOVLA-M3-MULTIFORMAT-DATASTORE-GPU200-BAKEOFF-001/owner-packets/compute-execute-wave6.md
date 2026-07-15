# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Compute/HPC Execute Wave 6 Packet

## Role

You are `80-OWNER · Compute/HPC`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Do not create child write-capable subagents.
No parallel write.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`

Before acting, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

## Allowed write scope

No source/code/test/config/docs writes in this wave.

You may write only:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave6.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/**`
- `runs/slurm/autovla-m3-multiformat-store-benchmark/**`
- `runs/slurm/autovla-m3-multiformat-gpu200-*/**`
- `runs/slurm_debug/autovla-m3-multiformat-*/**`

Do not write:

- `autovla/**`
- `tests/**`
- `configs/**`
- `scripts/**`
- `README.md`
- `docs/**`
- `datasets/readonly/**`
- `datasets/working/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

Read-only external exception allowed:

- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

## Required prior evidence

Read before execution:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave4.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave5.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_runtime_failure.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/COMPUTE_EXECUTION_STATE.yaml`
- `scripts/slurm/request_compute_debug.sh`

## Manager gate update

Wave 6 starts from two accepted facts:

1. Wave 4 already proved the narrowed store-benchmark envelope launches successfully:
   - `a100`
   - `16 CPU`
   - `64G`
   - `gres=none`
   - `01:00:00`
2. Data Wave 5 is `PASS` and repaired the exact runtime blocker by teaching
   `_build_source_sample(...)` to accept real mapping-shaped camera refs with a
   non-empty `path`.

Therefore this wave should not revisit the old scheduler question or the old
camera-ref contract mismatch unless evidence proves they regressed.

## Objective of this wave

1. rerun the reduced real store benchmark after the Data Wave 5 repair;
2. if benchmark outputs are produced, derive the runnable candidate set;
3. run the minimum telemetry matrix required by the top-level task when full
   four-candidate telemetry is not practical;
4. record exact run ids, output roots, status rows, telemetry evidence, and any
   remaining blockers.

## Store benchmark route for this wave

Reuse the already-written task-local reduced config:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`

Reuse the same narrowed wrapper envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `none`
- time: `01:00:00`

Use project wrapper only:

- `scripts/slurm/request_compute_debug.sh`

Do not run raw `srun` or `sbatch`.

Suggested run id:

- `autovla-m3-multiformat-store-benchmark-wave6`

## Telemetry route for this wave

Only after the rerun benchmark completes and emits candidate outputs.

If full four-candidate telemetry is not practical, run the top-level minimum matrix:

1. `zjh_lerobot_v21_raw`
2. best load-benchmark candidate
3. second-best candidate only if within 10 percent of best on samples/sec or p95 latency

Use the existing Training wave-3 bridge surface exactly as implemented.

Bounded telemetry envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `gpu:1`
- time: `01:00:00`
- steps: exactly `200`

Do not run optional 2-GPU communication jobs in this wave.

## Required execution order

### Phase A — Benchmark rerun

Rerun the reduced benchmark after the Data repair.

Success criteria for Phase A:

- benchmark launch succeeds
- `store-benchmark/load-benchmark.json` is produced
- candidate rows exist with exact numeric values or exact blocked statuses
- runnable candidate set can be derived

If Phase A fails:

- stop immediately
- record the exact remaining blocker
- do not launch telemetry

### Phase B — Minimum telemetry matrix

Only after Phase A succeeds.

For each candidate actually attempted, record:

- run id
- whether job launched
- output root
- exact status

If a candidate is not run, emit an exact `NOT_RUN_*` reason row.

Do not claim a winner unless the top-level decision rule is satisfied.

## Report requirements

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave6.md`

Include:

1. workspace verification
2. exact rerun wrapper command and envelope
3. whether rerun benchmark launched and completed
4. benchmark output root and candidate rows
5. runnable candidate set
6. exact telemetry jobs attempted
7. telemetry rows completed vs not run
8. exact remaining blocker if any
9. job ids or explicit `unknown_debug_wrapper_no_job_id`
10. DevSpace MCP compliance
11. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_COMPUTE_ENV`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- benchmark rerun plus minimum telemetry evidence completed:
  - `PASS`
- scheduler/env/wrapper route blocks again:
  - `BLOCKED_COMPUTE_ENV`
- further progress would require new source changes or broader resources:
  - `BLOCKED_SCOPE`
