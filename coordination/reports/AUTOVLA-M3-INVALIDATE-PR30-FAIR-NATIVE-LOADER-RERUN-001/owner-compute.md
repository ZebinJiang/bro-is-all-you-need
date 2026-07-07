# Owner Compute/HPC Evidence Review

Task: `AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`
Role: `80-OWNER · Compute/HPC`
Mode: read-only compute evidence review plus report write only
Decision: `APPROVE_COMPUTE`

## Dispatch and Scope

- User override recorded: `model=gpt-5.5`, `thinking=high`
- `thinking=max` used: no
- DevSpace MCP used: no
- New Slurm, compute, training, test, source edit, docs edit, PR mutation, staging, commit, push, merge, reset, restore, clean, stash: not run
- Report-only write performed: `coordination/reports/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/owner-compute.md`

## Workspace Verification

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git top level: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `cb5ca3f12e01d7900b2f04945db0137a6ba8a15c`
- Pre-existing dirty/untracked worktree state observed and not modified beyond this report path.

## Evidence Reviewed

- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/run_fair_native_loader_srun.sh`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/run_fair_native_loader_inside_compute.sh`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.status`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.log`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.json`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.md`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/generated-artifact-ledger.json`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/invalidation/pr30-invalidated-results-manifest.json`

## Compute Routing Review

The rerun evidence supports compute execution after the `python -m` entrypoint fix.

- The outer wrapper invokes Slurm via `srun -p a100 -c 32 --mem=128G --gres=gpu:1 --time=04:00:00`.
- The inner compute script runs `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.dataloader.perf.fair_native_loader_bakeoff`.
- `fair-native-loader-srun.status` contains `0`, so the recorded `srun` wrapper completed successfully.
- `fair-native-loader-srun.log` records the benchmark Markdown output path and `conclusion=NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- No contrary login-node heavy-run evidence was found in the reviewed task-local compute evidence.

Residual note: the reviewed log does not expose a Slurm job id or compute hostname. This approval is therefore based on the recorded `srun` wrapper command, successful wrapper status, and task-local benchmark outputs, not on scheduler accounting or node-name evidence.

## Fair Rerun Output Review

The fair benchmark result is internally consistent and bounded.

- Output schema: `autovla.fair_native_loader_bakeoff.v1`
- Row count: `4`
- All candidates report `status=RUNNABLE_NOW`, `payload_complete=True`, `worker_count=8`, `batch_size=8`, `warmup_batches=5`, `measured_batches=50`, `repeats=3`, `sample_count=2048`, and no missing metrics.
- Candidate sample throughput:
  - `zjh_lerobot_v21_raw`: `5.437251` samples/s, recommendation `native_raw_baseline_context`
  - `zjh_lerobot_v3_local`: `174.028064` samples/s, recommendation `compare_against_raw_native_before_selection`
  - `zjh_webdataset_tar`: `36.113377` samples/s, recommendation `compare_against_raw_native_before_selection`
  - `zjh_robodm_container_v1`: `47.459339` samples/s, recommendation `compare_against_raw_native_before_selection`
- The Markdown summary explicitly invalidates the prior PR #30 multiformat benchmark numbers because the old raw row used preloaded `SourceSample` lookup and `camera_refs`.
- The Markdown summary selects no final backend winner by this table alone.
- The wrapper log conclusion is `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

## Boundary Review

The fair rerun output stays inside the requested non-training/non-runtime boundary.

- For every benchmark row, `checkpoint_read=false`.
- For every benchmark row, `model_load=false`.
- For every benchmark row, `real_training=false`.
- For every benchmark row, `hf_network=false`.
- For every benchmark row, `wandb=false`.
- For every benchmark row, `endpoint=false`.
- For every benchmark row, `robot=false`.
- For every benchmark row, `tokenizer_load=false`.
- Generated-artifact ledger reports `source_dataset_mutated=False`.
- Invalidated-results manifest reports `source_dataset_mutation_status=not_mutated`.

## Subagent Ledger

- Subagents used: none
- Child-agent depth: `0`
- Retirement status: not applicable

## Final Decision

`APPROVE_COMPUTE`

The evidence supports that the fair native loader rerun completed through the task-local Slurm `srun` compute wrapper after the `python -m` entrypoint fix, produced bounded fair-benchmark outputs, did not cross into training/model/checkpoint/HF/W&B/endpoint/robot behavior, and concluded `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
