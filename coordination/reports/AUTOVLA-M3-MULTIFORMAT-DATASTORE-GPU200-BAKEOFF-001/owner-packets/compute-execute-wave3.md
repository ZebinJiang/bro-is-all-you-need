# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Compute/HPC Execute Wave 3 Packet

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

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave3.md`
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

## Start gate

Do not proceed into actual compute commands unless all of the following exist
in the worktree:

1. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`
   with conclusion `PASS`
2. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-feasibility-wave2.md`
   with conclusion `APPROVE_BOUNDARY`
3. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
   with conclusion `PASS`

If any are missing or conclude otherwise, stop and report the exact blocker.

## Governing reports to read before execution

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-plan.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-feasibility-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-feasibility-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-bridge-plan-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/COMPUTE_EXECUTION_STATE.yaml`
- `scripts/slurm/request_compute_debug.sh`
- `configs/slurm/debug_profiles.json`
- `configs/slurm/default_sandbox.json`

## Objective of this wave

This is the first real compute execution wave for the bakeoff.

Your goals are:

1. verify the bridge surface is compute-executable and honest;
2. run one wrapper-backed compute preflight on an approved Slurm route;
3. run the real multi-format store benchmark on compute node(s);
4. determine the runnable candidate set from produced benchmark outputs;
5. run the real 1-GPU, 200-step GR00T telemetry for runnable candidates,
   subject to task fallback rules;
6. collect exact run ids, Slurm job ids if present, logs, output paths,
   candidate results, and blockers.

This wave must not:

- mutate source dataset
- run long finetune or 30-epoch training
- download model/data/checkpoints
- enable W&B online sync
- enable HF network
- use raw `srun`/`sbatch` directly outside project wrappers

## Wrapper policy for this wave

Use project wrappers only.

For interactive/short compute allocations, use:

- `scripts/slurm/request_compute_debug.sh`

Do not run raw `srun` directly.

Because the current repo wrapper surface for this task is centered on debug
allocations plus a task-local training bridge, wrapper-backed `srun` is the
authorized route here.

If you determine a formal `sbatch` wrapper path is required but insufficiently
specified by current repo surfaces, stop and report `BLOCKED_COMPUTE_ENV`
rather than improvising raw scheduler commands.

## Phase A — Static bridge and path verification

Before any compute allocation:

1. verify the actual training bridge entrypoint now present in source
   (do not assume names from the packet; inspect the current files)
2. verify the actual datastore benchmark entrypoint now present in source
3. verify local model root visibility:
   - `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`
4. verify bridge-required local files exist according to the Training/Model
   reports
5. verify the shared fairness manifest path and working-root paths exist or
   can be created under approved governed roots
6. verify offline env guards are present in the rendered bridge/wrapper surface

Required evidence outputs under:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/`

## Phase B — Wrapper dry-run preflight

Run a wrapper dry-run first, no allocation:

- use `scripts/slurm/request_compute_debug.sh`
- profile may start from `h800-gpu`, but override to the actual approved task
  resource shape when needed
- for this task, the preferred partition family is `a100` when available in the
  current cluster route

Record:

- exact wrapper command
- resolved partition / cpus / mem / gres / time
- generated `srun_command.txt`

Suggested run id:

- `autovla-m3-multiformat-preflight-dryrun`

Required evidence path:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-dryrun.md`

## Phase C — Actual short compute preflight

Use the same wrapper for one short real preflight allocation.

Intent:

- verify compute node visibility for:
  - source dataset root
  - working dataset root
  - local GR00T project root
  - local base-model root
  - project-local toolenv
- verify `nvidia-smi` visibility
- verify bridge command can at least render/validate on compute

This is not the final benchmark or telemetry run.

Preferred bounded shape:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `gpu:1`
- time: `01:00:00`

Suggested run id:

- `autovla-m3-multiformat-preflight-real`

Required evidence under:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-real.md`
- wrapper-emitted debug allocation path under `runs/slurm_debug/autovla-m3-multiformat-preflight-real/**`

## Phase D — Real multi-format store benchmark

Run the real store benchmark on compute through the current actual benchmark
surface.

Preserve prompt semantics:

- compare all four candidates
- use same fairness manifest
- bounded sample/window selection
- record blocked rows when needed

Preferred bounded resource shape:

- partition: `a100`
- cpus: `32`
- mem: `128G`
- gres: `none`
- time: `06:00:00`

Suggested run id:

- `autovla-m3-multiformat-store-benchmark`

Use wrapper-backed `srun`, not raw `srun`.

You may adapt the invoked Python module/CLI to the actual implemented source,
but preserve the semantics from the top-level prompt.

Expected governed output root:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/`

Required evidence:

- exact wrapper command
- actual compute log path
- benchmark output root
- candidate rows and statuses
- runnable candidate set derived from outputs

## Phase E — Real 1-GPU 200-step telemetry

For each runnable candidate, run the real bounded GR00T-N1D6 telemetry route
through the actual bridge surface implemented by Training wave 3.

Requirements:

- exactly 1 GPU
- exactly 200 steps
- offline env guards enabled
- local read-only GR00T base-model root only
- no network
- no long training

Preferred resource shape per candidate:

- partition: `a100`
- cpus: `32`
- mem: `128G`
- gres: `gpu:1`
- time: `02:00:00`

Suggested run id prefix:

- `autovla-m3-multiformat-gpu200-<candidate>`

Expected governed output root per candidate:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/gpu200/<candidate>/`

Wrapper route:

- use `scripts/slurm/request_compute_debug.sh`
- do not run raw `srun`

You may adapt the bridge module name to the actual implemented source, but
preserve the task semantics from the top-level prompt.

## Candidate fallback rule

If all four runnable candidates cannot be completed safely within this wave,
apply the top-level prompt fallback exactly:

at minimum run:

1. `zjh_lerobot_v21_raw`
2. the best load-benchmark candidate
3. the second-best candidate if within 10% of best samples/sec or p95 latency

For all not-run candidates, record exact `NOT_RUN` rows and reasons.

Do not claim a winner unless:

- all four load benchmarks are complete
- and at least raw v2.1 plus one converted/store candidate have 200-step
  telemetry

## Data to record

Your report must capture at minimum:

- actual wrapper commands used
- run ids
- whether wrapper dry-run passed
- whether real preflight passed
- benchmark run id and output path
- runnable candidate set
- telemetry run id per candidate
- actual compute log path per candidate
- output root per candidate
- whether each candidate completed 200 steps
- any exact blocker tokens / reasons
- whether optional 2-GPU comm was skipped

## Required report

Write exactly one report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave3.md`

The report must include:

- workspace verification
- start-gate verification
- actual wrapper route used
- dry-run preflight result
- real preflight result
- real benchmark execution result
- runnable candidate set
- 1-GPU telemetry execution result by candidate
- exact evidence paths under `runs/tmp`, `runs/slurm`, and `runs/slurm_debug`
- whether training/model bridge was sufficient
- whether any blocker remains for publication-quality summary tables
- DevSpace MCP compliance
- subagent retirement ledger

## Allowed conclusion values

- `PASS`
- `BLOCKED_COMPUTE_ENV`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`

## Finish condition

This wave is successful only if:

1. wrapper dry-run evidence exists
2. one real compute preflight was attempted
3. the real store benchmark was attempted on compute
4. the runnable candidate set is evidenced from actual outputs
5. at least the required fallback telemetry set was attempted unless a hard
   compute blocker prevents it
6. the report is written at the required path
