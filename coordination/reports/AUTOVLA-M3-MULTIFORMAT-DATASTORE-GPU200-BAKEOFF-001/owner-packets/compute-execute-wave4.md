# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Compute/HPC Execute Wave 4 Packet

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

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave4.md`
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
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave3.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/COMPUTE_EXECUTION_STATE.yaml`
- `scripts/slurm/request_compute_debug.sh`
- `configs/slurm/debug_profiles.json`
- `configs/slurm/default_sandbox.json`

## Manager resolution of the Wave 3 hard stop

Wave 3 proved:

1. dry-run preflight: `PASS`
2. real `a100`, `gpu:1`, `01:00:00` preflight: `PASS`
3. the bridge is compute-executable when runtime uses:
   - `python_executable=/home/cz-jzb/workspace/Isaac-GR00T17/.venv/bin/python`
   - `PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17`
4. the preferred store-benchmark envelope failed before launch only because:
   - requested time was `06:00:00`
   - scheduler rejection was `QOSMaxWallDurationPerJobLimit`

This wave explicitly authorizes a narrower replacement envelope after that hard stop.

Do not treat the Wave 3 scheduler rejection as permission to broaden resources or bypass policy.

## Objective of this wave

Continue the same governed compute execution with a scheduler-compatible narrow route:

1. run the real multi-format store benchmark under a narrower envelope;
2. derive the runnable candidate set from produced outputs;
3. run the minimum telemetry matrix required by the top-level task if full four-candidate telemetry is not practical under current scheduler limits;
4. record exact job ids/logs/output roots/status rows/blockers without touching source.

## Narrow-envelope authorization for this wave

### Store benchmark

You are authorized to rerun the real store benchmark with all four required candidates using this narrower bounded envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `none`
- time: `01:00:00`

Use project wrapper only:

- `scripts/slurm/request_compute_debug.sh`

Do not run raw `srun` or `sbatch`.

### Fairness selection reduction

The top-level task already authorizes one bounded reduction if compute proves the default selection too large.

For this wave, use the reduced fairness selection:

- `max_episodes: 16`
- `max_samples: 2048`
- `batch_size: 8`
- `worker_count: 8`
- `repeats: 3`
- `seed: 11`

Do not reduce further.
Do not invent alternative sample-selection values.

### 1-GPU telemetry

If the reduced store benchmark completes and yields runnable candidates, you are authorized to run the minimum telemetry matrix required by the top-level task under this bounded envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `gpu:1`
- time: `01:00:00`
- steps: exactly `200`

Minimum telemetry matrix in this wave if full four-candidate telemetry is not practical:

1. `zjh_lerobot_v21_raw` baseline
2. best load-benchmark candidate
3. second-best candidate only if within 10 percent of best on samples/sec or p95 latency

If a candidate is not run, write an exact `NOT_RUN_*` reason row.

Do not launch optional 2-GPU communication jobs in this wave.

## Required execution order

### Phase A — Reuse Wave 3 preflight evidence

Do not rerun the successful Wave 3 preflight unless a required path disappeared.

You may reuse Wave 3 evidence for:

- bridge/runtime viability
- Isaac `.venv` viability
- `a100` `gpu:1` `01:00:00` real preflight viability

If any required preflight file/path is now missing, stop with exact blocker.

### Phase B — Real reduced store benchmark

Run the real benchmark through the actual benchmark entrypoint already implemented by Data.

Preserve top-level semantics:

- compare all four candidates
- use the shared fairness manifest semantics
- record blocked rows when needed
- write task-owned evidence only

You may adapt the invoked CLI/module to the actual implemented source surface, but preserve the task semantics exactly.

Required outputs if launch succeeds:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/**`
- candidate rows with exact numeric values or exact blocked status
- runnable candidate set

If scheduler policy rejects even this narrower envelope, stop immediately and report the exact policy/error.

### Phase C — Minimum 1-GPU telemetry matrix

Only after Phase B completes.

Use the Training wave-3 bridge surface exactly as implemented.

Run:

1. `zjh_lerobot_v21_raw`
2. best benchmark candidate
3. second-best candidate only if within 10 percent threshold

If a candidate runtime fails before completion, record exact blocker/status row and continue only if packet-faithful and safe.

Do not claim a winner unless the top-level decision rule is satisfied.

### Phase D — Evidence and blocker accounting

Your report must explicitly separate:

- what is now numerically completed;
- what remains blocked by scheduler policy;
- what remains blocked by runtime compatibility;
- what telemetry rows are real vs not-run rows.

## Report requirements

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave4.md`

Include:

1. workspace verification
2. reused Wave 3 evidence
3. exact reduced benchmark wrapper command and envelope
4. whether reduced benchmark launched
5. benchmark output root
6. candidate statuses and runnable set
7. exact telemetry jobs attempted
8. exact telemetry rows completed vs not run
9. exact scheduler/runtime blockers if any
10. job ids or explicit `unknown_debug_wrapper_no_job_id`
11. DevSpace MCP compliance
12. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_COMPUTE_ENV`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- scheduler rejection or wrapper route insufficiency after this narrower authorized retry:
  - `BLOCKED_COMPUTE_ENV`
- packet-faithful execution completed with numeric benchmark and minimum telemetry evidence:
  - `PASS`
- any need to widen resources, mutate source, or improvise raw scheduler commands:
  - `BLOCKED_SCOPE`
