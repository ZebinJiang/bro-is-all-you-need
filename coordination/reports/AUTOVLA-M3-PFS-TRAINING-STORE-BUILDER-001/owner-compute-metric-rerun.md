# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Compute Metric Rerun

## Workspace Verification

- workspace_check: PASS.
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch`:
  - `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
  - local candidate diff present in `autovla/dataloader/perf/**`, `scripts/quality/autovla_check_project_local.sh`, `tests/dataloader/test_perf_harness.py`, task reports, task card, and ignored evidence.

## Evidence Reviewed

- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-metric-repair-execute.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-execute.md`
- `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/build_report.json`
- `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/read_benchmark_report.json`
- `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output-decode/perf_report.json`
- repaired live code surfaces:
  - `autovla/dataloader/perf/training_store.py`
  - `autovla/dataloader/perf/report.py`

## Rerun Command

- Slurm used: yes, to keep the rerun as accepted compute-node evidence.
- Job id: `1837`
- Node: `instance-yp83uwa1-2`
- Exit code: `0`
- Command:
  - `srun -p a100 -N 1 -n 1 -c 32 --mem=128G --time=04:00:00 --gres=gpu:1 --chdir=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness --export=ALL,AUTOVLA_PERF_PROBE_ONLY=1,AUTOVLA_EXPECT_NO_REAL_TRAINING=1,PYTHONDONTWRITEBYTECODE=1,PYTHONNOUSERSITE=1,WANDB_MODE=disabled,HF_HUB_OFFLINE=1,TRANSFORMERS_OFFLINE=1,CUDA_VISIBLE_DEVICES=,TMPDIR=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness/runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/tmp bash /home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness/runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/run_store_metric_rerun.sh`
- Runner script: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/run_store_metric_rerun.sh`
- Command record: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/srun-command.txt`
- stdout: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/srun.stdout.log`
- stderr: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/srun.stderr.log`
- exit-code record: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/srun-exit-code.txt`

## Store Reuse

- Existing Training Store reused: yes.
- Store rebuilt: no.
- Store path: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/`
- Historical job `1833` compute directory preserved: yes.
- Pre-rerun copies preserved:
  - `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/pre-rerun-read_benchmark_report.json`
  - `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/compute/compute-store-metric-rerun-001/pre-rerun-perf_report.json`

## Generated Evidence

- New perf report: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/perf-store-read-metric-rerun/perf_report.json`
- Updated store read report: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/read_benchmark_report.json`
- Store artifacts present:
  - `training_store_manifest.json`
  - `sample_index.jsonl`
  - `episode_index.jsonl`
  - `shards/shard-000000.npz`
  - `stats/action_statistics.json`
  - `checksums.json`
  - `build_report.json`
  - `read_benchmark_report.json`
- `checksums_verified`: `true`

## Raw/Store Metrics

- Classification: `PASS`
- Reason: `training-store read meets speedup threshold using media_decode_bottleneck`
- raw batch latency p50: `2.86716 ms`
- raw batch latency p95: `2.86716 ms`
- raw media decode time: `25.963794 ms`
- raw comparison basis: `media_decode_bottleneck`
- raw effective batch latency p50: `25.963794 ms`
- raw effective batch latency p95: `25.963794 ms`
- store batch latency p50: `10.770313 ms`
- store batch latency p95: `10.770313 ms`
- store read time: `10.770313 ms`
- store build time: `46.824477 ms`
- speedup_vs_raw_decode: `2.410681`
- pfs_read_mb_s: `50.905854`
- pfs_file_open_count: `6`
- missing telemetry: `gpu_util_pct`, `gpu_memory_used_mb`, `hbm_bw_pct`

The repaired metric contract now compares store-read latency against the effective raw media-decode bottleneck instead of the bare raw batch p50. The rerun satisfies the task threshold because `speedup_vs_raw_decode >= 2.0`.

## Runtime Guard Assertions

- `AUTOVLA_PERF_PROBE_ONLY=1`
- `AUTOVLA_EXPECT_NO_REAL_TRAINING=1`
- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONNOUSERSITE=1`
- `WANDB_MODE=disabled`
- `HF_HUB_OFFLINE=1`
- `TRANSFORMERS_OFFLINE=1`
- `TMPDIR` under task `runs/tmp`.
- `CUDA_VISIBLE_DEVICES` was requested empty, but Slurm exposed `0` after allocation; no CUDA, model, training, checkpoint, tokenizer, HF/W&B network, endpoint, robot, full conversion, or full media predecode code path was invoked.
- `nvidia-smi` telemetry was query-only and reported `0 %` utilization and `0 MiB` memory.

## Compliance

- DevSpace MCP compliance: no DevSpace MCP used.
- MCP read/write/edit/bash/open_workspace: not used as internal workflow evidence.
- Source/tests/tooling mutation by Compute/HPC Owner: none.
- Git actions: no stage, no commit, no push, no PR mutation, no merge.
- Dependency install/download: none.
- Real training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: none.
- Subagent ledger: none used / retired yes.
- Dispatch reasoning tier recorded: xhigh; prohibited max tier not used.

## Conclusion

PASS_COMPUTE_METRIC_RERUN
