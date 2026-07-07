# AutoVLA Benchmark Dashboards

This directory records AutoVLA decision-support dashboards. Benchmark evidence
does not authorize real training, model loading, external network use, dataset
source mutation, endpoints, or robots.

## Active Dashboards

- [Data Format Pipeline Suite](DATA_FORMAT_PIPELINE_SUITE.md)
- [Native Loader Timing Report V2](NATIVE_LOADER_TIMING_REPORT_V2.md)
- [Data Pipeline Backend Bakeoff](DATA_PIPELINE_BACKEND_BAKEOFF.md)
- [GR00T GPU200 Multiformat Telemetry Surface](GR00T_GPU200_MULTIFORMAT_TELEMETRY.md)

## Current Data-Format Direction

PR #19 selected WebDataset-native as the fastest measured candidate, while
Robo-DM-style remained close enough to keep as a first-class AutoVLA-owned
candidate. Raw ZJH / LeRobot v2.1 remains the source baseline. LeRobot v3
remains a required comparison route and must be represented either by a real
approved local route or by an explicit dependency-blocked decision.

Final backend selection is deferred to the next formal telemetry stage. Generated
format stores, shards, containers, media payloads, and run outputs remain ignored
artifacts under `datasets/working/**` and `runs/tmp/**`.

The GR00T GPU200 multiformat tranche now includes bounded Wave 11 200-step
telemetry evidence for `zjh_lerobot_v21_raw` and `zjh_lerobot_v3_local`, both
with return code 0 and `dataloader_num_workers=0`. WebDataset tar and
RoboDM-style container rows remain load-benchmark context in this tranche, not
selected telemetry candidates. The dashboard remains decision-support only: it
does not select a final backend, claim long-training readiness, or authorize
model download, W&B/HF network use, endpoints, or robot behavior.
