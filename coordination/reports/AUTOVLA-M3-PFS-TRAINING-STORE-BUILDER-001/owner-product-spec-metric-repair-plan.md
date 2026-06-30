# AUTOVLA-M3-PFS-STORE-METRIC-REPAIR-001 Product/Spec Metric Repair Plan

Role: 15-OWNER - Product/Spec
Task: AUTOVLA-M3-PFS-STORE-METRIC-REPAIR-001
Parent task: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001
Stage: Product/Spec planning for PR #14 continuation

## Workspace Verification

- Worktree/pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Status note: worktree already contains uncommitted PR #14 continuation changes and task reports; this Product/Spec review writes only this assigned report.
- Dispatch policy: xhigh requested; no max-tier policy used.

## Evidence Reviewed

- `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-product-spec-plan.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/manager-summary.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-execute.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-execute.md`
- `.agent-docs/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-SPEC.md`
- Current comparison/report code and current generated benchmark evidence under `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/perf-store-read/perf_report.json`

Observed current metric conflict:

- Store read p50: `9.233619 ms`
- Raw media decode time: `25.963794 ms`
- Raw batch p50 currently used by classifier: `2.86716 ms`
- Current classifier compares store p50 to the smaller raw batch p50 and returns `FAIL`.
- Product/Spec accepts the Manager finding that current `raw_batch_latency_ms_p50` appears not to include the measured media read/decode bottleneck that the Training Store is intended to remove.

## Spec Decision

Do not silently redefine the existing `raw_batch_latency_ms_p50` field in place if it currently means the measured raw batch p50 excluding decode. That field should remain traceable to its original measured meaning, because overwriting its semantics would make PR #14 evidence difficult to audit and could create an apparent pass by changing the denominator.

The repair should introduce an explicit raw effective comparator for bounded-decode comparison, such as `raw_effective_bottleneck_latency_ms_p50` or `raw_effective_pipeline_latency_ms_p50`, and document its formula in the report/schema. Product/Spec preference is:

- Preserve `raw_batch_latency_ms_p50`.
- Preserve `raw_media_decode_time_ms`.
- Add an explicit effective comparator that includes the active raw decode bottleneck.
- Compute `speedup_vs_raw_decode` from the comparator it actually claims to measure, or rename/split the speedup field so the numerator is unambiguous.

The parent acceptance phrase `raw_batch_latency_ms_p50` should be repaired as a spec-contract issue by comparing Training Store read p50 against a declared raw effective bounded-decode latency, not against the current bare raw batch p50 when that p50 omits decode. Architecture/Data/Quality may choose the exact formula, but the formula must be explicit and auditable. Acceptable formulas include a conservative sequential total such as `raw_batch_latency_ms_p50 + raw_media_decode_time_ms`, or a bottleneck comparator such as `max(raw_batch_latency_ms_p50, raw_media_decode_time_ms)`, as long as the selected meaning is documented and used consistently in code, tests, and reports.

## Acceptance Interpretation After Repair

PASS is acceptable only if all of the following are true:

- The repaired report preserves original raw batch p50, raw media decode time, Training Store read p50, effective raw comparator, and formula.
- `training_store_batch_latency_ms_p50 <= 0.50 * raw_effective_bottleneck_latency_ms_p50` or the declared speedup field is `>= 2.0`.
- The active bottleneck is no longer `media_decode_time_ms` on the Training Store read path.
- The comparison was rerun on the approved bounded compute-node path and does not rely on manual reinterpretation of the prior failing JSON.
- No source dataset mutation, generated artifact leakage, dependency expansion, real training, model loading, GPU/CUDA use, W&B/HF operation, endpoint/robot behavior, or compatibility shim is introduced.

WARN is acceptable only if all of the following are true:

- Training Store read measurably improves the declared raw effective decode bottleneck, but does not meet the 50 percent or 2x threshold.
- Media decode is no longer the active bottleneck on the Training Store read path.
- Remaining bottleneck is clearly classified, for example PFS read overhead, index construction, serialization, or batch assembly, without claiming full performance success.
- Quality/Compute/Data evidence is complete enough for a foundation PR and every relevant Owner explicitly accepts the WARN.

FAIL remains required if any of the following are true:

- Store read is not materially faster than the declared effective raw comparator.
- The report continues to compare store read against a raw p50 that omits the measured decode bottleneck while claiming decode removal.
- `speedup_vs_raw_decode` is computed from a numerator that does not match its name or documented formula.
- Media decode remains the active Training Store read bottleneck.
- Telemetry is missing, inconsistent, or cannot support the classifier.
- The repair expands into runtime/training/model/data conversion/dependency/PR mutation scope outside PR #14's foundation scope.

With the current observed numbers, a repaired effective comparator that includes the measured `25.963794 ms` raw media decode bottleneck could plausibly convert the result from classifier `FAIL` to `PASS`, because the `9.233619 ms` store read is less than half of the raw decode component alone. That is Product/Spec acceptable only after the code/report schema is repaired and the bounded benchmark is rerun; this report does not retroactively reclassify the existing failing artifact.

## Owner-Approved WARN Position

Owner-approved WARN remains acceptable for PR #14 as a foundation PR only when the repair shows real decode-bottleneck improvement but the strict threshold is not met. In that case, PR #14 may be described as a bounded foundation for PFS Training Store v0 telemetry and comparison infrastructure, not as a completed performance win or production-ready dataloader.

WARN is not acceptable if the only issue is a misleading denominator that can be repaired to produce valid PASS evidence. In that case the next step should be metric/schema repair plus bounded rerun, not publication of a known classifier mismatch.

## Safety and Claim Boundaries

- PR #14 must remain within bounded PFS Training Store builder and benchmark comparison scope.
- No real training, fine-tuning allocation, model/tokenizer loading, dataset conversion, GPU/CUDA execution, W&B/HF operation, endpoint/robot behavior, dependency change, or compatibility shim is authorized by this Product/Spec plan.
- User-facing claims must say "bounded compute-node benchmark" and "foundation PR" unless repaired PASS evidence and Owner gates support stronger wording.
- Historical failed evidence should remain preserved; repaired evidence should be new evidence with clear schema/version/formula notes.
- Draft-to-ready, merge, and PR mutation remain out of scope for this Owner report.

## DevSpace MCP Compliance

DevSpace MCP: no. This Product/Spec review used local repository evidence only and does not rely on DevSpace MCP as internal workflow evidence.

## Subagent Ledger

- Subagents used: none.
- Child-agent depth: 0.
- Retired: yes.

## Conclusion

APPROVE_METRIC_REPAIR_PLAN
