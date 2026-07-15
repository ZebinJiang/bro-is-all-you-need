# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Owner Data-RO1

Role: 30-OWNER - Data
Runtime override: model=gpt-5.5, thinking=high; xhigh/max not used.

## Conclusion

REQUIRE_ADAPTER_FIXES_BEFORE_RUN

Data does not approve running a final compute benchmark on the current PR30 actual-worker scaffold. The current implementation proves route/provenance and worker-process mechanics, but runnable D2-D5 candidates still share the same prebuilt JSONL payload artifact path in the actual-worker benchmark. Data-W1 must repair the adapter/native-loader measured path before final Compute/HPC execution.

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- `git status --short --branch`: aligned to origin branch; only untracked coordination/task report paths were present before this RO1 report write.
- PR #30 state from dispatch: open draft; no PR mutation performed.
- Shell note: local shell startup printed `whoami: cannot find name for user ID 2000`; verification outputs were valid.

## Reports Written

- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/code-review/adapter-benchmark-code-review.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-ro1.md`

## Reviewed Surfaces

- Governance/task inputs:
  - `AGENTS.md`
  - `boundaries.txt`
  - `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
  - `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- Prior PR30 reports:
  - `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/**`
- Source/test/docs:
  - `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
  - `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - `autovla/dataloader/perf/native_loader_timing_v2.py`
  - `autovla/dataloader/stores/common.py`
  - `autovla/dataloader/stores/lerobot_v21_reader.py`
  - `autovla/dataloader/stores/lerobot_v3_reader.py`
  - `autovla/dataloader/stores/webdataset_reader.py`
  - `autovla/dataloader/stores/robodm_reader.py`
  - `autovla/dataloader/stores/webdataset_builder.py`
  - `autovla/dataloader/stores/robodm_builder.py`
  - `autovla/dataloader/stores/lerobot_v3_builder.py`
  - `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
  - `README.md`
  - `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
  - `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
  - `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`

## Key Findings

1. Current actual-worker runnable rows are not candidate-native enough for final benchmark execution.
   - `actual_dataloader_worker_bakeoff.py:504-527` writes one common `payloads.jsonl` for every runnable D2-D5 candidate.
   - `actual_dataloader_worker_bakeoff.py:657-692` builds that payload set from source rows through one raw/native timing materializer before worker execution.
   - `actual_dataloader_worker_bakeoff.py:336-367` then only has workers read the JSONL payload file.
   - Result: actual workers are real, but they are not measuring distinct D2-D5 native reader paths.

2. Media/RGB/action/state/language/mask materialization is outside the measured worker path.
   - `actual_dataloader_worker_bakeoff.py:657-692` materializes payloads before the worker runner.
   - `actual_dataloader_worker_bakeoff.py:793-823` defaults many required timing fields to `0.0` and marks them missing.
   - Result: current route cannot be final prompt-contract timing evidence.

3. Store/probe readers still expose camera-reference payloads that are valid for metadata probes but invalid for final RUN payloads.
   - `common.py:99-116` emits `camera_refs`.
   - `lerobot_v3_reader.py:48-77` returns local-v3 payloads with `camera_refs`.
   - `webdataset_builder.py:38-49` and `robodm_builder.py:36-47` write camera-ref sidecars.
   - Data-W1 must keep metadata/probe routes separate from actual-worker materialized RUN payloads.

4. Known adapter overhead hot spots need repair before final run:
   - WebDataset reader can rescan shards per batch (`webdataset_reader.py:14-35`, `native_loader_timing_v2.py:922-939`).
   - RoboDM reader reopens containers per sample (`robodm_reader.py:14-27`).
   - Local-v3 reader reloads index/tasks and keeps parquet cache only inside one call (`lerobot_v3_reader.py:14-32`).

5. Docs are conservative enough for request-changes posture.
   - Reviewed README/docs state no backend winner, no final backend selection, no training format selected, and adapter-v1/actual-worker limitations.

## Required Data-W1 Fix Plan

Data-W1 should implement the following before Compute/HPC final run:

1. Add a strict candidate-native worker runner:
   - candidate adapter protocol;
   - dataset-like adapter objects;
   - worker-side adapter initialization;
   - worker-side batch read/collate into `BenchmarkBatch`.
2. Replace common JSONL measured path:
   - shared manifest may select ids/windows only;
   - no common prebuilt payload blob path can be the measured path for D2-D5.
3. Candidate-specific measured paths:
   - D2 `zjh_lerobot_v21_autovla_adapter`: raw/source AutoVLA v2.1 adapter baseline, with decode/materialization inside measured adapter path.
   - D3 `zjh_lerobot_v3_local`: persistent local-v3 parquet/meta/RGB reader.
   - D4 `zjh_webdataset_tar`: WebDataset package-backed persistent/streaming shard reader, no per-batch shard-start rescan.
   - D5 `zjh_robodm_container_v1`: owned RoboDM-style reader with grouped/persistent container handles.
4. Keep blocked/optional rows honest:
   - D1 blocked unless safe data-only native route exists with no model/checkpoint/tokenizer/runtime side effects.
   - D6 optional `NOT_IMPLEMENTED_IN_CURRENT_PR` unless existing implementation is present.
5. Enforce payload completeness for RUN rows:
   - action;
   - state;
   - language;
   - action_mask;
   - sample/episode/window ids;
   - deterministic hash;
   - exactly three RGB payloads as bytes/arrays;
   - no camera-refs-only or proof-only payloads.
6. Add full prompt-contract metrics:
   - loader/index/metadata/sample select;
   - media decode/RGB materialize;
   - action/state/language/mask load;
   - payload validation;
   - collate/array conversion;
   - worker queue and next-batch wait;
   - file opens, bytes read, read MB/s, CPU/RSS where feasible;
   - warmup/measured/repeats raw per-batch rows.
7. Keep missing telemetry fail-closed:
   - missing required metrics go to `missing_telemetry_table` with blocking status.
8. Keep docs in WIP/no-winner posture until final gates pass.

## Candidate Matrix

| Label | Candidate | Data-RO1 status |
| --- | --- | --- |
| D1 | `zjh_lerobot_v21_gr00t_or_lerobot_native` | Block by default: `NOT_RUN_UNSAFE_OR_UNAVAILABLE` / `BLOCKED_NATIVE_V21_DATALOADER_UNAVAILABLE`. |
| D2 | `zjh_lerobot_v21_autovla_adapter` | Mandatory AutoVLA v2.1 adapter baseline; use this as the raw/v2.1 adapter label if D1 is blocked. |
| D3 | `zjh_lerobot_v3_local` | Mandatory local-v3 candidate; must use real local-v3 reader path. |
| D4 | `zjh_webdataset_tar` | Mandatory WebDataset candidate; must use WebDataset package-backed shard reader. |
| D5 | `zjh_robodm_container_v1` | Mandatory owned RoboDM-style prototype; must not claim official RoboDM. |
| D6 | `zjh_zarr_cache` | Optional; no implementation found, keep `NOT_IMPLEMENTED_IN_CURRENT_PR`. |

## D1a And D6 Decisions

- D1a should not be attempted in Data-W1 unless a safe, existing, data-only GR00T/LeRobot native route is proven without model/checkpoint/tokenizer/HF/W&B/training/endpoint/robot side effects.
- If D1a remains blocked, the fair raw/source baseline should be D2 `zjh_lerobot_v21_autovla_adapter`.
- D6 should remain optional-not-implemented. No zarr cache implementation was found in current reviewed PR30 scope.

## Reference Reuse Decision

- References considered:
  - Existing AutoVLA PR30 actual-worker scaffold.
  - Existing fair native-loader benchmark scaffold.
  - Existing native-loader timing v2 materialized RGB helpers.
  - Existing datastore builders/readers for local-v3, WebDataset, and RoboDM-style.
  - WebDataset package API and PyArrow/parquet API already present in project tool environment.
  - GR00T/LeRobot native route as a safety-bounded D1 concept only.
- Code reuse/wrap/adapt/reject:
  - Reuse native AutoVLA helpers and existing package-backed readers where they match the contract.
  - Wrap WebDataset/PyArrow APIs; do not copy package code.
  - Reject GR00T/LeRobot D1 execution for Data-W1 unless separately proven safe.
- License/dependency impact:
  - No new dependency required for planned D2-D5 fixes.
  - No copied third-party code recommended; no new notice needed.
  - D6/zarr remains dependency/scope blocked.
- Reason for native implementation:
  - The benchmark needs AutoVLA-specific worker evidence, payload validation, manifest fairness, generated artifact policy, and no model/runtime side effects.
- Tests required:
  - fail if D2-D5 share one common prebuilt payload JSONL measured path;
  - fail camera-ref-only RUN payloads;
  - verify persistent WebDataset/local-v3/RoboDM readers;
  - verify numeric actual worker evidence;
  - verify missing telemetry blocks final winner;
  - verify no generated artifacts tracked.

## Compliance

- DevSpace MCP: no.
- Source/test/docs/config/dependency edits: none.
- Git stage/commit/push/PR mutation: none.
- Compute/Slurm: not run.
- Training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not run.
- Source dataset mutation: none; only read-only inspection.
- `/tmp` tool env: not used.
- Subagents: none used.
- Retirement: Data-RO1 complete; retired yes.
