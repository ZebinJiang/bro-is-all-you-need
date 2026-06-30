# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Compute Resource Plan Review

## Workspace Verification

- Result: PASS.
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- status: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
- worktree source diff before this report write: clean.

## Evidence Reviewed

- `boundaries.txt`
- `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
- `coordination/COMPUTE_EXECUTION_STATE.yaml`
- `configs/slurm/default_sandbox.json`
- `configs/slurm/debug_profiles.json`
- `scripts/slurm/request_compute_debug.sh`
- `scripts/slurm/submit_sandbox_job.sh`
- `autovla/dataloader/perf/cli.py`
- `autovla/dataloader/perf/config.py`
- `autovla/dataloader/perf/benchmark.py`
- `autovla/dataloader/perf/MODULE.md`
- `tests/dataloader/test_perf_harness.py`
- `docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md`
- `docs/architecture/FAST_TRAINING_VIEW.md`
- `docs/architecture/AI_NATIVE_VLA_INFRA.md`

No task card/spec/report file for this task id was present under `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/` before this review. This report therefore treats the dispatch prompt as the authoritative Wave 1 task card.

## Requested Resource Envelope

- Cluster/partition: `cz_hpc01` / `a100`.
- Nodes: `1`.
- Tasks: `1`.
- CPUs per task: `32`.
- Memory: `128G`.
- GRES: `gpu:1`.
- Wall time: `04:00:00` maximum.
- Maximum compute jobs: `3`.
- Intended one-allocation sequence, if implemented:
  - raw bounded-decode probe;
  - store-build-bounded;
  - store-read-benchmark.

This resource envelope is acceptable for a bounded compute-node PFS store-builder validation in principle. It is larger than the active `configs/slurm/default_sandbox.json` defaults, but the top-level dispatch supplies explicit resources, so the prompt is the resource source for this plan review.

## Current Harness Findings

- Current perf CLI supports `python -m autovla.dataloader.perf benchmark`.
- Current modes are `metadata-only`, `bounded-decode`, and `training-view`.
- `bounded-decode` is correctly compute-gated by `SLURM_JOB_ID` or `AUTOVLA_PERF_COMPUTE_NODE`.
- Current bounded media probe reads a small bounded amount of video bytes and does not perform full conversion or real training.
- Current perf harness records no model load, checkpoint read, W&B/HF network, real training, or scheduler submission from inside the benchmark.
- Current code does not expose `store-build-bounded` or `store-read-benchmark` entrypoints.
- Current Fast Training View docs still describe the optimized store as a future schema/policy target, not a materialized PFS shared store.

## Wrapper Assessment

- Repository governance requires project wrappers/helpers for Slurm work and logged equivalent raw commands.
- Direct raw scheduler commands are allowed only as a recorded one-off user exception; this plan should not rely on raw `srun` as the normal execution path.
- `scripts/slurm/request_compute_debug.sh` can override partition, CPU, memory, GRES, and time, and it logs the raw `srun` command under `runs/slurm_debug/<run_id>/logs/srun_command.txt`.
- However, `request_compute_debug.sh` always appends `--pty`. That is acceptable for interactive debug sessions, but it is not ideal for a four-hour, three-step store-builder validation that needs deterministic stdout/stderr capture and terminal evidence.
- `scripts/slurm/submit_sandbox_job.sh` records a noninteractive `sbatch` command and run evidence, but it reads resources from config and does not directly provide the requested one-allocation chained command for this PFS store-builder task.

Required wrapper adjustment before execution:

- Provide a project wrapper or wrapper mode that runs the one-allocation command noninteractively, records run id, raw scheduler command, node, allocation/job id, stdout/stderr, exit status, generated report paths, and per-step status.
- The wrapper may use `srun` under the hood, but it must be invoked through a project wrapper and must not require interactive `--pty` behavior.
- The wrapper must accept the explicit prompt resources: `a100`, `1` node, `1` task, `32` CPU, `128G`, `gpu:1`, and `04:00:00`.
- If scheduler policy rejects `gpu:1`, account, QoS, partition, time, memory, or CPU shape, stop with compute environment/policy blocker; do not broaden resources or bypass site policy.

## Required Environment And Safety Guards

The eventual compute command should set or enforce:

- `AUTOVLA_PERF_COMPUTE_NODE=1`.
- `AUTOVLA_EXPECT_NO_REAL_TRAINING=1`.
- `AUTOVLA_EXPECT_NO_MODEL_LOAD=1`.
- `AUTOVLA_EXPECT_NO_CHECKPOINT=1`.
- `WANDB_MODE=disabled`.
- `HF_HUB_OFFLINE=1`.
- `TRANSFORMERS_OFFLINE=1`.
- `PYTHONNOUSERSITE=1`.
- `PYTHONDONTWRITEBYTECODE=1`.
- `TMPDIR` under the governed run directory, not under unmanaged local scratch.

GPU GRES is acceptable only for scheduler placement or explicit telemetry collection. The command must not run model CUDA, torch CUDA training/inference, checkpoint loading, or GPU compute.

## PFS Shared-Store Policy

- Store-build outputs must be under a governed project path on the shared filesystem, for example `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/<run_id>/store/` or a future approved `datasets/cache/...` path.
- The plan must not assume node-local NVMe, `/local_nvme`, `/scratch`, `/tmp`, `$SLURM_TMPDIR`, or local ephemeral storage for correctness.
- Any temporary files must remain under the run directory or another explicitly governed project-local path.
- The plan must not copy full datasets into the run directory.
- The bounded store build must cap episodes/samples/bytes/time and must emit a manifest with source metadata, byte counts, file counts, and stop conditions.

## Stop Conditions

Stop before submission if any of the following remain unresolved:

- No concrete one-allocation command sequence exists for bounded-decode, store-build-bounded, and store-read-benchmark.
- Store-build/read entrypoints are missing or unreviewed.
- Wrapper still requires interactive `--pty` for this noninteractive evidence job.
- Store path assumes local NVMe/local scratch or writes outside governed paths.
- Command would run real training, model/tokenizer/checkpoint load, HF/W&B network, endpoint, robot, full dataset conversion, or unbounded dataset scan.
- Scheduler rejects the requested resource shape or requires account/QoS not supplied by Manager.
- More than three compute jobs would be required.

## Decision

The requested resource envelope is acceptable in principle, but the current executable plan is not ready to run. The plan needs a wrapper/evidence adjustment and concrete store-build/read commands before Compute/HPC should authorize actual submission.

## Compliance And Ledger

- DevSpace MCP: not used.
- Source/test/git/PR mutation: none.
- Slurm/compute jobs: not run.
- GPU/CUDA: not run.
- Dataset scan/decode/store build: not run.
- Report write: limited to `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-plan.md`.
- Dispatch reasoning tier recorded: xhigh; prohibited tier not used.
- Child subagents: none.
- Retirement ledger: Compute/HPC Owner logical review retired=yes.

## Conclusion

REQUEST_CHANGES_PLAN
