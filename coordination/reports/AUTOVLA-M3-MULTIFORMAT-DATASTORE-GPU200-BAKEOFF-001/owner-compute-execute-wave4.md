# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Compute Execute Wave 4

Role: `80-OWNER · Compute/HPC`

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## 2. Reused Wave 3 Evidence

Wave 4 reused the successful Wave 3 preflight evidence exactly as authorized:

- dry-run preflight evidence:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-dryrun.md`
  - `runs/slurm_debug/autovla-m3-multiformat-preflight-dryrun/logs/srun_command.txt`
- real preflight evidence:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/preflight-real.md`
  - `runs/slurm_debug/autovla-m3-multiformat-preflight-real/logs/srun_command.txt`
- bridge/runtime viability evidence:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/bridge_preflight_raw.yaml`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/base_model_manifest.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/manifests/checkpoint_manifest.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/autovla_gr00t_gpu200_multiformat.sbatch`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/static-preflight/rendered-wrapper/telemetry_bridge_plan.json`

Reused Wave 3 runtime finding that remained valid:

- the Isaac bridge is compute-executable only when runtime uses:
  - `python_executable=/home/cz-jzb/workspace/Isaac-GR00T17/.venv/bin/python`
  - `PYTHONPATH=/home/cz-jzb/workspace/Isaac-GR00T17`

No reused preflight path had disappeared, so Wave 4 did not rerun preflight.

## 3. Exact Reduced Benchmark Wrapper Command And Envelope

Reduced benchmark config written under allowed task-owned evidence path:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`

Config values carried from the Wave 4 packet:

- `max_episodes: 16`
- `max_samples: 2048`
- `batch_size: 8`
- `seed: 11`
- packet metadata preserved in YAML:
  - `worker_count: 8`
  - `repeats: 3`

Important implementation note:

- the current benchmark CLI surface consumes:
  - `max_episodes`
  - `max_samples`
  - `batch_size`
  - `measured_batches`
  - `samples_per_shard`
  - `seed`
- the current benchmark CLI does not expose dedicated `worker_count` or `repeats` knobs without source mutation, so those Wave 4 reduction values were preserved in the task-local YAML as packet metadata but were not consumed by the existing code path.

Exact wrapper route used:

- `scripts/slurm/request_compute_debug.sh --profile h800-gpu --partition a100 --cpus 16 --mem 64G --gres none --time 01:00:00 --run-id autovla-m3-multiformat-store-benchmark-wave4 -- bash -lc 'set -euo pipefail; /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.dataloader.stores run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml; echo STORE_BENCHMARK_OK'`

Resolved benchmark envelope:

- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `none`
- time: `01:00:00`

Wrapper command evidence:

- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark-wave4/logs/srun_command.txt`

## 4. Whether Reduced Benchmark Launched

Yes.

Wave 4 successfully got past the Wave 3 scheduler blocker:

- no `QOSMaxWallDurationPerJobLimit` rejection occurred on the narrowed `01:00:00` CPU envelope
- the benchmark launched on compute through the approved wrapper

However, the launched benchmark did not complete.

## 5. Benchmark Output Root

Expected output root:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/**`

Actual result:

- not produced

Reason:

- the benchmark failed during runtime before `load-benchmark.json`, `load-benchmark.csv`, or `load-benchmark.md` could be written

Runtime failure evidence:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_runtime_failure.md`

## 6. Candidate Statuses And Runnable Set

No benchmark candidate rows were produced, so no runnable candidate set could be derived from actual outputs in Wave 4.

Per-candidate status after the failed benchmark launch:

- `zjh_lerobot_v21_raw`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_lerobot_v3_local`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_webdataset_tar`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_robodm_container_v1`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`

Runnable set:

- none derived

## 7. Exact Telemetry Jobs Attempted

No 1-GPU telemetry jobs were attempted in Wave 4.

Reason:

1. Phase B must complete first.
2. Phase B launched but failed before producing benchmark outputs.
3. Without a benchmark result set, Wave 4 could not derive the packet-required minimum telemetry matrix.

## 8. Exact Telemetry Rows Completed Vs Not Run

Completed real telemetry rows:

- none

Not-run telemetry rows:

- `zjh_lerobot_v21_raw`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_lerobot_v3_local`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_webdataset_tar`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`
- `zjh_robodm_container_v1`: `NOT_RUN_BENCHMARK_RUNTIME_BLOCKED`

## 9. Exact Scheduler / Runtime Blockers

Wave 4 scheduler blocker:

- resolved for the narrowed benchmark envelope
- no new scheduler rejection was encountered on the `a100`, `16 CPU`, `64G`, `01:00:00`, `gres=none` route

Wave 4 runtime blocker:

- exact failure:
  - `ValueError: observation.images.left_wrist_rgb must be a non-empty string`
- failing path:
  - `autovla/dataloader/stores/common.py`
  - inside `_build_source_sample(...)` while building the reduced real-data sample set
- compute evidence tail:
  - `srun: error: instance-yp83uwa1-2: task 0: Exited with exit code 1`

Interpretation:

- this is no longer a scheduler-policy blocker
- this is a real benchmark runtime/data-contract blocker encountered under the packet-authorized reduced selection
- progressing further in this wave would require source or data-contract changes, which are outside the allowed write scope

## 10. Job IDs Or Explicit `unknown_debug_wrapper_no_job_id`

- reduced benchmark run id: `autovla-m3-multiformat-store-benchmark-wave4`
- Slurm job id: `unknown_debug_wrapper_no_job_id`

The current debug-wrapper evidence records the exact `srun` command and run directory, but it does not emit a stable scheduler job id in the task-owned evidence path.

## 11. Exact Evidence Paths

Wave 4 task-owned compute evidence:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_runtime_failure.md`

Wave 4 wrapper-owned debug evidence:

- `runs/slurm_debug/autovla-m3-multiformat-store-benchmark-wave4/logs/srun_command.txt`

Wave 4 expected-but-missing benchmark outputs:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.json`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.csv`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.md`

## 12. DevSpace MCP Compliance

- DevSpace MCP used: no

## 13. Subagent Retirement Ledger

- child subagents used: none
- write-capable child subagents used: none
- no parallel write: yes
- retired: yes

## Conclusion

`FAIL`

Reason:

Wave 4 successfully overcame the Wave 3 scheduler walltime blocker by launching the reduced benchmark on the authorized narrow envelope, but the real benchmark then failed at runtime on actual data with `ValueError: observation.images.left_wrist_rgb must be a non-empty string` before any candidate rows or benchmark tables were produced. Because the benchmark did not complete, no runnable candidate set or minimum telemetry matrix could be derived in this wave without source or data-contract changes outside the allowed scope.
