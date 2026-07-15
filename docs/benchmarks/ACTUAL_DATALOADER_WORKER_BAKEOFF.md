# PR30 Actual Dataloader Worker Bakeoff

This page records the PR #30 replacement benchmark surface for actual
dataloader/native-loader worker evidence. It supersedes adapter-only timing as
backend-comparison evidence. The bounded Compute-W2 run completed on the real
readonly source dataset, but the generated decision remains request-changes
because D1 and prompt-contract metric gaps are still open.

## Status

- implementation surface: `autovla.dataloader.perf.actual_dataloader_worker_bakeoff`
- local evidence mode: tiny fixture for Data validation; source-dataset evidence
  produced by Compute-W2
- compute evidence: Compute-W2 completed the primary matrix and secondary worker
  sweep with exit code 0 through the project wrapper
- decision status: `REQUEST_CHANGES_REMAIN` / `NO_BACKEND_WINNER`
- publication decision label:
  `NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS`
- final backend winner: not selected
- training format: not selected
- GPU200, training, model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not run
- Slurm: used only for bounded dataloader benchmark evidence through the
  project wrapper

## Compute-W2 Evidence

Compute-W2 ran the actual-worker scaffold on the real readonly source dataset
through the project wrapper.

- job id: `2488`
- node: `instance-yp83uwa1-1`
- partition: `a100`
- CPUs: `16`
- memory: `128G`
- GRES: `none`
- primary matrix: worker_count `8`, batch_size `8`, warmup `10`, measured `100`,
  repeats `3`, max_samples `4096`, max_episodes `32`
- secondary sweep: worker_count `0,2,4,8`, batch_size `8`, warmup `5`,
  measured `50`, repeats `2`, max_samples `2048`, max_episodes `16`
- source mutation proof: before/after hash matched
  `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`
- primary evidence root:
  `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/`

This is still not final benchmark PASS evidence:

- D1 remains `BLOCKED_NATIVE_V21_DATALOADER_UNAVAILABLE` /
  `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.
- D6 remains `NOT_IMPLEMENTED_IN_CURRENT_PR`.
- Persistent-worker and prefetch-factor matrix coverage is missing.
- Several prompt-contract stage metrics remain defaulted and are represented in
  `missing_telemetry_table` as blocking for final benchmark pass.
- No backend winner or training format is selected.

## Compute-W2 Primary Ranking

| Rank | Label | Candidate | Status | Actual workers | Samples | total_batch_ms | samples_per_sec |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | D4 | `zjh_webdataset_tar` | `RUN` / `PASS` | 8 | 4096 | 8163.014375 | 501.775424 |
| 2 | D5 | `zjh_robodm_container_v1` | `RUN` / `PASS` | 8 | 4096 | 13883.202613 | 295.03279 |
| 3 | D3 | `zjh_lerobot_v3_local` | `RUN` / `PASS` | 8 | 4096 | 20175.055925 | 203.022981 |
| 4 | D1b/D2 | `zjh_lerobot_v21_autovla_adapter` | `RUN` / `PASS` | 8 | 4096 | 165212.583614 | 24.7923 |
| not ranked | D1a | `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | not_applicable | 0 | not_applicable | not_applicable |
| optional | D6 | `zjh_zarr_cache` | `NOT_IMPLEMENTED_IN_CURRENT_PR` | not_applicable | 0 | not_applicable | not_applicable |

The ranking above is the final bounded runnable-candidate ordering for PR #30.
It is not a final backend winner because the decision table remains
`NO_BACKEND_WINNER`.

## Candidate Matrix

| Label | Candidate | Status policy |
| --- | --- | --- |
| D1a | `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` unless a safe native route exists without runtime/model side effects |
| D1b/D2 | `zjh_lerobot_v21_autovla_adapter` | actual-worker adapter row required |
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

## Generated Evidence Policy

Task-local benchmark outputs remain generated evidence under:

`runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/`

Generated working artifacts remain under:

`datasets/working/autovla_pr30_final_dataloader_perf_v1/w2`

Those files are generated evidence only and must not be tracked as product
source.
