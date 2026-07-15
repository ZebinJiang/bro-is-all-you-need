# Owner Compute-RO1 Report

Task: AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001
Owner role: 80-OWNER · Compute/HPC
Wave: 1 Compute-RO1
Runtime override: model=gpt-5.5, thinking=high
Thinking xhigh used: no
Thinking max used: no

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- Required branch: matched.
- Required dispatch HEAD: matched.
- PR #30 state was not mutated.

Only lightweight local inspection was performed. No `srun`, `sbatch`, compute job, test suite, source-dataset benchmark, dependency install, or PR/git mutation was run.

## Governance And Inputs Read

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- Prior PR30 Compute reports:
  - `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-compute-w1r.md`
  - `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-compute-r1.md`
- Current runner/source surface:
  - `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
  - Slurm wrapper/config evidence under `scripts/slurm/request_compute_debug.sh`, `configs/slurm/debug_profiles.json`, and `configs/slurm/default_sandbox.json`

## Current Code Readiness

Current code requires Data fixes before the final compute benchmark should run.

Findings:

- The current runner still exposes the previous candidate matrix labels/ids: old `D1`, `D2`, `D3`, `D4`, `D5`, `D6`.
- The task requires final candidates `D1a`, `D1b`, `D3`, `D4`, `D5`, `D6`.
- Current code has no `D1a`/`D1b` candidate labels/ids.
- Current code still emits defaulted core timing fields for many prompt-contract metrics.
- Current code does support matrix CLI flags needed after Data fixes: `--worker-counts`, `--batch-sizes`, `--warmup-batches`, `--measured-batches`, `--repeats`, `--max-episodes`, `--max-samples`, `--candidates`, and `--gr00t-root`.
- The source dataset path exists.
- Project-local Python exists.

Therefore Compute should not run Wave 4 final benchmark until Data supplies final candidate ids/routes and fixes or explicitly fail-closes the final metrics contract.

## Recommended Wrapper Route

Use the project wrapper, not raw `srun`:

```bash
scripts/slurm/request_compute_debug.sh \
  --profile h800-gpu \
  --partition a100 \
  --cpus 16 \
  --mem 128G \
  --gres none \
  --time 04:00:00 \
  --run-id autovla-m3-pr30-final-dataloader-perf-w4 \
  -- bash -lc 'bash runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/run_final_dataloader_perf_inside_compute.sh'
```

Rationale:

- Prior W1R route successfully used the same wrapper shape with `partition=a100`, `cpus=16`, `mem=64G`, `gres=none`, `time=01:00:00`.
- Final matrix is larger and should request a longer allocation and more memory, subject to scheduler policy.
- `gres=none` and `CUDA_VISIBLE_DEVICES=""` preserve no-GPU/no-CUDA execution.

Scheduler-policy risk:

- `a100` with `gres=none` has prior successful evidence, but longer time or higher memory may be rejected.
- If rejected, record exact scheduler output and stop; do not bypass policy or retry with broader resources without Manager authorization.

## Planned Benchmark Matrix

Primary matrix after Data fixes:

- Candidates: `D1a`, `D1b`, `D3`, `D4`, `D5`, `D6` using exact Data-supplied CLI candidate ids.
- `worker_count=8`
- `batch_size=8`
- `warmup=10`
- `measured=100`
- `repeats=3`
- `max_samples=4096`
- `max_episodes=32`

Fallback matrix only with explicit approval after resource/time risk:

- `worker_count=8`
- `batch_size=8`
- `warmup=5`
- `measured=50`
- `repeats=2`
- `max_samples=2048`
- `max_episodes=16`

Secondary worker sweep after primary if allocation budget remains:

- `worker_count=0,2,4,8`
- `batch_size=8`
- recommended reduced matrix: `warmup=5`, `measured=50`, `repeats=2`, `max_samples=2048`, `max_episodes=16`

If the primary run consumes most of the allocation, skip secondary sweep and record the skip instead of risking timeout.

## Required Evidence

Wave 4 should record:

- wrapper `srun_command.txt`;
- task-local launch and inside-compute scripts;
- stdout/stderr logs copied or teed under task-local `compute/`;
- status file with exact exit code for every CLI invocation;
- `environment.json` with hostname/node, cwd, git HEAD, Python version, source dataset, working root, output root, matrix, and guard envs;
- `job_metadata.json` with scheduler job id if emitted, otherwise explicit `job_id_not_emitted_by_wrapper`;
- raw per-batch timing files;
- aggregate summaries;
- generated artifact ledger;
- source dataset mutation proof;
- command log index;
- generated output file list.

Do not claim a job id unless the wrapper or scheduler output actually exposes it.

## Stop Conditions

Stop as `BLOCKED_DEPENDENCY_OR_EXECUTION`, `BLOCKED_COMPUTE_ENV`, or `BLOCKED_SCOPE` as appropriate if:

- Data fixes are missing or final D1a/D1b candidate ids are absent.
- D1a/D1b require model/checkpoint/tokenizer/HF/W&B/endpoint/robot/training behavior.
- Source dataset path is missing or any command attempts to mutate `datasets/readonly/**`.
- Generated artifacts would be staged/committed.
- Project wrapper is unavailable.
- Scheduler rejects the route or resource request.
- A retry would require raw unmanaged `srun`/`sbatch` or scheduler-policy bypass.
- Runner cannot emit raw per-batch timing, generated artifact ledger, source mutation proof, or command log index.
- Login-node full benchmark would be the only route.

## External-Effect Compliance

- DevSpace MCP used: no.
- Subagents used: none.
- Subagent retirement ledger: none required; no subagents were created.
- Compute jobs run: no.
- Slurm submitted: no.
- GPU/CUDA/GPU200/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not run.
- Source/tests/docs/config/dependency edits: no.
- Git stage/commit/push/PR mutation: no.

## Report Artifacts

- Plan: `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/compute-benchmark-plan.md`
- Owner report: `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-ro1.md`

## Conclusion

APPROVE_COMPUTE_PLAN_AFTER_DATA_FIXES

The compute-node execution plan is ready, but current code should not be executed for the final benchmark until Data fixes the final candidate matrix and metrics contract.
