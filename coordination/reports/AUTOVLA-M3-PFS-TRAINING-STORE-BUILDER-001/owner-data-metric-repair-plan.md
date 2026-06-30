# Data Owner Metric Repair Plan

## Scope

- Role: 30-OWNER Data
- Task: AUTOVLA-M3-PFS-STORE-METRIC-REPAIR-001
- Parent task: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001
- Mode: read-only repair planning only
- Conclusion: APPROVE_METRIC_REPAIR_PLAN

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Status: PR #14 candidate diff is present; this planning task made no source/test/git/PR mutation.

## Evidence Reviewed

- `autovla/dataloader/perf/benchmark.py`
- `autovla/dataloader/perf/training_store.py`
- `autovla/dataloader/perf/report.py`
- `tests/dataloader/test_perf_harness.py`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-execute.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/manager-summary.md`
- `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/build_report.json`
- `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/read_benchmark_report.json`

## Root Cause

The current store-read classifier compares Training Store read p50 directly against `raw_batch_latency_ms_p50`.

Current evidence:

- Raw batch p50: `2.86716 ms`
- Raw media decode time: `25.963794 ms`
- Raw classification: `FAIL`, because `media_decode_time_ms` dominates per-batch time.
- Store read p50: `9.233619 ms`
- Store `decode_avoided_ratio`: `1.0`
- Store checksums verified: `true`
- Current computed `speedup_vs_raw_decode`: `0.310513`

Code path:

- `training_store.py::read_training_store_benchmark()` copies `raw_batch_latency_ms_p50`, `raw_batch_latency_ms_p95`, and `raw_media_decode_time_ms` from `build_report.json`.
- `_speedup(raw_p50, store_p50)` uses only `raw_batch_latency_ms_p50`.
- `report.py::classify_training_store_comparison()` uses `raw_batch_latency_ms_p50` for the PASS/WARN/FAIL threshold.
- `benchmark.py::run_benchmark()` trusts that comparison result for store-read classification.

This loses the raw failure basis: the raw report failed because media decode time dominates, while the comparison denominator ignores the media decode metric that the Training Store avoids. The metric contract is therefore ambiguous rather than proving the store path is ineffective.

## Proposed Narrow Repair

Data recommends a metric-contract repair first, not a store-format or shard-layout rewrite.

Add an explicit effective raw comparison latency:

```text
raw_effective_batch_latency_ms_p50 = max(raw_batch_latency_ms_p50, raw_media_decode_time_ms)
raw_effective_batch_latency_ms_p95 = max(raw_batch_latency_ms_p95, raw_media_decode_time_ms)
raw_comparison_basis = media_decode_dominates when raw_media_decode_time_ms > raw_batch_latency_ms_p50
speedup_vs_raw_decode = raw_effective_batch_latency_ms_p50 / training_store_batch_latency_ms_p50
```

Use `max(...)`, not sum, to avoid double-counting unless Architecture/Quality decide that the raw benchmark should redefine batch latency itself. This is the narrowest repair because it keeps preserved raw fields intact and adds an explicit comparison basis for the store classifier.

With the current evidence, this would compare `9.233619 ms` against effective raw latency `25.963794 ms`, giving an effective speedup of about `2.81x`. Manager should still require Quality/Architecture agreement before reclassifying compute evidence.

## Proposed Exact File/Test Edits

1. `autovla/dataloader/perf/training_store.py`
   - Add helper to derive effective raw latency from raw batch p50/p95 and `raw_media_decode_time_ms`.
   - Add comparison fields:
     - `raw_effective_batch_latency_ms_p50`
     - `raw_effective_batch_latency_ms_p95`
     - `raw_comparison_basis`
   - Recompute `speedup_vs_raw_decode` from effective raw latency.
   - Keep legacy/raw evidence fields unchanged.

2. `autovla/dataloader/perf/report.py`
   - Update `classify_training_store_comparison()` to use `raw_effective_batch_latency_ms_p50` when present.
   - Fall back to `raw_batch_latency_ms_p50` only when effective latency is absent.
   - Include reason text that names the comparison basis.

3. `tests/dataloader/test_perf_harness.py`
   - Add a regression test using the compute evidence values:
     - raw p50 `2.86716`
     - raw media decode `25.963794`
     - store p50 `9.233619`
     - expected effective raw p50 `25.963794`
     - expected speedup greater than `2.0`
     - expected classifier `PASS` or policy-approved `WARN` depending on Architecture/Quality wording.
   - Add fallback test where raw media decode is missing and classifier uses raw batch p50.
   - Assert `decode_avoided_ratio == 1.0` remains in the report.

4. Optional low-risk follow-up, only after metric contract is fixed:
   - Inspect `sample_index_lookup_time_ms` overhead (`5.434123 ms`) for avoidable repeated JSONL reads.
   - Do not optimize this in the first repair unless tests show a trivial single-pass reuse. The first repair should not mix metric-contract changes with store-read performance refactoring.

## Validation Commands

Login-node-safe validation after implementation:

```text
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_perf_harness.py -q
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q
runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf tests/dataloader/test_perf_harness.py
runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 autovla/dataloader/perf tests/dataloader/test_perf_harness.py
runs/tmp/m1-tool-venv/bin/pyright -p pyrightconfig.autovla.json
git diff --check
```

If Black repeats the prior tool-environment hang, record the exact command and use Manager-approved wrapper evidence instead of marking a false pass.

## Compute Rerun Plan

The existing Training Store can be reused for the metric repair because:

- `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/read_benchmark_report.json` has `checksums_verified: true`.
- `build_report.json` already contains the raw fields needed to derive effective raw latency.
- The proposed repair can derive new comparison fields at store-read time without rebuilding shards.

Recommended compute rerun after Architecture/Quality/Product planning:

- Minimum rerun: `store-read-benchmark` only, reusing the existing `training-store/` and preserved raw baseline fields.
- Rebuild not required for the metric-contract repair.
- Rebuild required only if the accepted plan requires persisted build-report schema migration or store artifact regeneration.

## Safety Constraints

- No writes into `datasets/readonly`.
- No full dataset conversion or full media predecode.
- No real training, finetune, model load, checkpoint load, tokenizer load, HF/W&B network, endpoint, robot, Slurm, or GPU in the Data repair implementation wave unless separately assigned.
- No dependency spec changes.
- No PR/git mutation.
- No local NVMe/local-cache public framing.
- Preserve raw bounded-decode FAIL evidence and do not rewrite historical compute reports.

## Compliance

- DevSpace MCP: no.
- Source/test/git/PR mutation in this planning task: none.
- Subagents: none used / retired yes.

## Conclusion

APPROVE_METRIC_REPAIR_PLAN
