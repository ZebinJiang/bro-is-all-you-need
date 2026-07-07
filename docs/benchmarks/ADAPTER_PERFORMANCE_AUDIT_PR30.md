# PR30 Adapter Performance Audit

This dashboard records the bounded PR #30 adapter audit after the corrected fair
native-loader result was reclassified as the adapter-v0 baseline.

The audit is diagnostic only. It does not select a final backend winner, does
not authorize GPU200 training, does not run Slurm, and does not load a model,
checkpoint, tokenizer, Hugging Face asset, W&B service, endpoint, or robot.

## Decision Status

`NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`

No converted backend is selected as winner. The corrected fair native-loader V1
result remains adapter-v0 baseline evidence. The bounded adapter-v1 profiling
run isolates AutoVLA adapter/reader overhead, but it is not final backend
selection evidence.

The replacement evidence path is the actual dataloader worker benchmark:
`docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`. That surface must record
numeric `actual_worker_count`, worker ids/process ids, and per-worker sample
counts before Compute/HPC can treat rows as comparable backend evidence.

## Compute-W1R Follow-Up

Compute-W1R produced wrapper-backed readonly-source evidence for worker counts
`0,2,4,8` with D2-D5 completing and matching requested worker counts. That result
updates the execution provenance, but it does not turn this audit into backend
selection evidence. D1 remains unavailable/blocked, D6 remains not implemented,
and the prompt-contract timing matrix is incomplete.

## Evidence

Task-local evidence root:

`runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun`

Generated files:

- `adapter_stage_timing_v0.json`, `.csv`, `.md`
- `adapter_stage_timing_v1.json`, `.csv`, `.md`
- `adapter_v0_vs_v1_summary.json`, `.csv`, `.md`
- `adapter_bottleneck_table.json`, `.csv`, `.md`
- `backend_decision_status.md`
- `fair-native-loader-bakeoff.json`, `.csv`, `.md`
- `generated-artifact-ledger.json`
- `shared-sample-window-manifest.json`

Generated working artifacts are under:

`datasets/working/autovla_fair_native_loader_bakeoff_v2`

Those artifacts are generated evidence only and are not tracked publication
artifacts.

## Adapter-v0 vs Adapter-v1 Summary

Adapter-v0 values are the corrected fair native-loader V1 baseline. Adapter-v1
values are from the bounded 128-sample diagnostic rerun. The worker count column
is a configured label only; `actual_worker_count=not_measured` is explicit and
must not be read as actual eight-worker execution evidence.

| Candidate | v0 p50 ms | v0 p95 ms | v0 samples/s | v1 p50 ms | v1 p95 ms | v1 samples/s | worker_count_label | actual_worker_count | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `zjh_lerobot_v21_raw` | 1412.945935 | 1649.215997 | 5.437251 | 1011.893106 | 1085.541792 | 6.429297 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_lerobot_v3_local` | 43.912011 | 49.341909 | 174.028064 | 0.091163 | 0.097437 | 67790.542926 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_webdataset_tar` | 224.916599 | 395.097018 | 36.113377 | 0.154350 | 0.165612 | 39933.333567 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_robodm_container_v1` | 158.422529 | 182.784043 | 47.459339 | 0.101197 | 0.114727 | 62410.635260 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |

## Stage Bottleneck Summary

The bounded adapter-v1 run reports `materialize_payload` as the largest stage for
all four candidates. This means the audit is primarily useful for separating
adapter/reader overhead from RGB materialization and report generation, not for
choosing a final backend.

| Candidate | Adapter | Bottleneck stage | total_ms | Notes |
| --- | --- | --- | ---: | --- |
| `zjh_lerobot_v21_raw` | `adapter_v1` | `materialize_payload` | 9954.433 | raw ffmpeg-per-frame cost is recorded separately |
| `zjh_lerobot_v3_local` | `adapter_v1` | `materialize_payload` | 17427.915 | materialized RGB/action/state/action_mask payloads |
| `zjh_webdataset_tar` | `adapter_v1` | `materialize_payload` | 17284.160 | materialized RGB/action/state/action_mask payloads |
| `zjh_robodm_container_v1` | `adapter_v1` | `materialize_payload` | 17603.804 | materialized RGB/action/state/action_mask payloads |

## Boundary

- no final backend winner
- no GPU200 or Slurm run in this Data follow-up
- no real training
- no model/checkpoint/tokenizer load
- no W&B/HF network use
- no endpoint or robot behavior
- no source dataset mutation
- no generated artifact committed as product source
