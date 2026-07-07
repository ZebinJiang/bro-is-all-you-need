# PR30 Actual Dataloader Worker Bakeoff

This page records the PR #30 replacement benchmark surface for actual
dataloader/native-loader worker evidence. It supersedes adapter-only timing as a
future compute input, but it is not final backend evidence until Compute/HPC runs
the real source-dataset benchmark.

## Status

- implementation surface: `autovla.dataloader.perf.actual_dataloader_worker_bakeoff`
- local evidence mode: tiny fixture only
- compute evidence: Compute-W1R completed worker counts `0,2,4,8` for D2-D5 with
  request-changes blockers still open
- decision status: `REQUEST_CHANGES_REMAIN` / `NO_BACKEND_WINNER`
- final backend winner: not selected
- training format: not selected
- GPU200, Slurm, training, model/checkpoint/tokenizer/HF/W&B/endpoint/robot:
  not run by Data-W1R

## Compute-W1R Evidence

Compute-W1R ran the actual-worker scaffold on the real readonly source dataset
through the project wrapper. Worker counts `0,2,4,8` completed with exit code 0
for D2-D5 and recorded numeric actual worker counts, process evidence, and
per-worker sample counts.

This is still not final benchmark PASS evidence:

- D1 remains `BLOCKED_NATIVE_V21_DATALOADER_UNAVAILABLE` /
  `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.
- D6 remains `NOT_IMPLEMENTED_IN_CURRENT_PR`.
- Persistent-worker and prefetch-factor matrix coverage is missing.
- Several prompt-contract stage metrics remain defaulted and are represented in
  `missing_telemetry_table` as blocking for final benchmark pass.
- No backend winner or training format is selected.

## Candidate Matrix

| Label | Candidate | Status policy |
| --- | --- | --- |
| D1 | `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` unless a safe native route exists without runtime/model side effects |
| D2 | `zjh_lerobot_v21_autovla_adapter` | actual-worker adapter row required |
| D3 | `zjh_lerobot_v3_local` | actual-worker local-v3 row required |
| D4 | `zjh_webdataset_tar` | actual-worker WebDataset tar row required |
| D5 | `zjh_robodm_container_v1` | actual-worker owned RoboDM-style prototype row required |
| D6 | `zjh_zarr_cache` | optional; `NOT_IMPLEMENTED_IN_CURRENT_PR` when absent |

RUN rows must include numeric worker evidence: requested worker count, actual
worker count, worker ids or process ids, per-worker sample counts, execution
mode, and PASS/BLOCKED worker-count evidence status.

## Payload Contract

RUN rows must collate a `BenchmarkBatch` with:

- action
- state when available
- language
- action mask
- sample, episode, and window ids
- three RGB payloads as bytes or arrays
- deterministic payload hash

Camera-reference-only, proof-only, or preloaded `SourceSample` rows are not
acceptable as RUN evidence.

## Local Evidence

Data-W1R may generate tiny fixture artifacts under:

`runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/`

Tiny generated working artifacts may be written under:

`datasets/working/autovla_actual_worker_bakeoff_v1/`

Those files are generated evidence only and must not be tracked as product
source. Full source-dataset execution remains a later Compute/HPC responsibility.
