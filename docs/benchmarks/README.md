# AutoVLA Benchmark Dashboards

This directory records AutoVLA decision-support dashboards. Benchmark evidence
does not authorize real training, model loading, external network use, dataset
source mutation, endpoints, or robots.

## Active Dashboards

- [Data Format Pipeline Suite](DATA_FORMAT_PIPELINE_SUITE.md)
- [Native Loader Timing Report V2](NATIVE_LOADER_TIMING_REPORT_V2.md)
- [Fair Native Loader Bakeoff V1](FAIR_NATIVE_LOADER_BAKEOFF_V1.md)
- [Fair Native Loader Bakeoff V2](FAIR_NATIVE_LOADER_BAKEOFF_V2.md)
- [PR30 Adapter Performance Audit](ADAPTER_PERFORMANCE_AUDIT_PR30.md)
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

PR #30 prior multiformat benchmark numbers are invalidated because the raw row
measured preloaded SourceSample lookup and camera_refs rather than the same
materialized native-loader payload contract used by converted candidates. The
corrected fair native-loader rerun uses worker_count=8 and identical
materialized RGB/state/action payloads for raw, local-v3, WebDataset tar, and
RoboDM-style container candidates. Its conclusion remains
`NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`. The dashboard remains
decision-support only: it does not select a final backend, claim long-training
readiness, or authorize model download, W&B/HF network use, endpoints, or robot
behavior.

PR #30 adapter audit follow-up treats the corrected fair native-loader V1 result
as the adapter-v0 baseline. The bounded adapter-v1 profiling run is diagnostic
only and records `worker_count_label=configured_8` separately from
`actual_worker_count=not_measured`. It does not run GPU200, Slurm, or training,
and it does not select a final backend winner.
