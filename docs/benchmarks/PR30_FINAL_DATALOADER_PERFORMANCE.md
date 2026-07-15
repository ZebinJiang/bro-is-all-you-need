# PR30 Final Dataloader Performance Evidence

This page normalizes the bounded Compute-W2 result for PR #30. It records the
final runnable-candidate ranking for this task, not a final backend winner.

## Decision

- benchmark evidence status: `REQUEST_CHANGES_REMAIN`
- backend decision: `NO_BACKEND_WINNER`
- publication decision label:
  `NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS`
- training format selected: no
- fine-tune/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: no
- deployment/production readiness: no

The runnable converted candidates have numeric bounded dataloader performance,
but D1a is still `NOT_RUN_UNSAFE_OR_UNAVAILABLE`, D6 is optional and not
implemented, and prompt-contract missing telemetry remains blocking.

## Compute-W2 Matrix

- job id: `2488`
- node: `instance-yp83uwa1-1`
- partition: `a100`
- CPUs: `16`
- memory: `128G`
- GRES: `none`
- time limit: `04:00:00`
- execution route: project Slurm wrapper
- primary matrix: worker_count `8`, batch_size `8`, warmup `10`, measured `100`,
  repeats `3`, max_samples `4096`, max_episodes `32`
- secondary sweep: worker_count `0,2,4,8`, batch_size `8`, warmup `5`,
  measured `50`, repeats `2`, max_samples `2048`, max_episodes `16`

Source dataset:

`/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`

Source mutation proof:

- before hash: `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`
- after hash: `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`
- result: source dataset unchanged

## Primary Runnable Ranking

| Rank | Label | Candidate | Status | Worker evidence | Samples | Actual workers | total_batch_ms | samples_per_sec |
| ---: | --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | D4 | `zjh_webdataset_tar` | `RUN` | `PASS` | 4096 | 8 | 8163.014375 | 501.775424 |
| 2 | D5 | `zjh_robodm_container_v1` | `RUN` | `PASS` | 4096 | 8 | 13883.202613 | 295.03279 |
| 3 | D3 | `zjh_lerobot_v3_local` | `RUN` | `PASS` | 4096 | 8 | 20175.055925 | 203.022981 |
| 4 | D1b/D2 | `zjh_lerobot_v21_autovla_adapter` | `RUN` | `PASS` | 4096 | 8 | 165212.583614 | 24.7923 |
| not ranked | D1a | `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | 0 | not_applicable | not_applicable | not_applicable |
| optional | D6 | `zjh_zarr_cache` | `NOT_IMPLEMENTED_IN_CURRENT_PR` | `NOT_IMPLEMENTED_IN_CURRENT_PR` | 0 | not_applicable | not_applicable | not_applicable |

## Evidence Paths

Compute reports:

- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-w2.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-compute-benchmark-w2.md`

Copied primary evidence:

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_raw.json`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_summary.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_summary.csv`

Primary output root:

`runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/`

Key tables:

- `backend_decision_table.md`
- `missing_telemetry_table.md`
- `worker_evidence_table.md`
- `payload_completeness_table.md`
- `stage_timing_table.md`
- `per_batch_timings.jsonl`
- `generated_artifact_ledger.json`

Generated working artifacts remain under:

`datasets/working/autovla_pr30_final_dataloader_perf_v1/w2`

These are generated evidence artifacts only and are not product source.

## Caveats

- D4 is fastest among bounded runnable rows, but no backend winner is selected.
- D5 is an AutoVLA-owned RoboDM-style container route, not a claim of official
  upstream Robo-DM package support.
- D1a remains unavailable/unsafe in this task scope.
- D6 remains optional and not implemented in the current PR.
- `backend_decision_table.md` keeps `mandatory_comparability_gates_pass=False`
  and `blocking_missing_telemetry=True`.
- `missing_telemetry_table.md` keeps D1 and prompt-contract metric gaps visible.
- The adapter-v0/v1 audit numbers remain historical diagnostics only and should
  not be used as active backend-selection evidence.
