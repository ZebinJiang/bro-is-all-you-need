# Fair Native Loader Bakeoff V1

This dashboard replaces the invalidated PR #30 multiformat benchmark numbers.
The prior table compared preloaded `SourceSample` lookup and `camera_refs`
against disk-backed converted candidates, so it is not valid for backend
selection.

The corrected rerun uses the same selected sample/window manifest across all
candidates with worker_count=8, batch_size=8, 2048 samples, and materialized
RGB/state/action payloads.

## Corrected Results

| Candidate | Native loader | Workers | Batch | Samples | p50 ms | p95 ms | p99 ms | Samples/s | Frames/s | Conversion s | Artifact GB | Payload complete | Status | Recommendation |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `zjh_lerobot_v21_raw` | `autovla_lerobot_v21_native_ffmpeg_materialized_reader` | 8 | 8 | 2048 | 1412.945935 | 1649.215997 | 2093.333878 | 5.437251 | 16.311753 | 0.0 | 6e-07 | `True` | `RUNNABLE_NOW` | `native_raw_baseline_context` |
| `zjh_lerobot_v3_local` | `autovla_lerobot_v3_local_materialized_parquet_reader` | 8 | 8 | 2048 | 43.912011 | 49.341909 | 54.92134 | 174.028064 | 522.084193 | 367.683332 | 1.211325296 | `True` | `RUNNABLE_NOW` | `compare_against_raw_native_before_selection` |
| `zjh_webdataset_tar` | `autovla_webdataset_tar_materialized_streaming_reader` | 8 | 8 | 2048 | 224.916599 | 395.097018 | 426.476422 | 36.113377 | 108.34013 | 364.576253 | 1.221707328 | `True` | `RUNNABLE_NOW` | `compare_against_raw_native_before_selection` |
| `zjh_robodm_container_v1` | `autovla_robodm_style_materialized_container_reader` | 8 | 8 | 2048 | 158.422529 | 182.784043 | 201.11354 | 47.459339 | 142.378016 | 366.478184 | 1.217494455 | `True` | `RUNNABLE_NOW` | `compare_against_raw_native_before_selection` |

Current conclusion: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

No final backend winner is selected by this table alone.

## Evidence Paths

The corrected compute run wrote task-local evidence under:

`runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark`

Key evidence files:

- `fair-native-loader-bakeoff.json`
- `fair-native-loader-bakeoff.csv`
- `fair-native-loader-bakeoff.md`
- `generated-artifact-ledger.json`
- `shared-sample-window-manifest.json`

Generated candidate stores are ignored artifacts under:

`datasets/working/autovla_fair_native_loader_bakeoff_v1`

## Contract

Each candidate row includes p50/p95/p99 batch latency, samples/s, frames/s,
loader-init time, conversion time, artifact size, generated file count,
file-open count, read throughput, CPU/RSS fields, payload-completeness proof,
and no external-effect evidence.

## Boundary

- no final backend winner
- no long-training readiness claim
- no model-quality claim
- no source dataset mutation
- no generated artifacts committed as product source
- no training, model load, checkpoint download, W&B/HF network use, endpoint, or
  robot behavior
