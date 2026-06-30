# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Compute Execution

## Workspace Verification

- Result: PASS.
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- status: local candidate diff present in perf harness/source tests plus ignored/report evidence; no git stage/commit/PR mutation performed.

## Execution Summary

- New compute job: `1833`
- Node: `instance-yp83uwa1-2`
- Exit status: `0`
- Resource command: `srun -p a100 -N 1 -n 1 -c 32 --mem=128G --time=04:00:00 --gres=gpu:1 --chdir=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness --export=ALL,AUTOVLA_PERF_PROBE_ONLY=1,AUTOVLA_EXPECT_NO_REAL_TRAINING=1,PYTHONDONTWRITEBYTECODE=1,PYTHONNOUSERSITE=1,WANDB_MODE=disabled,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,CUDA_VISIBLE_DEVICES=,TMPDIR=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness/runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/tmp bash /home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness/runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-builder-001/run_store_builder_compute.sh`
- Command record: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-builder-001/srun-command.txt`
- stdout: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-builder-001/srun.stdout.log`
- stderr: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-builder-001/srun.stderr.log`
- exit-code record: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-builder-001/srun-exit-code.txt`

## Runtime Guards

- `AUTOVLA_PERF_PROBE_ONLY=1`
- `AUTOVLA_EXPECT_NO_REAL_TRAINING=1`
- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONNOUSERSITE=1`
- `WANDB_MODE=disabled`
- `HF_HUB_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`
- `TMPDIR` governed under task `runs/tmp`.
- Slurm exposed `CUDA_VISIBLE_DEVICES=0` after allocation despite empty export request; no CUDA or model path was invoked. `nvidia-smi` telemetry reported `0 %` GPU utilization and `0 MiB` memory.

## Evidence Produced

- Raw bounded-decode baseline: reused existing report `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output-decode/perf_report.json` from Slurm job `1824`; no raw rerun was needed.
- Store build output: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/perf-store-build/perf_report.json`
- Store read output: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/perf-store-read/perf_report.json`
- Training store root: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/`
- Evidence-only raw baseline stitching: updated ignored `training-store/build_report.json` with preserved raw p50/p95/media decode values before the read benchmark.

## Store Artifact Check

Present:

- `training_store_manifest.json`
- `sample_index.jsonl` with `512` rows
- `episode_index.jsonl` with `4` rows
- `shards/shard-000000.npz` at `179K`
- `stats/action_statistics.json`
- `checksums.json`
- `build_report.json`
- `read_benchmark_report.json`

`read_benchmark_report.json` reports `checksums_verified: true`.

## Raw/Store Metrics

- raw classification: `FAIL`
- raw batch latency p50: `2.86716 ms`
- raw batch latency p95: `2.86716 ms`
- raw media decode time: `25.963794 ms`
- store classification: `FAIL`
- store batch latency p50: `9.233619 ms`
- store batch latency p95: `9.233619 ms`
- store read time: `9.233619 ms`
- store build time: `46.824477 ms`
- speedup_vs_raw_decode: `0.310513`
- pfs_read_mb_s: `56.975636`
- pfs_file_open_count: `6`
- missing telemetry: `gpu_util_pct`, `gpu_memory_used_mb`, `hbm_bw_pct`, `raw_batch_latency_ms_p50`, `raw_media_decode_time_ms`

Acceptance recommendation: FAIL. The store read path is not materially faster than the preserved raw p50 and misses the required threshold of `store p50 <= 0.5 * raw p50` or `speedup >= 2.0`.

## Safety Assertions

- No real training, model load, checkpoint load, tokenizer load, HF/W&B network, endpoint, robot action, full dataset conversion, or full media predecode was performed.
- Source dataset remained read-only; generated artifacts were written only under ignored task evidence.
- One compute job was used in this execution, within the max compute job budget of `3`.
- DevSpace MCP: no.
- Source/test/tooling/git/PR mutation by Compute/HPC Owner: none.
- Subagents: none used; retired=yes.
- Dispatch reasoning tier recorded: xhigh; prohibited tier not used.

## Conclusion

FAIL_COMPUTE
