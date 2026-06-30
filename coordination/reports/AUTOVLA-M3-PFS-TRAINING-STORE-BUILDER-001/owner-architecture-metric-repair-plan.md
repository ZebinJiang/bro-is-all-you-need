# AUTOVLA-M3-PFS-STORE-METRIC-REPAIR-001 Architecture Metric Repair Plan

Role: 10-OWNER - Architecture
Parent: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 / PR #14 continuation
Mode: read-only planning plus this report write
Dispatch reasoning policy: thinking=xhigh requested; thinking=max not used

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `git branch --show-current`: `dev/feat-autovla-m3-dataloader-perf-harness`
- `git rev-parse HEAD`: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- `git status --short --branch`: existing PR #14 candidate diff is present in `autovla/dataloader/perf/**`, `tests/dataloader/test_perf_harness.py`, `scripts/quality/autovla_check_project_local.sh`, task card, and task reports.

Workspace verification: PASS.

## Evidence Reviewed

- User/Manager prompt attachment:
  - `/home/cz-jzb/.codex/attachments/4f313e72-bc08-4518-8dd5-7768174ec6da/pasted-text-1.txt`
- Normative spec:
  - `/home/cz-jzb/workspace/vla-flywheel/.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`
- Current source/tests:
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/report.py`
  - `autovla/dataloader/perf/metrics.py`
  - `autovla/dataloader/perf/training_store.py`
  - `tests/dataloader/test_perf_harness.py`
- Current task reports:
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-execute.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/manager-summary.md`
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-execute.md`
- Current metric evidence:
  - raw bounded-decode report: `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output-decode/perf_report.json`
  - store read report: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/perf-store-read/perf_report.json`
  - store build/read evidence: `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/training-store/`

## Current Failure Shape

Compute job `1833` completed successfully and produced the required PFS-backed Training Store artifacts. The compute conclusion is `FAIL_COMPUTE` because the current comparison contract reports:

- raw batch p50: `2.86716 ms`
- raw media decode time: `25.963794 ms`
- raw classification: `FAIL`
- raw failure reason: `media_decode_time_ms dominates per-batch time`
- store read p50: `9.233619 ms`
- current `speedup_vs_raw_decode`: `0.310513`
- current store classification: `FAIL`

Current source cause:

- `benchmark.py` computes raw `batch_latency` as adapter metadata inspect time plus a small placeholder.
- `media_decode_time_ms` is measured separately.
- `training_store.py` computes `_speedup(raw_p50, store_p50)`, so the field named `speedup_vs_raw_decode` is actually using raw batch p50, not raw decode cost.
- `report.py::classify_training_store_comparison()` also gates PASS/WARN on `raw_batch_latency_ms_p50` and `training_store_batch_latency_ms_p50`.

This compares the store read path against the wrong baseline for the specific bottleneck that the Training Store was designed to remove.

## Contract Decision

Architecture decision: use an explicit raw decode bottleneck comparison when the preserved raw bounded-decode result failed because `media_decode_time_ms` dominates.

Do **not** redefine all raw bounded-decode `batch_latency_ms_p50` semantics in this narrow repair. Keep raw batch latency and raw decode bottleneck as separate metrics because they represent different observations:

- `raw_batch_latency_ms_p50`: bounded batch/probe latency proxy currently emitted by the raw benchmark.
- `raw_media_decode_time_ms`: explicit measured decode/read bottleneck that caused the raw failure.
- `raw_decode_bottleneck_ms` or `raw_comparison_latency_ms`: comparison baseline for Training Store when the raw classification reason is media-decode dominated.

For this repair, `speedup_vs_raw_decode` must be computed from the explicit raw decode bottleneck metric:

```text
speedup_vs_raw_decode = raw_media_decode_time_ms / training_store_batch_latency_ms_p50
```

The comparison classifier should allow PASS when:

- `decode_avoided_ratio == 1.0`;
- raw failure reason or preserved raw baseline indicates `media_decode_time_ms dominates`;
- `training_store_batch_latency_ms_p50 <= 0.50 * raw_decode_bottleneck_ms` OR `speedup_vs_raw_decode >= 2.0`.

The raw p50 threshold may remain as a secondary/general benchmark condition, but it must not override the decode-bottleneck-specific speedup path when the accepted raw bottleneck is media decode.

Rationale:

- This matches the normative spec fields `raw_media_decode_time_ms` and `speedup_vs_raw_decode`.
- It keeps existing metric fields stable instead of silently changing the meaning of raw batch p50.
- It directly answers whether the PFS Training Store removes the bottleneck that made raw bounded decode fail.
- It avoids broad changes to `PerfMetrics` and avoids new Model/Training/Data contract surface outside `autovla.dataloader.perf`.

## Minimal Allowed Source/Test Scope For Data Repair

Approved narrow Data repair scope:

- `autovla/dataloader/perf/training_store.py`
  - Compute `speedup_vs_raw_decode` from raw media decode/bottleneck latency, not raw batch p50.
  - Emit an explicit comparison field such as `raw_decode_bottleneck_ms` or `raw_comparison_latency_ms`.
  - Preserve existing raw p50/p95 fields for audit.
  - Do not list `raw_batch_latency_ms_p50` or `raw_media_decode_time_ms` as missing telemetry when numeric values are present.
- `autovla/dataloader/perf/report.py`
  - Update `classify_training_store_comparison()` to use the decode-bottleneck comparison path when raw decode dominates.
  - Keep `INSUFFICIENT_TELEMETRY` when the raw decode bottleneck metric is missing.
  - Preserve WARN for improvement below threshold if Product/Spec/Owner review later accepts foundation status.
- `tests/dataloader/test_perf_harness.py`
  - Add focused tests for the current paradox:
    - raw p50 lower than store p50;
    - raw media decode greater than store p50;
    - computed `speedup_vs_raw_decode >= 2.0`;
    - classification becomes PASS or threshold-appropriate result through the decode-bottleneck path.
  - Add a missing-raw-decode test that remains `INSUFFICIENT_TELEMETRY`.

Optional only if needed:

- `autovla/dataloader/perf/benchmark.py` if the source of raw baseline stitching needs to pass through raw classification reasons or explicit comparison basis.
- `autovla/dataloader/perf/MODULE.md` to document the comparison basis.

Do not change:

- dependency specs;
- `autovla/core/**`;
- Model or Training public APIs;
- `genesisvla/**`;
- Slurm scripts or compute policy;
- PR state, git index, or publication state.

## Docs And Tests

Tests should be updated. The repair is a metric-contract change and must have focused regression coverage around raw decode bottleneck comparison.

Docs should be updated only if current docs imply that `speedup_vs_raw_decode` uses raw batch p50. Minimal acceptable doc wording:

- raw batch p50 and raw media decode are separate metrics;
- PFS Training Store comparison uses raw decode bottleneck when media decode is the raw failure reason;
- local cache/NVMe staging remains out of scope.

## Reclassification Of Current Compute Result

Do not reclassify the current compute result without a source fix and regenerated report.

The current canonical compute and manager reports say `FAIL_COMPUTE`; the current JSON evidence embeds `speedup_vs_raw_decode=0.310513` and store `FAIL`. Architecture should not override those artifacts by narrative reinterpretation.

After the source fix, the same raw/store numeric values would likely pass the decode-bottleneck speedup path because `25.963794 / 9.233619` is approximately `2.81`, but acceptance must come from regenerated store-read evidence and Owner/Quality review, not a manual report edit.

## Safety And No-Scope-Creep Checks

- No real training, finetune, model/checkpoint/tokenizer load, HF/W&B network, endpoint, robot, full dataset conversion, or full media predecode is needed for the repair.
- No dependency change is needed.
- No `genesisvla` compatibility shim is needed.
- No M1/M2/Model/Training public contract drift is needed.
- Generated store artifacts remain ignored task evidence under `runs/tmp`.
- PR #14 should remain draft until repaired evidence is regenerated and reviewed.

## Validation Plan For Repair

After Data repair:

- Focused pytest for `tests/dataloader/test_perf_harness.py`.
- Full dataloader pytest if lightweight and already part of task practice.
- Ruff/Black/Pyright through current project-local tooling or the accepted wrapper workaround.
- `git diff --check`.
- Static scans for no dependency changes, no generated binary/media artifacts, no `genesisvla` shim, and no real runtime scope.
- One regenerated bounded store-read compute evidence pass, coordinated by Compute/HPC, to replace the current failed comparison.

## DevSpace MCP Compliance

DevSpace MCP: no. No `vla-flywheel-devspace`, MCP connector, `open_workspace`, or MCP read/write/edit/bash was used as workflow or evidence.

## Subagent Ledger

Child subagents: none used.
Retired: yes.

## Conclusion

APPROVE_METRIC_REPAIR_PLAN
