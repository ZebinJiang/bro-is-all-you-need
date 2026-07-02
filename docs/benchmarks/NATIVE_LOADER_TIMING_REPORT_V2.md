# Native Loader Timing Report V2

## Decision

- Decision class: `SELECT_WEBDATASET_NATIVE`
- Recommended winner: `webdataset_converted`
- Confidence: `MEDIUM`
- Raw baseline: `zjh_lerobot_v21_raw`
- p50 speedup vs raw: `6.396852`
- sample throughput speedup vs raw: `6.394769`

`webdataset_converted` is the recommended backend for the next productionization task because it is runnable now, has a complete materialized BenchmarkPayload, records concrete timing metrics, has no model/checkpoint/training side effect, and beats the raw path on both p50 batch latency and samples/sec.

## Scope And Evidence

- Task: `AUTOVLA-M3-NATIVE-LOADER-TIMING-REPORT-V2-001`
- Source dataset: `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- Working root: `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_native_loader_timing_v2`
- Compute log: `runs/tmp/AUTOVLA-M3-NATIVE-LOADER-TIMING-REPORT-V2-001/compute/srun-native-loader-timing.log`
- Slurm job id: `2098`
- Node: `instance-yp83uwa1-1`
- CPU allocation evidence: `32`
- GPU telemetry: captured only for allocation visibility; benchmark ran with no model/training path.
- Training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not used.
- PR #16: not mutated.

## Candidate List And Dependency Status

| Candidate | Status | Native loader | Timing source | Dependency status |
| --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | `RUNNABLE_NOW` | `raw_zjh_lerobot_v21_ffmpeg_materialized_reader` | `source_parquet_ffmpeg` | runnable now |
| `lerobot_v3_converted` | `NOT_RUN_DEPENDENCY_BLOCKED` | `not-run` | `not-run` | official LeRobot v3 dependency/conversion route is not separately approved |
| `webdataset_converted` | `RUNNABLE_NOW` | `webdataset_rgb_materialized_streaming_reader` | `converted_webdataset_artifact` | runnable now |
| `robodm_style_converted` | `RUNNABLE_NOW` | `autovla_owned_robodm_style_rgb_materialized_reader` | `converted_robodm_style_artifact` | runnable now |
| `zarr_converted` | `NOT_RUN_DEPENDENCY_BLOCKED` | `not-run` | `not-run` | actual Zarr dependency/version decision is missing |

## Batch Timing Table

| Candidate | batch_size | samples | episodes | first ms | p50 ms | p95 ms | max ms | total s |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | 1 | 512 | 2 | 156.936022 | 171.072641 | 189.900773 | 193.30709 | 26.39405 |
| `webdataset_converted` | 1 | 512 | 2 | 3.057801 | 26.743256 | 50.360388 | 53.31062 | 4.127444 |
| `robodm_style_converted` | 1 | 512 | 2 | 29.655654 | 30.076333 | 38.863741 | 44.162897 | 4.791056 |

## Throughput And Conversion Table

| Candidate | samples/s | frames/s | batches/s | conversion s | artifact GB | files |
| --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | 5.683099 | 17.049297 | 5.683099 | 0 | 0.002247 | 2 |
| `webdataset_converted` | 36.342106 | 109.026318 | 36.342106 | 94.878337 | 0.307656 | 4 |
| `robodm_style_converted` | 31.308339 | 93.925017 | 31.308339 | 94.163871 | 0.306613 | 1540 |

## Payload Completeness Table

| Candidate | action | language | state | mask | RGB cams | payload_missing_fields | hash |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `zjh_lerobot_v21_raw` | yes | yes | yes | yes | 3 | [] | yes |
| `webdataset_converted` | yes | yes | yes | yes | 3 | [] | yes |
| `robodm_style_converted` | yes | yes | yes | yes | 3 | [] | yes |

Every RUN row has action, language, state, action_mask, all three RGB camera payloads materialized into batch memory, and a deterministic payload hash. RUN rows have concrete core timing values and empty `missing_metrics`.

## Not-Run Reasons

| Candidate | Classification | Reason |
| --- | --- | --- |
| `lerobot_v3_converted` | `NOT_RUN_DEPENDENCY_BLOCKED` | official LeRobot v3 dependency/conversion route is not separately approved |
| `zarr_converted` | `NOT_RUN_DEPENDENCY_BLOCKED` | actual Zarr dependency/version decision is missing |

## Generated Artifact Ledger

- Working artifacts root: `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_native_loader_timing_v2`
- Ledger entries: `1548`
- Tracked statuses: `ignored_generated_artifact`
- Generated artifacts staged/tracked: `false`
- Root aggregate ledger: `runs/tmp/AUTOVLA-M3-NATIVE-LOADER-TIMING-REPORT-V2-001/generated-artifact-ledger.json`

## Limitations

- Batch size was fixed at `1` as the largest safe common value across the raw ffmpeg materializer and converted artifact readers.
- The bounded run used `max_samples=512`; the observed timed set contains `512` samples from `2` episodes.
- `robodm_style_converted` is an AutoVLA-owned prototype artifact reader, not upstream Robo-DM package support.
- `lerobot_v3_converted` and `zarr_converted` remain dependency-blocked and were not timed as runnable rows.

## Next Action

Productionize `webdataset_converted` behind a scoped follow-up task, with the current raw LeRobot v2.1 path retained as the telemetry baseline.
