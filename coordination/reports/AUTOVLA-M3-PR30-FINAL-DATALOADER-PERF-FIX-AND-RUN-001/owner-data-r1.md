# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Data-R1

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- `git status --short --branch`: expected PR30 local diffs remain unstaged; no staging, commit, push, PR mutation, merge, Slurm, or dataset mutation was performed by Data-R1.

## Reviewed Evidence

- Current local diff for:
  - `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
  - `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
  - `README.md`
  - `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
  - `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
  - `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- Data reports:
  - `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w1.md`
  - `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w2.md`
  - `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w3-docs.md`
- Compute-W2 evidence:
  - `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-w2.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-compute-benchmark-w2.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_raw.json`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final_dataloader_perf_w2_summary.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/backend_decision_table.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/missing_telemetry_table.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/worker_evidence_table.md`
  - `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/benchmark-w2/final-primary/payload_completeness_table.md`

## Findings

No blocking Data correctness findings.

The candidate-specific route repair is acceptable for PR30 review. The measured paths no longer collapse all runnable candidates into one shared JSONL payload path:

- D1a `zjh_lerobot_v21_gr00t_or_lerobot_native` remains structured as `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.
- D1b/D2 `zjh_lerobot_v21_autovla_adapter` uses `raw_source_rows` for real source runs, with raw/source materialization inside worker-owned routes. The JSONL adapter remains scoped to tiny/local compatibility evidence.
- D3 `zjh_lerobot_v3_local` uses a local-v3 parquet plus RGB sidecar candidate artifact and a persistent local-v3 reader path.
- D4 `zjh_webdataset_tar` uses WebDataset tar shard artifacts and a persistent WebDataset reader path.
- D5 `zjh_robodm_container_v1` uses owned RoboDM-style container artifacts with grouped/persistent reader behavior; it is not represented as official Robo-DM package support.
- D6 `zjh_zarr_cache` remains `NOT_IMPLEMENTED_IN_CURRENT_PR`.

The shared manifest is used as sample/window selection evidence rather than a shared measured payload blob. Payload completeness evidence records action, action_mask, language, state, and all three RGB payloads present for D1b/D2, D3, D4, and D5, with identical manifest checksum `8ede4b7ec447306679adc715f02650e50ff3ee549734c050dc337d923c4b3f1a`.

## Timeout Fix Review

Data-W2 replaced the fixed parent queue wait with an adaptive bounded timeout and fail-closed diagnostics. The current constants keep the wait bounded between `120.0` and `2400.0` seconds and derive candidate waits from adapter kind, sample count, and worker slots. The failure mode remains conservative: timed-out or dead workers raise a detailed `TimeoutError` with candidate id, adapter kind, sample count, worker slot count, timeout seconds, timed-out slots, and process status; metrics are not faked.

This addresses the Compute-W1 failure mode where real source-dataset workers could exceed the old fixed `120` second parent queue timeout before reporting evidence.

## Metric Transcription Check

Compute-W2 raw JSON and docs agree on the primary bounded matrix values:

| Candidate | Status | Sample count | Actual workers | Total batch ms | Samples/sec |
|---|---:|---:|---:|---:|---:|
| `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE` | 0 | `not_applicable` | `not_applicable` | `not_applicable` |
| `zjh_lerobot_v21_autovla_adapter` | `RUN` / `PASS` | 4096 | 8 | 165212.583614 | 24.7923 |
| `zjh_lerobot_v3_local` | `RUN` / `PASS` | 4096 | 8 | 20175.055925 | 203.022981 |
| `zjh_webdataset_tar` | `RUN` / `PASS` | 4096 | 8 | 8163.014375 | 501.775424 |
| `zjh_robodm_container_v1` | `RUN` / `PASS` | 4096 | 8 | 13883.202613 | 295.03279 |
| `zjh_zarr_cache` | `NOT_IMPLEMENTED_IN_CURRENT_PR` | 0 | `not_applicable` | `not_applicable` | `not_applicable` |

The review-visible ranking is therefore D4 WebDataset first, D5 RoboDM-style second, D3 local-v3 third, and D1b/D2 AutoVLA v2.1 adapter fourth. The docs preserve this as bounded evidence, not final backend selection.

## Decision Semantics

The current evidence correctly preserves no backend winner:

- `backend_decision_table.md` records `decision=NO_BACKEND_WINNER`, `mandatory_comparability_gates_pass=False`, `blocking_missing_telemetry=True`, `required_run_rows_present=False`, and `training_format_selected=False`.
- The missing telemetry table keeps D1 and prompt-contract metric gaps blocking.
- README and benchmark docs state that no backend winner, training readiness, model quality, deployment readiness, or production readiness is claimed.

## Data Mutation and Artifact Review

- Compute-W2 source dataset hash before/after is recorded as matched: `36d39a8931d12c3460d330053a9bce9096a38f2219b3c6c0a6becac31c396b21`.
- Data-R1 did not mutate `datasets/readonly`, `datasets/working`, source, tests, docs, configs, task state, git index, or PR state.
- `git ls-files datasets/working runs/tmp` returned no tracked generated artifacts.
- `rg` found no runtime source/test/doc dependency on task evidence paths such as `final_dataloader_perf_w2` or `benchmark-w2`; the runtime benchmark implementation is not coupled to generated evidence files.

Publication caveat: `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md` is currently ignored by `.gitignore` and appears as an ignored file unless Quality/Manager force-adds it or chooses another publication route. This is not a Data correctness blocker because the tracked docs/README already preserve the bounded ranking and no-winner caveats, but it remains a publication handling item.

## Validation Evidence

Data-R1 did not rerun heavy validation. Reviewed Data-W3 validation records:

- `py_compile autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `pytest tests/dataloader tests/meta -v`: PASS, `255 passed`.
- Black file-by-file fallback for changed Python files: PASS after combined invocation was interrupted due known multi-file stickiness.
- Ruff changed Python files: PASS.
- Strict pyright substitute using `pyrightconfig.autovla.json`: PASS, `0 errors`.
- Requested `pyrightconfig.genesisvla.json` path was absent; this is recorded as a tooling/config caveat, not a Data correctness failure.
- `git diff --check`: PASS.

## Residual Data Risks

- D1a remains unsafe/unavailable, so the benchmark does not contain a safe native GR00T/LeRobot v2.1 comparator row.
- D6 zarr remains optional and not implemented in current PR30.
- Missing telemetry remains blocking for final benchmark pass, especially default-zero prompt-contract timing fields and unexecuted persistent/prefetch/full warmup-measured-repeat matrix items.
- The final publishable performance Markdown is currently ignored unless explicitly publication-handled.

## Compliance

- DevSpace MCP: no.
- PR #30 mutation: no.
- PR #16 mutation: no.
- Stage/commit/push/merge/mark-ready: no.
- Slurm/job submission by Data-R1: no.
- Dataset mutation/download: no.
- Subagent ledger: none used; retired yes.

## Decision

APPROVE
