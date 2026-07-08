# Owner Compute-W1 Report

Task: AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001
Owner role: 80-OWNER · Compute/HPC
Wave: 4 Compute-W1
Runtime override: model=gpt-5.5, thinking=high
Thinking xhigh used: no
Thinking max used: no

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- Required baseline HEAD before Data-W1: matched.
- Data-W1 source/test changes were present as unstaged working-tree modifications, as expected from the Wave 4 dispatch.

## Inputs Read

- `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-ro1.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w1.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-quality-r1.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/quality/quality-r1-fast-validation.md`
- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py` CLI/candidate matrix

Quality-R1 decision: `PASS_FAST_GATE`; Compute-W1 proceeded.

## Scheduler And Wrapper Evidence

Project wrapper used:

- `scripts/slurm/request_compute_debug.sh`

Task-local launch script:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/run_final_dataloader_perf_srun.sh`

Task-local inside-compute script:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/run_final_dataloader_perf_inside_compute.sh`

Wrapper command:

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

Raw command emitted by wrapper:

- `runs/slurm_debug/autovla-m3-pr30-final-dataloader-perf-w4/logs/srun_command.txt`
- copied to `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/wrapper_srun_command.txt`

Scheduler/job metadata:

- Slurm job id: `2485`
- Node: `instance-yp83uwa1-1`
- Partition: `a100`
- CPUs: `16`
- Memory: `128G`
- GRES: `none`
- Time: `04:00:00`

No scheduler rejection occurred. No lower-risk retry was attempted because the failure was in the runner/evidence path, not in scheduling.

## Actual Matrix Run

Primary matrix attempted:

- `worker_count=8`
- `batch_size=8`
- `warmup=10`
- `measured=100`
- `repeats=3`
- `max_samples=4096`
- `max_episodes=32`
- `seed=11`

Primary status:

- `primary_matrix exit_code=1`

Secondary worker sweep:

- Not run because primary matrix failed.

Fallback matrix:

- Not run because the primary was not scheduler/time infeasible; it failed due runner multiprocessing timeout.

## Candidate Mapping

- D1a = `zjh_lerobot_v21_gr00t_or_lerobot_native`; expected blocked/native unsafe row.
- D1b = `zjh_lerobot_v21_autovla_adapter`.
- D3 = `zjh_lerobot_v3_local`.
- D4 = `zjh_webdataset_tar`.
- D5 = `zjh_robodm_container_v1`.
- D6 = `zjh_zarr_cache`; optional/not implemented if no implementation.

The run did not reach final table emission, so final per-candidate metrics are unavailable.

## Failure Evidence

The primary CLI failed with:

```text
TimeoutError: adapter worker process did not report evidence
```

Traceback location:

- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`, `_run_adapter_processes`
- `queue.get(timeout=120.0)` raised `_queue.Empty`
- The code re-raised `TimeoutError("adapter worker process did not report evidence")`

Log paths:

- stdout: `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-dataloader-perf.stdout.log`
- stderr: `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-dataloader-perf.stderr.log`
- status: `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-dataloader-perf.status`

## Raw Metrics Artifact Paths

Partial artifact:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/shared-sample-window-manifest.json`

Missing required final metrics artifacts:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_raw.json`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/actual_worker_bakeoff_raw.json`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/per_batch_timings.jsonl`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/worker_evidence_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/stage_timing_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/payload_completeness_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/v21_gap_investigation_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/backend_decision_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/missing_telemetry_table.*`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/command_log_index.json`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark/final-primary/generated_artifact_ledger.json`

Because these artifacts are absent, metrics instrumentation is not verifiable and the run cannot support final docs.

## Source Mutation Proof

Source dataset:

- `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`

Metadata manifest hash before:

- `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`

Metadata manifest hash after:

- `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`

Result:

- `source_dataset_mutation_check: PASS`

Evidence path:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/source_dataset_mutation_check.md`

## Generated Artifact Ledger

The primary run failed before the runner emitted `generated_artifact_ledger.json`.

Generated working artifacts were still created under the authorized working root:

- `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_pr30_final_dataloader_perf_v1`
- observed size: about `6.9G`
- observed file count: `12297`

Generated output index paths:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/generated_output_files.txt`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/generated_working_files_sample.txt`

## No External Effects Compliance

- DevSpace MCP: no.
- Subagents: none used; retired yes.
- Git stage/commit/push/PR mutation: no.
- Source/tests/docs/config/dependency edits by Compute-W1: no.
- `datasets/readonly` mutation: no.
- Dependency install/global/conda/system mutation: no.
- Raw unmanaged `srun`/`sbatch`: no.
- GPU/CUDA/GPU200 allocation: no; wrapper used `gres=none`, and inside script set `CUDA_VISIBLE_DEVICES=""`.
- Real training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: no.

## Downstream Routing

Training-R1 / Architecture-R2 / Quality-R2 may proceed only as blocker-review or repair-routing stages.

They should not treat this run as final compute evidence ready for docs because:

- primary matrix exited 1;
- final raw metrics and summary tables are missing;
- per-batch timing evidence is missing;
- command log index and generated artifact ledger from the runner are missing;
- no final per-candidate rankings are available.

Recommended next owner route: Data repair of the candidate-specific multiprocessing timeout path, then another compute run.

## Conclusion

BLOCKED_DEPENDENCY_OR_EXECUTION
