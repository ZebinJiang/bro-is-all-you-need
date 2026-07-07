# AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 Data RO1

## Conclusion

PASS_PLAN

Data RO1 approves the minimal Data-W1 implementation plan. No true scope or dependency blocker was found for the planning stage. The current PR30 benchmark evidence remains diagnostic-only until W1 implements Dataset-like native adapters plus an actual worker runner and a later compute wave records real worker execution evidence.

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- status: branch tracks `origin/dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`; task card is untracked as expected input; this report directory/file is the only RO1 write.

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- `README.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
- `autovla/dataloader/perf/native_loader_timing_v2.py`
- `autovla/dataloader/stores/*reader.py`
- `autovla/dataloader/stores/*builder.py`
- `autovla/dataloader/stores/benchmark.py`
- `autovla/dataloader/stores/common.py`
- `tests/dataloader/test_fair_native_loader_bakeoff.py`

No DevSpace MCP, compute jobs, Slurm, PR mutation, staging, commits, pushes, dataset writes, model/checkpoint/tokenizer load, HF/W&B, endpoint, or robot access were used.

## Current PR30 Gaps

- `fair_native_loader_bakeoff.py` currently times direct callables and cached readers, not an actual Dataset-like worker path.
- Current `actual_worker_count` is explicitly `not_measured`; `worker_count_label` is only a configured label.
- Current runner hard-requires `worker_count=8` in config validation, but does not prove eight worker participants.
- Raw paths currently depend on preloaded `SourceSample` and materializer-style proof paths; that is insufficient for an actual dataloader worker benchmark.
- Current `stores/common.py::measure_reader` is a direct callable loop and cannot produce worker ids, process/thread ids, per-worker sample counts, or every-worker-observed evidence.
- Current store readers/builders are useful substrate, but several paths still produce or consume `camera_refs` payloads; actual Dataloader W1 RUN rows must materialize or carry real RGB bytes/arrays in `BenchmarkBatch`, not camera-reference-only rows.
- PR-visible docs correctly state that adapter-v0/v1 numbers are diagnostic and no backend winner is selected.

## Candidate Mapping

- D1 `zjh_lerobot_v21_gr00t_or_lerobot_native`: required row. Data-W1 should fail closed or mark unsafe if GR00T-native execution would require model/training/runtime side effects; a safe LeRobot-native/raw read path may run only if it avoids preloaded `SourceSample` and materializes payload in the worker path.
- D2 `zjh_lerobot_v21_autovla_adapter`: required row. Must use an AutoVLA adapter Dataset-like path over the same sample/window manifest, not a preloaded proof row.
- D3 `zjh_lerobot_v3_local`: required row. Should use the current local-v3 builder/reader substrate, but W1 must ensure the benchmark read path produces action/state/language/mask and three RGB payloads, not `records/*.json` or `camera_refs` as the measured payload.
- D4 `zjh_webdataset_tar`: required row. Should use the existing WebDataset package-backed tar route where available, with sequential/streaming worker reads and materialized RGB/action/state/language/mask payloads.
- D5 `zjh_robodm_container_v1`: required row. Should remain an owned RoboDM-style bounded prototype, not actual Robo-DM package support, with container/index reuse where practical.
- D6 `zjh_zarr_cache`: optional only if an existing implementation exists. Current inspected PR30 surfaces do not show an existing zarr cache implementation, so W1 should emit `NOT_IMPLEMENTED_IN_CURRENT_PR` unless Manager supplies an implementation or dependency authorization.

## Minimal Data-W1 Plan

1. Add a narrow actual-worker benchmark surface under `autovla/dataloader/perf/**`, for example `actual_dataloader_worker_bakeoff.py`.
2. Define a small native adapter contract:
   - `CandidateNativeAdapter`: candidate id, status, native loader name, adapter version, prototype flag, dependency status, `prepare(...)`, and `dataset(...)`.
   - Dataset-like objects: `__len__` and `__getitem__` returning one fully materialized benchmark sample.
   - `BenchmarkBatch`: action, state when present, language, action mask, exactly three RGB camera payloads as bytes or arrays, sample ids, episode ids, window ids, deterministic payload hashes, and `payload_missing_fields`.
3. Add `collate_benchmark_batch(...)` that rejects missing action/language/mask/sample ids and rejects camera-reference-only or proof-only RGB payloads for RUN rows.
4. Add an `ActualWorkerRunner` using a dependency-free worker implementation such as `concurrent.futures` or `multiprocessing`. It must record:
   - requested_worker_count
   - observed_worker_count
   - worker ids or process ids
   - per-worker sample counts
   - every_worker_observed_at_least_one_sample
   - worker_execution_mode
   - actual_worker_count
   - worker_count_evidence_status
5. Use one deterministic shared sample/window manifest for all candidates, including seed, max episodes, max samples, sample ids/window ids, camera policy, decode policy, action horizon, and manifest checksum.
6. Separate build/prepare timing from worker read timing. Converted candidates may build artifacts under `datasets/working/autovla_actual_worker_bakeoff_v1/**`, but measured read rows must read from the candidate artifact through its Dataset-like adapter.
7. Keep generated evidence under `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/**` and generated datastore artifacts under `datasets/working/autovla_actual_worker_bakeoff_v1/**`.
8. Keep source dataset read-only and never use it as an output path.

## Required Output Artifacts

Data-W1 should produce these task-local outputs before compute review:

- `shared-sample-window-manifest.json`
- `actual_dataloader_worker_bakeoff.json`
- `actual_dataloader_worker_bakeoff.csv`
- `actual_dataloader_worker_bakeoff.md`
- `actual_worker_stage_timing.json`
- `actual_worker_stage_timing.csv`
- `actual_worker_stage_timing.md`
- `worker_execution_evidence.json`
- `worker_execution_evidence.csv`
- `worker_execution_evidence.md`
- `benchmark_batch_contract_validation.json`
- `pr30_result_consistency_audit.json`
- `pr30_result_consistency_audit.md`
- `generated-artifact-ledger.json`

Tracked documentation should be updated only in the implementation wave after evidence exists, especially `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`, `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`, existing PR30 benchmark docs, and concise README status.

## Test Plan For W1

- Assert D1-D5 rows are present and D6 is `NOT_IMPLEMENTED_IN_CURRENT_PR` unless an implementation exists.
- Assert RUN rows reject preloaded `SourceSample` proof-only paths.
- Assert RUN rows reject `camera_refs`-only payloads.
- Assert collated `BenchmarkBatch` includes action, state when available, language, action mask, sample ids, episode ids, deterministic hash, and exactly three RGB payloads.
- Assert actual worker evidence fails if `observed_worker_count` is missing, `actual_worker_count` is `not_measured`, or per-worker sample counts do not cover all workers when sample_count is at least worker_count.
- Assert all candidates use the same manifest checksum and sample/window ordering.
- Assert generated artifacts are under allowed task roots and no generated artifacts are tracked.
- Assert no final backend winner is selected from incomplete or non-comparable evidence.
- Assert no training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot fields or side effects appear.

## Compute Routing

Data-W1 can implement and validate tiny login-node-safe fixtures locally. The real source-dataset actual-worker benchmark should be routed to Compute/HPC after the implementation passes local tests and produces the runnable CLI/config surface. Data RO1 did not run compute or Slurm.

## Dependency Position

No new dependency is required for W1 if it uses existing project dependencies and a stdlib worker runner. If W1 attempts to use a framework-specific DataLoader requiring new dependency/runtime authorization, that should become `BLOCKED_DEPENDENCY_OR_EXECUTION`; the preferred plan is dependency-free worker execution plus existing WebDataset/pyarrow routes already present in the project-local environment.

## Governance

- DevSpace MCP: not used.
- PR #30: not mutated; remains draft/open by instruction.
- PR #16: not touched.
- Source dataset: read-only inspection only; no mutation.
- Generated datasets: not created in RO1.
- Git: no staging, commit, push, merge, PR mutation, reset, restore, clean, or stash.
- Task-local override record: user requested model `gpt-5.5` and thinking `high`; no `xhigh` or `max` was used for this dispatch.
- Subagent ledger: none used; retired yes.

## Residual Risks

- D1 may need a precise Manager decision on whether the safe executable route is GR00T-native, LeRobot-native, or an AutoVLA raw adapter, because any GR00T original loader path must avoid model/training/runtime side effects.
- Current stores substrate is close but not sufficient: W1 must ensure measured converted read paths use real artifact payloads with RGB bytes/arrays, not source materializer fallbacks.
- Actual worker proof must be measured during the real runner, not inferred from configuration or labels.
- Final backend selection remains out of scope until comparable actual-worker evidence is reviewed.
