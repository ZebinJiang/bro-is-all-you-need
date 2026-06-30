# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Compute Plan Rereview

## Workspace Verification

- Result: PASS.
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- status before this report write:
  - `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
  - `?? coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/`
  - `?? coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`

## Evidence Reviewed

- `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`
- `/home/cz-jzb/workspace/vla-flywheel/.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-plan.md`
- `boundaries.txt`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/COMPUTE_EXECUTION_STATE.yaml`
- current perf harness surfaces:
  - `autovla/dataloader/perf/cli.py`
  - `autovla/dataloader/perf/config.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/MODULE.md`
  - `tests/dataloader/test_perf_harness.py`
- current Slurm helper surfaces:
  - `scripts/slurm/request_compute_debug.sh`
  - `scripts/slurm/submit_sandbox_job.sh`
  - `configs/slurm/default_sandbox.json`
  - `configs/slurm/debug_profiles.json`

## Reconciliation Finding

The previous Compute/HPC plan review requested changes because no task card/spec was available, the current harness did not yet expose `store-build-bounded` or `store-read-benchmark`, and the available project wrapper path was not a clean fit for a noninteractive three-step evidence run.

Manager reconciliation resolves the authorization ambiguity:

- the active task card now exists in the PR #14 worktree;
- the root-checkout spec is normative;
- implementation will add the missing store plan/build/read modes before any compute submission;
- Manager accepts the spec's one-off `srun` command as user-authorized when a project wrapper cannot cover the exact bounded noninteractive run;
- final evidence must record command, job/node, environment, stdout/stderr, and generated report paths.

## Compute Plan Decision

Compute plan can proceed after implementation adds and validates the missing store-builder/read entrypoints.

A wrapper change is not mandatory before the first bounded compute run because the normative spec plus Manager reconciliation authorize the one-off raw `srun` template when the existing project wrappers cannot express the exact one-allocation run. A project wrapper remains preferred for repeatability, but it is not a blocker for this task if the one-off run is recorded exactly and remains inside the approved envelope.

## Approved Resource Envelope

- partition: `a100`
- nodes: `1`
- ntasks: `1`
- cpus_per_task: `32`
- memory: `128G`
- gres: `gpu:1`
- time limit: `04:00:00`
- max compute jobs: `3`
- preferred execution: one bounded allocation containing:
  - raw bounded-decode baseline;
  - `store-build-bounded`;
  - `store-read-benchmark`;
  - optional `nvidia-smi` telemetry only, no GPU compute.

The `gpu:1` request is acceptable for scheduler placement and telemetry. It must not be used for model CUDA, training, checkpoint, tokenizer, or GPU-compute work.

## Required Runtime Guards

The compute run must set or enforce:

- `AUTOVLA_PERF_PROBE_ONLY=1`
- `AUTOVLA_EXPECT_NO_REAL_TRAINING=1`
- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONNOUSERSITE=1`
- `WANDB_MODE=disabled` or equivalent no-network W&B guard
- Hugging Face/network offline behavior if any HF/transformers package path could be imported
- governed `TMPDIR` under `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/` when temporary files are needed

The command must not load real model, tokenizer, checkpoint weights, HF/W&B network, endpoint, robot, or training runtime.

## Evidence Required For The Compute Run

Final compute evidence must record:

- exact command string, including the full one-off `srun` command or wrapper command;
- job id;
- node name;
- resource allocation observed or requested;
- exported environment guard values;
- stdout path;
- stderr path, or a clearly labeled combined stdout/stderr log if the one-off command uses `2>&1 | tee`;
- exit status;
- generated report paths:
  - raw bounded-decode output/report;
  - training-store build output/report;
  - training-store read benchmark output/report;
  - training store manifest/index/checksum/statistics paths;
- PASS/WARN/FAIL classification and speedup/bottleneck evidence.

## PFS Store Constraints

- Store outputs must remain under ignored task evidence, e.g. `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/`, unless a future persistent derived dataset path is explicitly authorized.
- No writes into `datasets/readonly`.
- No local NVMe, node-local scratch, `/scratch`, `/tmp`, or `$SLURM_TMPDIR` assumption for correctness.
- No full dataset conversion or full media predecode.
- No media/store artifacts may be committed.
- Store build must be bounded by max episodes, max samples, and max decode seconds.

## Stop Conditions

Do not submit compute if any remain true:

- `store-plan`, `store-build-bounded`, or `store-read-benchmark` entrypoints are missing;
- implementation cannot run the raw bounded-decode, store build, and store read benchmark inside max three compute jobs;
- command would write outside governed ignored evidence paths;
- command would run real training, model/checkpoint/tokenizer load, W&B/HF network, endpoint, robot, full conversion, or unbounded dataset scan;
- scheduler requires unspecified account/QoS or rejects `a100`, `32` CPU, `128G`, `gpu:1`, or `04:00:00`;
- evidence capture cannot record job id, node, env, logs, exit status, and generated reports.

## Compliance And Ledger

- DevSpace MCP: not used.
- Source/tests/docs/config/git/PR mutation: none.
- Slurm/compute jobs: not run in this rereview.
- GPU/CUDA: not run in this rereview.
- Report write: limited to `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-plan-rereview.md`.
- Dispatch reasoning tier recorded: xhigh; prohibited tier not used.
- Child subagents: none.
- Retirement ledger: Compute/HPC Owner logical review retired=yes.

## Conclusion

APPROVE_COMPUTE_PLAN
