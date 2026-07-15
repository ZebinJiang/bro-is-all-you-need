# Owner Architecture Plan Review

Task: `AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001`
Role: `10-OWNER · Architecture`
Mode: read-only review/planning, report-only write
Decision: `APPROVE_PLAN`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `f194b6e8d3d6679448749da36e6bfc68f690ef91`
- Status: clean, tracking `origin/dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- Workspace check: `PASS`
- User override recorded: `model=gpt-5.5`, `thinking=high`
- `thinking=xhigh` used: no
- `thinking=max` used: no

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `README.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`
- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- `coordination/reports/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/manager-summary.md`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/invalidation/pr30-invalidated-results-manifest.json`
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.md`
- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
- `autovla/dataloader/perf/native_loader_timing_v2.py`
- `autovla/dataloader/perf/native_loader_bakeoff.py`
- `autovla/dataloader/perf/profiler.py`
- `autovla/dataloader/perf/metrics.py`
- `autovla/dataloader/perf/benchmark.py`
- `tests/dataloader/test_fair_native_loader_bakeoff.py`
- `tests/dataloader/test_native_loader_bakeoff.py`

No source, tests, docs, PR metadata, branch state, or git index was modified by this Architecture review. The only write was this report path.

## Architecture Decisions

1. **Current corrected PR #30 result is `adapter-v0` baseline, not backend selection.**
   The corrected fair native-loader bakeoff invalidates the prior unfair PR #30 numbers and is useful as the initial adapter-v0 baseline for audit. It must not be reframed as a final backend winner, training format decision, GPU training result, or new data-format selection.

2. **Stage-level profiler contract is appropriate and should be added before optimization claims.**
   The next tranche may introduce an AutoVLA-native stage profiler under the dataloader/perf surface. It should decompose adapter-v0 latency into explicit stages such as source row selection, frame materialization/ffmpeg, artifact build/write, batch read, payload validation/hash, serialization/report write, and optional worker/queue overhead. Each stage should record concrete p50/p95/max or total elapsed time, sample/batch counts, and missing/unsupported fields explicitly.

3. **Adapter-v1 optimization boundary is narrow.**
   Adapter-v1 may optimize the adapter path only: batching/read ordering, avoiding repeated artifact/index reads, safe reuse of bounded per-run metadata, vectorized validation where semantics are identical, and clearer stage timing. It must preserve the same selected sample/window manifest, payload completeness contract, candidate set, no-source-mutation policy, no generated artifact tracking, and no final-winner semantics. It must not introduce a new backend format, dependency route, model/training path, or PR #16 dependency.

4. **Worker-count label must be separated from actual worker execution evidence.**
   The current fair rerun records `worker_count=8`, but the inspected `native_loader_timing_v2` timing loops are sequential over batches and do not emit observed worker participation evidence. Therefore current fair results should be labeled as configured/requested `worker_count=8` adapter-v0 baseline, not proof that eight independent workers executed. Any future claim of actual W8 execution must include observed worker evidence equivalent to `native_loader_bakeoff.py`'s `worker_execution_evidence`: requested worker count, observed worker count, per-worker sample counts, worker ids, execution mode, and pass/fail status.

5. **BenchmarkBatch/shared-batch contract should be explicit.**
   The optimizer must define a stable `BenchmarkBatch` or equivalent shared-batch contract covering candidate id, sample ids/window ids, batch size, action/state/action_mask, language, exactly three materialized RGB payload proofs, payload hash, and provenance. Adapter-v0 and adapter-v1 must consume the same batch manifest and output comparable rows. Camera refs or path-only payloads are invalid for fair adapter performance claims.

6. **PR #30 must remain draft/open for this tranche.**
   This is an audit/optimization planning task for a draft PR. It does not authorize marking PR #30 ready, merging it, mutating PR #16, or promoting benchmark output to a final backend decision.

## Allowed Path Assessment

Allowed future implementation paths, if Manager dispatches write-capable workers:

- `autovla/dataloader/perf/**`
  - New adapter audit/profiler module is acceptable.
  - Small extensions to `fair_native_loader_bakeoff.py` and `native_loader_timing_v2.py` are acceptable only to expose stage timing, relabel adapter-v0 baseline, or add adapter-v1 comparison while preserving existing contracts.
- `tests/dataloader/**`
  - Focused unit tests for stage profiler schema, adapter-v0/v1 shared batch equivalence, worker-count label/evidence separation, camera_refs rejection, and no-final-winner docs.
- `docs/benchmarks/**` or `README.md`
  - Only narrow wording updates that label corrected fair result as adapter-v0 baseline and keep final backend selection deferred.
- `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**`
  - Task-local evidence, generated profiler output, and ignored benchmark artifacts.
- `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**`
  - Owner reports and Manager synthesis.

## Protected Path and Scope Assessment

Protected or out of scope:

- M1/M2 public contracts and `genesisvla/**`
- `autovla/models/**`, `autovla/training/**`, checkpoints, tokenizer/model loading, HF/W&B, endpoints, robot surfaces
- Dependency files, `pyproject.toml`, requirements, workflow/CI files, Makefile, and uv profiles unless a separate Tooling/user decision authorizes them
- PR #16 or any other backend-research PR state
- `datasets/readonly/**` mutation
- Generated stores, media, logs, and benchmark outputs as tracked source
- Any claim that adapter-v1 is the final backend winner or fine-tune/training-ready format
- Any GPU training, Slurm training, new format task, or model-quality claim

## Required Review Criteria for Implementation

Implementation review should require:

- Stage profiler schema with concrete stage timings and explicit missing values.
- Adapter-v0 baseline label in report/docs, preserving `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- Adapter-v1 rows compared only against adapter-v0 over the same shared sample/window manifest and `BenchmarkBatch` contract.
- Payload proof for action, language, state, action_mask, and exactly three materialized RGB streams.
- Camera refs/path-only payloads rejected for fair performance rows.
- Worker-count fields split into requested/configured label and observed worker evidence. If actual W8 is claimed, require worker execution evidence; otherwise keep it explicitly label-only.
- Generated artifact ledger proving source dataset not mutated and generated artifacts not tracked.
- Docs and README maintain draft/decision-support wording and no final backend winner.
- Validation includes focused tests plus no-mutation/no-generated-artifact scans before any PR publication update.

## DevSpace MCP Compliance

- DevSpace MCP used: no
- `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash used: no
- Evidence source: local filesystem, local git, task-local reports/evidence only

## Subagent Ledger

- Child subagents used: none
- Child-agent depth: `0`
- Retirement status: `retired yes`

## Conclusion

`APPROVE_PLAN`

The adapter performance audit/optimization tranche is architecturally acceptable if it remains a bounded dataloader/perf audit: relabel the corrected fair result as adapter-v0 baseline, add stage-level profiling and optional adapter-v1 comparison over the same shared batch contract, avoid backend-selection/final-winner claims, and keep PR #30 draft/open.
