# Data Owner Plan Gate Report

## Scope

- Role: 30-OWNER Data
- Task: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001
- Mode: Wave 1 read-only plan gate
- Dispatch reasoning request: xhigh
- Conclusion: APPROVE_PLAN

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Worktree status: clean relative to tracked files at plan-gate read time.

## Inputs Reviewed

- Worktree: `AGENTS.md`
- Worktree: `boundaries.txt`
- Worktree: `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- Worktree: `autovla/dataloader/perf/config.py`
- Worktree: `autovla/dataloader/perf/benchmark.py`
- Worktree: `autovla/dataloader/perf/report.py`
- Worktree: `autovla/dataloader/perf/cli.py`
- Worktree: `autovla/dataloader/perf/metrics.py`
- Worktree: `tests/dataloader/test_perf_harness.py`
- Root read-only supplemental input: `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`
- Root read-only supplemental input: `.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`

The task YAML and normative spec were not present at the exact relative paths in the named worktree, but were available in the root checkout and were read without mutation. No root files were modified.

## Current Data Surface

The existing perf harness supports `metadata-only`, `bounded-decode`, and `training-view`. It already has useful safety boundaries: output cannot be inside the source dataset root, metadata-only avoids row/media reads, bounded-decode requires compute context, and environment output records no training/model/checkpoint/network side effects.

The current surface is not yet aligned with this task because:

- `store-plan`, `store-build-bounded`, and `store-read-benchmark` are not registered modes.
- `report.py` still recommends a local media cache in one branch.
- `build_fast_training_view_schema()` and tests still expose `local_nvme_staging_manifest`.
- Metrics still include `local_nvme_staging_hit_rate`.

These are implementation targets, not plan blockers, provided the next stage is serial and Data-owned.

## Data-Owned Training Store v0 Plan

Data approves a bounded PFS-backed AutoVLA Training Store v0 design with this contract:

- Storage model: `storage_backend: pfs_shared`, `local_stage_used: false`.
- Store format: `npz_jsonl_v0` using stdlib JSON/JSONL plus NumPy `.npz` shards; no dependency addition.
- Required outputs under ignored task evidence:
  - `training_store_manifest.json`
  - `sample_index.jsonl`
  - `episode_index.jsonl`
  - `shards/*.npz`
  - `stats/action_statistics.json`
  - `checksums.json`
  - `build_report.json`
  - `read_benchmark_report.json`
- Source dataset remains read-only; no writes under `datasets/readonly`.
- Build scope remains bounded: max 4 episodes, max 512 samples, max 300 decode seconds unless Manager updates the task card.

The manifest/index/shard contract is feasible from bounded ZJH/LeRobot metadata plus bounded media/sample reads because the existing adapter/artifact surface already exposes dataset manifest, feature/modality, sample count, episode count, splits, action/state/language fields, fingerprints, and statistics-scope semantics. The Training Store should consume that metadata and bounded row/media material only for the selected subset.

## Raw Bounded-Decode Baseline Preservation

The plan must preserve the current raw bounded-decode FAIL as baseline evidence. Data recommends:

- Do not overwrite existing raw bounded-decode reports.
- Copy or reference the raw baseline path in the new `build_report.json` and `read_benchmark_report.json`.
- Use the same bounded sample/episode selection for raw and store-read comparison.
- Report both raw and store read metrics in one comparison record, including `raw_media_decode_time_ms`, raw p50/p95 latency, store read p50/p95 latency, speedup, file-open estimate, metadata-op estimate, and decode-avoided ratio.
- Keep FAIL evidence visible even when the Training Store improves the result.

If the raw baseline path is not present in the worktree, implementation should fail closed until Manager supplies the exact evidence path or authorizes recomputation on compute.

## PFS-Only Requirements

Implementation must remove local-cache framing from active Training Store docs/reports:

- Do not call the store a compute-node cache, node-local cache, or local NVMe staging.
- Replace local-cache recommendations with PFS-backed prepacked shard language.
- Keep any local temporary path language out of the current acceptance surface unless Compute/HPC separately proves hardware support.
- Use `pfs_read_mb_s`, `pfs_file_open_count`, `pfs_metadata_ops_estimate`, `sample_index_lookup_time_ms`, and `prepacked_shard_read_time_ms` as first-class metrics.

Data recommends deprecating or renaming `local_nvme_staging_hit_rate` in the task implementation surface. If backward compatibility requires preserving it in legacy metrics, it must be explicitly zero/legacy and not part of the new store acceptance.

## TDD Sequence

Proceed serially with tests first:

1. Add store contract tests:
   - Training store manifest JSON roundtrip.
   - Sample index JSONL roundtrip.
   - Episode index JSONL roundtrip.
   - Shard checksum determinism.
   - `storage_backend == "pfs_shared"`.
   - `local_stage_used is False`.
2. Add mode/config tests:
   - `store-plan`, `store-build-bounded`, `store-read-benchmark` accepted.
   - Source dataset path cannot be used as output or training-store dir.
   - Tracked/source paths refused for generated store artifacts.
   - Existing `metadata-only` and `bounded-decode` stay compatible.
3. Add tiny-fixture builder tests:
   - `store-plan` writes manifest/plan only.
   - `store-build-bounded` writes bounded `.npz` shards and indexes under caller output.
   - Build bounds enforced before media/sample expansion.
   - No full conversion and no full media predecode.
4. Add read benchmark tests:
   - `store-read-benchmark` reads the store, not source media.
   - PASS/WARN/FAIL classification and speedup calculation.
   - Missing telemetry remains explicit.
5. Add policy/meta tests:
   - No local NVMe/local-cache wording in active PFS store docs.
   - No generated media/store artifacts committed.
   - No dependency spec change.
   - No `genesisvla` compatibility shim.

## Implementation Notes

Recommended implementation layout:

- `autovla/dataloader/perf/training_store.py` for manifest/index/shard contracts and bounded builder.
- `autovla/dataloader/perf/io_metrics.py` for PFS file-open/read/metadata estimates if separation stays simple.
- Extend `config.py`, `cli.py`, `benchmark.py`, `report.py`, and tests to route the three store modes.

The implementation should keep code direct and Python 3.10-compatible, with Chinese docstrings/comments for new or modified code. It should avoid introducing WebDataset, Arrow, Parquet, or IndexedDataset dependencies in v0.

## Risks And User Decision Points

- Store payload format: `.npz` is acceptable for bounded v0 evidence. A future persistent production store backend such as WebDataset, Arrow, Parquet, or indexed binary shards should require user/Owner decision after the v0 benchmark.
- Statistics scope: action statistics must remain action-only or mixed with an explicit action subset. Vision-language-only samples must not contribute to action normalization.
- Raw/store comparability: if the bounded sample set cannot be made identical between raw decode and store-read, the result should be WARN or REQUEST_CHANGES rather than PASS.
- Compute evidence: login-node tests can validate contract behavior, but raw bounded-decode and store-read performance acceptance must run on the approved compute path.
- Missing baseline evidence: if the existing raw bounded-decode FAIL artifact is unavailable, Manager must either provide its path or authorize recomputation before merge gating.

No immediate user decision is required for serial implementation of bounded Training Store v0. A user decision may be needed later if v0 remains FAIL/WARN and the team must choose a persistent derived-store format or larger conversion strategy.

## Data Gate

Data approves proceeding to serial implementation with one Data-owned writer and independent review. The implementation must preserve the raw bounded-decode FAIL, replace local-cache framing with PFS Training Store terminology, and keep all generated store artifacts under ignored task evidence unless a future task explicitly authorizes a persistent derived dataset location.

## Compliance

- DevSpace MCP: not used.
- Source/test/docs/config/git/PR mutation: not performed.
- Report-only write: `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-plan.md`.
- Slurm/GPU/training/model/checkpoint/network: not run.
- PR #14: not mutated.
- Subagent ledger: none used / retired yes.

## Conclusion

APPROVE_PLAN
