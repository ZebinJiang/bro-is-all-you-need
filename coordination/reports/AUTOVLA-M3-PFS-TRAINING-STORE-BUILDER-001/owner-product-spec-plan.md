# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Product/Spec Acceptance Criteria

## Role And Mode

- Role: `15-OWNER - Product/Spec`
- Task: `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001`
- Stage: Wave 1 read-only acceptance criteria review
- Dispatch policy recorded: `thinking=xhigh`
- Allowed write used: this Owner planning report only.

## Workspace Verification

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Required branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- Observed branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- Required HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Observed HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Status: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
- No file/git/PR mutation was performed except this allowed report write.

## Evidence Reviewed

- Governance:
  - `AGENTS.md`
  - `boundaries.txt`
  - `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- Task-local evidence discovery:
  - `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/` exists but was empty before this report.
  - `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/` exists but was empty at review time.
  - No task-local card/spec file for this exact task ID was found under `coordination/tasks`, `coordination/reports`, `runs/tmp`, or `docs`.
- Local PR #14 summary evidence:
  - `coordination/reports/AUTOVLA-M3-PR13-MERGE-AND-DATALOADER-PERF-HARNESS-001/manager-summary.md`
- Roadmap/spec surfaces:
  - `docs/architecture/ROADMAP.md`
  - `docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md`
  - `docs/architecture/FAST_TRAINING_VIEW.md`
  - `autovla/dataloader/perf/MODULE.md`
- Current threshold/test surfaces:
  - `autovla/dataloader/perf/report.py`
  - `tests/dataloader/test_perf_harness.py`
- Current perf evidence:
  - `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output/perf_report.md`
  - `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output/perf_report.json`
  - `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output-decode/perf_report.md`
  - `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/perf-output-decode/perf_report.json`
  - `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/baseline-comparison-report.md`

No live PR query was required because a local PR #14 Manager summary was available.

## Current Product Context

PR #14 is a draft foundation for the DataLoader Performance Harness. Local summary evidence says the implementation and scans were broadly green, but the authorized compute-node bounded-decode probe classified the current dataset media path as `FAIL` because `media_decode_time_ms` dominates per-batch time.

This means PR #14 is product-appropriate to review as a draft, but it must not be described as merge-ready or as having solved input-pipeline readiness for fine-tune. `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001` should be treated as the next scoped response to that performance blocker.

## Threshold Baseline

Current classifier behavior in `autovla.dataloader.perf.report.classify_perf_report()`:

- `FAIL` when `data_wait_time_ms / compute_placeholder_time_ms > 2.0`.
- `FAIL` when `media_decode_time_ms > max(batch_latency_ms_p50 * 0.5, 1.0)`.
- `FAIL` when `tokenization_time_ms > max(batch_latency_ms_p50 * 0.2, 1.0)`.
- `FAIL` when `collate_time_ms > max(batch_latency_ms_p50 * 0.25, 1.0)`.
- `WARN` when no fail reason exists and `data_wait_time_ms / compute_placeholder_time_ms > 0.5`.
- `INSUFFICIENT_TELEMETRY` when no fail/warn reason exists but GPU telemetry is missing.
- `PASS` only when no obvious dataloader bottleneck exists and telemetry is sufficient.

Current evidence:

- Metadata-only probe: `INSUFFICIENT_TELEMETRY`, with GPU/CPU/RSS telemetry missing but no decode bottleneck.
- Bounded-decode probe: `FAIL`, with `media_decode_time_ms = 25.963794` and `batch_latency_ms_p50 = 2.86716`.
- Baseline comparison: historical baseline run had significant dataloader wait signals, and current bounded probe remains bounded and not real training.

## PFS Training Store Acceptance Criteria

### Required Scope

The PFS Training Store Builder may implement a foundation for an optimized training-store path, but only as a bounded data/readiness surface:

- derive store/index/cache artifacts only from approved dataset metadata or bounded compute-authorized reads;
- write derived outputs only under governed project paths such as `datasets/working/**`, `datasets/cache/**`, or task-local `runs/tmp/**`, as specified by the implementation plan;
- keep original data under `datasets/readonly/**` immutable;
- emit manifest, schema version, source dataset fingerprint, transform/statistics fingerprint references, sample/episode index metadata, cache/predecode policy, and lifecycle/cleanup notes;
- provide deterministic rerun behavior or record any nondeterministic input explicitly;
- include validation evidence proving no generated payload is staged for publication.

### Required Non-Goals

The task must not expand into:

- real fine-tuning or model training;
- model, tokenizer, checkpoint, W&B/HF, endpoint, or robot behavior;
- full dataset conversion unless separately authorized with exact output path and storage policy;
- committed media/cache/checkpoint/model artifacts;
- dependency changes unless a separate Tooling/Product decision approves them;
- login-node bounded-decode or other heavy validation;
- merge-ready claims while the performance classifier remains `FAIL`.

### PASS Criteria

`PASS` for this task means all of the following:

- PFS builder scope, manifests, outputs, cleanup policy, and docs are implemented and reviewed without violating dataset immutability or generated-artifact publication policy.
- Local/static gates and authorized compute-node probes pass.
- The relevant PFS-backed probe produces classifier `PASS` or a Product/Spec-accepted non-bottleneck telemetry status.
- The previous media-decode blocker is demonstrably removed from the training hot path, not merely hidden by missing metrics.
- User-visible docs and PR text state exactly what was built and do not claim real fine-tune or model support.

### WARN Criteria

`WARN` is acceptable as a foundation PR only when all of the following are true:

- No classifier `FAIL` remains for the PFS-backed path.
- Remaining warning is bounded and explained, such as moderate data-wait ratio, missing optional telemetry, partial cache coverage, or small-sample uncertainty.
- The PR is explicitly described as foundation/readiness work, not as solved production training performance.
- The PR includes concrete next-step issues or task recommendations for the warning.
- Quality, Data, Architecture, and Product/Spec all agree the warning does not hide a correctness, dataset safety, artifact publication, or runtime-authorization violation.

Product/Spec position: Owner-approved `WARN` may be acceptable as a foundation PR if the claim boundary is strict. It should not be used to authorize real fine-tune, runtime training, or M4 readiness.

### FAIL Criteria

`FAIL` must block performance-success claims and normal merge readiness when any of these are present:

- media decode still dominates the PFS-backed per-batch path;
- data wait dominates compute placeholder time;
- tokenization or collate time crosses the existing fail thresholds;
- the builder writes into `datasets/readonly/**` or stages generated dataset/cache/media artifacts for publication;
- missing telemetry prevents proving that the PFS path actually removed the prior bottleneck;
- the PR claims real training, model support, endpoint/robot readiness, or fine-tune readiness beyond planning/foundation scope.

## User-Visible Claim Boundaries

Allowed claims:

- "PFS Training Store foundation/scaffold."
- "Derived manifests/index/cache policy and bounded validation evidence."
- "Intended to remove slow interchange-loader behavior from the future training hot path."
- "`WARN` accepted only as foundation evidence, with explicit remaining risk."

Forbidden claims:

- "Ready for real GR00T fine-tune."
- "Training performance solved."
- "Production training store ready."
- "Model/data pipeline complete."
- "GPU starvation resolved" without telemetry-backed compute evidence.
- "Merge-ready despite classifier `FAIL`."

PR text must preserve draft/foundation wording unless a later exact-head review accepts the final classifier evidence and publication scans.

## Next Strategy If PFS Remains FAIL

If PFS Training Store remains `FAIL`, Product/Spec recommends stopping before merge-ready publication and returning to a user/Manager performance strategy decision:

1. Classify the active fail reason:
   - media decode dominance;
   - data wait dominance;
   - tokenization/collate dominance;
   - missing telemetry that blocks proof.
2. For media decode dominance, compare at least two bounded strategies before broader implementation:
   - predecoded frame cache;
   - local media staging/cache;
   - packed shard layout with sample-to-shard index.
3. For data wait dominance, prioritize packed shard/index layout, deterministic sampler state, queue-depth telemetry, and local NVMe staging evidence.
4. For tokenization/collate dominance, add pretokenized language policy or packed collate layout only under separate scoped acceptance.
5. If storage footprint or lifecycle is unclear, ask for user decision before materializing a persistent cache.
6. Keep PR #14 and follow-up PFS work as draft/foundation until a bounded compute-node probe no longer returns `FAIL`.

If the team cannot reduce the classifier below `FAIL` with bounded PFS work, the correct conclusion becomes `READY_FOR_USER_DECISION_PERF_STRATEGY`, not an implementation workaround or relaxed threshold.

## DevSpace MCP Compliance

- DevSpace MCP: no.
- `vla-flywheel-devspace`, MCP connectors, `open_workspace`, MCP read/write/edit/bash, and DevSpace-derived evidence were not used.
- Review used local shell/git/file inspection only.

## Mutation Boundary

- No source, tests, docs, configs, dependencies, datasets, runtime outputs, git index, commit, branch, push, or PR state was modified.
- No network, Slurm, GPU, training, model, tokenizer, dataset conversion, W&B/HF, endpoint, or robot action was run.
- The only write was this allowed Owner planning report.

## Subagent Ledger

- Child subagents used: none.
- Child-agent depth used: 0.
- Active child contexts remaining: none.
- Retirement status: retired yes.

## Conclusion

APPROVE_ACCEPTANCE_CRITERIA
