# GR00T GPU200 Multiformat Telemetry Surface

This document records the bounded GR00T-N1D6 GPU200 multiformat telemetry
evidence for `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`. Wave 11
completed the required bounded 200-step compute telemetry for the two required
candidates, `zjh_lerobot_v21_raw` and `zjh_lerobot_v3_local`, both with
return code 0.

This is decision-support telemetry only. It does not select a final backend,
authorize long training, prove model quality, authorize model download, use
Hugging Face network access, enable W&B online sync, expose an endpoint, or
authorize robot behavior.

## Scope

- model family: `gr00t-n1d6`
- datastore candidates: bounded raw/v3 telemetry plus load-only context rows
- bounded step budget: `200`
- dataloader workers for Wave 11 telemetry: `0`
- environment profile: `model-gr00t-n1d6`
- output root: governed task-local evidence under `runs/tmp/**`

## Candidate Status

| Candidate | Load status | Load p50 ms | Load p95 ms | Load samples/s | Telemetry disposition | Runtime s | Steps/s | Train loss | Notes |
| --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |
| `zjh_lerobot_v21_raw` | `PASS` | 0.558771 | 0.666286 | 443067.935066 | `PASS_200_STEP_TELEMETRY` | 88.1449 | 2.269 | 1.128048825263977 | Read-only raw ZJH / LeRobot v2.1 baseline. |
| `zjh_lerobot_v3_local` | `PASS` | 9.656905 | 10.643553 | 26189.024899 | `PASS_200_STEP_TELEMETRY` | 88.8496 | 2.251 | 1.1281476402282715 | AutoVLA-native local LeRobot v3-style artifact and reader. |
| `zjh_webdataset_tar` | `PASS` | 16.46985 | 19.481412 | 17788.371575 | `NOT_RUN_MINIMUM_MATRIX_SECOND_BEST_OUTSIDE_10_PERCENT` | missing | missing | missing | Load benchmark context only; not selected for the minimum Wave 11 telemetry set. |
| `zjh_robodm_container_v1` | `PASS` | 69.043836 | 86.930216 | 3514.775909 | `NOT_RUN_MINIMUM_MATRIX_RANKED_BELOW_REQUIRED_SET` | missing | missing | missing | AutoVLA-owned RoboDM-style prototype container; not actual Robo-DM package support. |

## Evidence Paths

| Evidence | Path |
| --- | --- |
| Wave 8 load benchmark JSON | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.json` |
| Wave 8 load benchmark Markdown | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.md` |
| Wave 11 raw bridge result | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/raw/outputs/bridge_runtime_result.json` |
| Wave 11 raw stdout metrics | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/raw/logs/autovla-m3-multiformat-gpu200-wave11-raw.stdout.log` |
| Wave 11 v3 bridge result | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/zjh_lerobot_v3_local/outputs/bridge_runtime_result.json` |
| Wave 11 v3 stdout metrics | `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/zjh_lerobot_v3_local/logs/autovla-m3-multiformat-gpu200-wave11-zjh-lerobot-v3-local.stdout.log` |

## Wave 11 Output Surface

Wave 11 writes the bounded runtime evidence listed in the evidence table above:
`bridge_runtime_result.json`, stdout/stderr logs, experiment configuration,
processor artifacts, and the task-local `checkpoint-200/**` runtime output.
The numeric runtime, steps-per-second, and loss values in this document come
from those Wave 11 bridge result and stdout files.

The structured `telemetry_*` tables and manifests are a future reporting
contract for a later telemetry packaging tranche. They were not emitted by Wave
11 and are not required to interpret the current bounded 200-step evidence.

## Numeric Table Feed

README and future benchmark rollups should consume PR-visible numeric summaries
instead of raw log text. Missing telemetry stays explicit as `missing`, never
inferred. The Wave 11 telemetry values above come from the task-local stdout
logs and bridge result JSON files, not from a new Data-side compute run.

## Current Boundary

- real dataset remains unchanged
- no raw log paste into docs
- no W&B online sync claim
- no HF network or model download
- no endpoint or robot behavior
- no long training readiness or model-quality claim from bounded 200-step
  telemetry
- no final backend winner or training format selected by this table
- generated checkpoints and run outputs remain task-local evidence and must not
  be staged or committed
