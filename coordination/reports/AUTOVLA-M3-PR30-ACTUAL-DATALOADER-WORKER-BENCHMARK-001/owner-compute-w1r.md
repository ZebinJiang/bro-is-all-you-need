# Owner Compute-W1R Report

Task: AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001
Owner role: 80-OWNER · Compute/HPC
Dispatch: Compute-W1R route recheck and wrapper-backed source-dataset run
Runtime override: model=gpt-5.5, thinking=high
Thinking xhigh used: no
Thinking max used: no

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `2322606f26fecbef37eafdb7504c848d476cd29e`
- Required worktree/root: matched.
- Required branch: matched.
- Required HEAD: matched exactly.
- Uncommitted state included existing current-task/report/generated paths; no git stage/commit/push/PR mutation was performed.

## Route Recheck

Prior route evidence inspected:

- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark-wave4/logs/srun_command.txt`
- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark-wave6/logs/srun_command.txt`

Both prior route logs used the same project wrapper profile and resource shape:

- `profile=h800-gpu`
- `partition=a100`
- `cpus_per_task=16`
- `mem=64G`
- `gres=none`
- `time=01:00:00`

Manager updated the active task scope to authorize the narrow wrapper output root:

- `runs/slurm_debug/autovla-m3-pr30-actual-worker-benchmark-w1r/**`

Given that explicit authorization plus the prior same-worktree route precedent, the wrapper-backed route was acceptable for this dataloader-only benchmark attempt. The run used `gres=none` and did not request GPU resources.

## Wrapper Command

Task-local launch script:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/run_actual_worker_benchmark_srun.sh`

Task-local inside-allocation script:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/run_actual_worker_benchmark_inside_compute.sh`

Wrapper command shape executed:

```bash
scripts/slurm/request_compute_debug.sh \
  --profile h800-gpu \
  --partition a100 \
  --cpus 16 \
  --mem 64G \
  --gres none \
  --time 01:00:00 \
  --run-id autovla-m3-pr30-actual-worker-benchmark-w1r \
  -- bash -lc 'bash runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/run_actual_worker_benchmark_inside_compute.sh'
```

Raw wrapper evidence:

- `runs/slurm_debug/autovla-m3-pr30-actual-worker-benchmark-w1r/logs/srun_command.txt`

Logged raw `srun` route:

```bash
srun -p a100 -c 16 --mem=64G --time=01:00:00 --chdir=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff --export=ALL\,SANDBOX_PROJECT_ROOT=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff\,SANDBOX_RUN_ID=autovla-m3-pr30-actual-worker-benchmark-w1r\,SANDBOX_RUN_DIR=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/slurm_debug/autovla-m3-pr30-actual-worker-benchmark-w1r\,PYTHONNOUSERSITE=1 --pty bash -lc bash\ runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/run_actual_worker_benchmark_inside_compute.sh
```

The wrapper log did not emit a scheduler job id; no unsupported job-id claim is made here. Compute host recorded by the inside script: `instance-yp83uwa1-2`.

## Benchmark Execution

Benchmark ran: yes.

Source dataset:

- `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`

Working root:

- `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_actual_worker_bakeoff_v1`

Output root:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark-w1r`

Run parameters:

- `worker_count`: `0,2,4,8`
- `batch_size`: `8`
- `max_samples`: `2048`
- `seed`: `11`
- `--tiny-fixture`: not used.

Guard environment set inside allocation:

- `AUTOVLA_ACTUAL_DATALOADER_BENCHMARK=1`
- `AUTOVLA_EXPECT_NO_TRAINING=1`
- `AUTOVLA_EXPECT_NO_MODEL_LOAD=1`
- `AUTOVLA_EXPECT_NO_HF_NETWORK=1`
- `HF_HUB_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`
- `WANDB_MODE=disabled`
- `PYTHONDONTWRITEBYTECODE=1`
- `CUDA_VISIBLE_DEVICES=""`

## Exit Codes And Logs

All wrapper-loop invocations exited 0:

- `worker_count=0 exit_code=0`
- `worker_count=2 exit_code=0`
- `worker_count=4 exit_code=0`
- `worker_count=8 exit_code=0`

Task-local compute logs:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/actual-worker-benchmark-w1r.status`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/actual-worker-benchmark-w1r.stdout.log`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/actual-worker-benchmark-w1r.stderr.log`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/compute/actual-worker-benchmark-w1r-output-files.txt`

Wrapper route log:

- `runs/slurm_debug/autovla-m3-pr30-actual-worker-benchmark-w1r/logs/srun_command.txt`

## Output Directories

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark-w1r/worker_count_0`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark-w1r/worker_count_2`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark-w1r/worker_count_4`
- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/actual-worker-benchmark-w1r/worker_count_8`

Each output directory emitted the expected current-runner files, including:

- `actual_worker_bakeoff_raw.json`
- `actual_worker_bakeoff_summary.md`
- `actual_worker_bakeoff_summary.csv`
- `worker_evidence_table.md/json/csv`
- `stage_timing_table.md/json/csv`
- `missing_telemetry_table.md/json/csv`
- `per_batch_timings.jsonl`
- `source_dataset_mutation_check.md`
- `generated_artifact_ledger.json`

## Matrix Evidence Summary

Runnable adapter worker-count evidence matched requested worker counts:

- `worker_count=0`: runnable adapters D2-D5 show `actual_worker_count=0`, `execution_mode=serial`, `sample_count=2048`, `batch_count=256`, `worker_count_evidence_status=PASS`.
- `worker_count=2`: runnable adapters D2-D5 show `actual_worker_count=2`, `execution_mode=process_pool`, two observed worker ids/process ids, `sample_count=2048`, `batch_count=256`, `worker_count_evidence_status=PASS`.
- `worker_count=4`: runnable adapters D2-D5 show `actual_worker_count=4`, `execution_mode=process_pool`, four observed worker ids/process ids, `sample_count=2048`, `batch_count=256`, `worker_count_evidence_status=PASS`.
- `worker_count=8`: runnable adapters D2-D5 show `actual_worker_count=8`, `execution_mode=process_pool`, eight observed worker ids/process ids, `sample_count=2048`, `batch_count=256`, `worker_count_evidence_status=PASS`.

Observed source-dataset throughput ranges in emitted summaries:

- `worker_count=0`: runnable adapters about `135.97` to `140.94` samples/sec.
- `worker_count=2`: runnable adapters about `135.54` to `136.61` samples/sec.
- `worker_count=4`: runnable adapters about `175.66` to `177.44` samples/sec.
- `worker_count=8`: runnable adapters about `195.74` to `197.72` samples/sec.

Each runnable adapter read `1207959552` bytes and processed `2048` samples for each worker-count run.

## Remaining Evidence Gaps

This W1R run is valid source-dataset compute evidence, but it should not be claimed as final benchmark PASS or backend-winner evidence.

Remaining gaps observed in current emitted evidence:

- D1 `zjh_lerobot_v21_gr00t_or_lerobot_native` remains `NOT_RUN_UNSAFE_OR_UNAVAILABLE` with blocking missing telemetry `worker_read_timing`.
- Optional D6 `zjh_zarr_cache` remains `NOT_IMPLEMENTED_IN_CURRENT_PR`.
- The current runner emits one measured pass per worker count, not the full prompt-contract warmup/measured/repeats matrix.
- The current runner does not exercise a persistent-worker/prefetch matrix; emitted `persistent_reader_enabled=False` and `prefetch_enabled=False`.
- Several core timing fields in the wide summary remain zero/default for runnable adapters, including stage-specific fields such as `loader_init_ms`, `index_load_ms`, `metadata_load_ms`, `media_decode_ms`, `rgb_materialize_ms`, `action_load_ms`, `state_load_ms`, `language_load_ms`, `payload_validation_ms`, `tensor_or_array_conversion_ms`, `worker_queue_wait_ms`, and `next_batch_wait_ms`.
- `per_batch_timings.jsonl` contains six lines per worker-count output, not a full measured/repeats timing series for every prompt-contract field.

## Source Dataset Mutation Check

Each emitted `source_dataset_mutation_check.md` reports:

- `source_dataset_mutation_check: PASS`

I did not write to `datasets/readonly/`. Generated artifacts are under authorized generated roots:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/**`
- `runs/slurm_debug/autovla-m3-pr30-actual-worker-benchmark-w1r/**`
- `datasets/working/autovla_actual_worker_bakeoff_v1/**`

The generated artifact ledger marks working-root payloads as ignored/generated artifacts and not intended for commit.

## External-Effect Compliance

- DevSpace MCP used: no.
- Subagents used: none.
- Subagent retirement ledger: none required; no subagents were created.
- Git stage/commit/push/PR mutation: no.
- Source/test/doc/config/dependency edits: no.
- Dependency installs: no.
- Raw unmanaged `srun`: no; project wrapper was used.
- GPU/CUDA/GPU200 allocation: no; wrapper used `gres=none`, and the inside script set `CUDA_VISIBLE_DEVICES=""`.
- Real training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot usage: no.
- `datasets/readonly` mutation: no.
- Login-node full benchmark: no; only lightweight route/schema/path inspection was run before wrapper execution.

## Final Judgement

REQUEST_CHANGES_COMPUTE_EVIDENCE

The wrapper-backed compute route succeeded and produced real source-dataset actual-worker evidence for worker counts `0,2,4,8`. However, current emitted evidence is not sufficient for final benchmark PASS/backend selection because D1 remains unexecuted/blocked and the metrics surface does not yet satisfy the full prompt-contract matrix and instrumentation requirements.
