# Fair Native Loader Bakeoff V2

Fair Native Loader Bakeoff V2 is the bounded PR #30 adapter-v1 diagnostic rerun.
It uses the existing corrected fair native-loader V1 result as adapter-v0
baseline and writes adapter stage tables for reader/profiler analysis.

This report is not GPU200 evidence and does not choose a final backend.

## Evidence Path

`runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun`

Key files:

- `fair-native-loader-bakeoff.json`
- `adapter_stage_timing_v0.json`
- `adapter_stage_timing_v1.json`
- `adapter_v0_vs_v1_summary.json`
- `adapter_bottleneck_table.json`
- `backend_decision_status.md`
- `generated-artifact-ledger.json`
- `shared-sample-window-manifest.json`

## Scope

- source dataset: readonly ZJH / LeRobot v2.1 source
- generated working root:
  `datasets/working/autovla_fair_native_loader_bakeoff_v2`
- bounded sample count: 128
- worker_count_label: `configured_8`
- actual_worker_count: `not_measured`
- multiprocessing_enabled: `false`
- prefetch_enabled: `false`
- no GPU200, Slurm, training, model load, checkpoint, tokenizer, W&B/HF, endpoint,
  or robot behavior

## Candidate Results

| Candidate | Adapter | Native loader | p50 ms | p95 ms | Samples/s | Persistent reader |
| --- | --- | --- | ---: | ---: | ---: | --- |
| `zjh_lerobot_v21_raw` | `adapter_v1` | `autovla_lerobot_v21_native_ffmpeg_materialized_reader` | 1011.893106 | 1085.541792 | 6.429297 | false |
| `zjh_lerobot_v3_local` | `adapter_v1` | `autovla_lerobot_v3_local_materialized_parquet_reader` | 0.091163 | 0.097437 | 67790.542926 | true |
| `zjh_webdataset_tar` | `adapter_v1` | `autovla_webdataset_tar_materialized_streaming_reader` | 0.154350 | 0.165612 | 39933.333567 | true |
| `zjh_robodm_container_v1` | `adapter_v1` | `autovla_robodm_style_materialized_container_reader` | 0.101197 | 0.114727 | 62410.635260 | true |

## Decision

`NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`

Adapter-v1 is diagnostic only. The persistent converted readers show that the
previous corrected result included substantial AutoVLA adapter/reader overhead,
but this bounded rerun is not a final backend-selection or training-readiness
claim.
