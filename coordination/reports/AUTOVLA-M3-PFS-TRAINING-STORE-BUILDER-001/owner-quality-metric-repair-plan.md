# Quality Owner Metric Repair Plan

## Scope

- Role: 60-OWNER Quality
- Task: AUTOVLA-M3-PFS-STORE-METRIC-REPAIR-001
- Parent task: AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001
- Mode: read-only quality planning plus this report write only
- Conclusion: APPROVE_METRIC_REPAIR_PLAN

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- Branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- Status summary: PR #14 candidate diffs are present in `autovla/dataloader/perf/**`, `tests/dataloader/test_perf_harness.py`, and the existing wrapper recovery file `scripts/quality/autovla_check_project_local.sh`; report evidence under `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/**` remains untracked. This planning task did not modify source, tests, git index, PR state, or compute artifacts.
- UID warning observed: shell startup prints `whoami: cannot find name for user ID 2000`; no OS identity repair attempted.

## Evidence Reviewed

- `autovla/dataloader/perf/report.py`
- `autovla/dataloader/perf/benchmark.py`
- `autovla/dataloader/perf/training_store.py`
- `tests/dataloader/test_perf_harness.py`
- `coordination/tasks/active/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001.yaml`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-compute-execute.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/manager-summary.md`
- `coordination/reports/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/owner-data-metric-repair-plan.md`

## Quality Decision

Quality approves one bounded metric-contract repair. The repair should make the Training Store comparison denominator explicit instead of silently comparing store read latency against raw batch p50 when the raw failure basis is media decode time.

Quality does not approve reclassifying compute job 1833 without a code/test change. The current task card and compute report both classify the result as `FAIL_COMPUTE`, and the active classifier uses `raw_batch_latency_ms_p50`. Job 1833 may be cited as motivating evidence only until the metric contract is changed, tested, and rerun.

## Required Test Changes

Data must add or update tests that make the comparison contract executable:

1. Add a regression test using the observed job 1833 values:
   - raw batch p50: `2.86716`
   - raw media decode time: `25.963794`
   - store read p50: `9.233619`
   - expected effective raw baseline: `25.963794`
   - expected effective speedup: greater than `2.0`
   - expected classification: `PASS`, unless Architecture explicitly chooses an owner-approved `WARN` policy.
2. Add assertions that the report exposes the comparison basis, for example:
   - `raw_effective_batch_latency_ms_p50`
   - `raw_effective_batch_latency_ms_p95`
   - `raw_comparison_basis`
   - `speedup_vs_raw_decode` derived from the effective baseline
   - preserved raw evidence fields such as `raw_batch_latency_ms_p50` and `raw_media_decode_time_ms`
3. Add a fallback test where `raw_media_decode_time_ms` is missing or not numeric, proving the classifier falls back to raw batch p50 or returns `INSUFFICIENT_TELEMETRY` with an actionable reason.
4. Add a non-media-dominated test proving the legacy raw-batch-p50 comparison remains the basis when media decode does not exceed raw batch p50.
5. Update `test_store_read_benchmark_should_compare_against_raw_decode` to require the new comparison-basis fields and to prevent missing-telemetry output from listing raw fields that were successfully stitched into the report.
6. Keep `decode_avoided_ratio == 1.0`, checksum verification, manifest schema, and no-write-outside-output-dir expectations intact.

Quality prefers the Data proposal to compute an effective baseline with `max(raw_batch_latency_ms_p50, raw_media_decode_time_ms)` rather than summing values, because it avoids double-counting while preserving the raw bounded-decode evidence. If Architecture selects a different contract, Data must update the tests first and record the rationale before implementation.

## Required Local Validation

After the repair, the local login-node-safe gate must include:

```text
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_perf_harness.py -q
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q
runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf tests/dataloader/test_perf_harness.py
runs/tmp/m1-tool-venv/bin/pyright -p pyrightconfig.autovla.json
git diff --check
```

Black evidence must use the previously accepted bounded workaround if directory or batch Black still hangs:

```text
runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 <changed-python-file>
```

Run it file-by-file over every changed Python file in `autovla/dataloader/perf/**` and `tests/dataloader/test_perf_harness.py`. Do not pass Markdown files to Black.

If the wrapper recovery diff remains in scope, also run:

```text
bash -n scripts/quality/autovla_check_project_local.sh
bash scripts/quality/autovla_check_project_local.sh
```

If the full wrapper is blocked by the known Black hang or tool environment, record the exact blocker instead of treating it as a pass.

## Required Safety Scans

The repair validation must include:

- Changed-file scope scan limited to `autovla/dataloader/perf/**`, `tests/dataloader/test_perf_harness.py`, already-authorized quality wrapper changes, and governance/evidence reports.
- Dependency diff scan: no `pyproject.toml`, lockfile, requirements, or package-manager changes.
- Compatibility-shim scan: no `genesisvla/**` package, import alias, CLI alias, or make-target compatibility shim.
- Generated artifact scan: no store shards, `*.npz`, generated `*.jsonl`, run output, dataset cache, checkpoint, model weight, media artifact, or `runs/tmp/**` staged for publication.
- Secret/private endpoint scan over changed text diff.
- Dataset immutability scan: no writes into `datasets/readonly` and no source dataset mutation path.
- External runtime scan: no real training, model load, tokenizer load, checkpoint load, HF/W&B network, endpoint, robot, GPU, or Slurm command in the local repair wave.

## Required Compute Rerun

After code and tests pass, Quality requires one bounded compute rerun before accepting the metric repair for publication readiness:

1. Run through the governed Compute Owner path, not from Quality.
2. Use the corrected metric contract and current repair commit/diff.
3. Prefer a store-read rerun against the existing checksum-verified Training Store if Data/Architecture confirm build schema migration is unnecessary. Rebuild only if the accepted contract changes persisted build-report schema or store artifact generation.
4. Record:
   - node/job id and command provenance;
   - `checksums_verified == true`;
   - store manifest/schema present;
   - raw batch p50/p95, raw media decode, effective raw baseline, comparison basis, store p50/p95, and effective speedup;
   - missing telemetry list, with raw baseline fields absent from missing telemetry when present;
   - no real training/model/data conversion/HF/W&B/endpoint/robot behavior.
5. Accept `PASS` only if the corrected classifier reports PASS under the owner-approved contract, such as effective speedup at least `2.0` or store p50 at most half the effective raw baseline.
6. Accept `WARN` only if all relevant Owners explicitly approve a weaker but defensible publication gate, with rationale recorded. `WARN` must not be inferred by Quality alone.
7. Keep `FAIL` if the corrected classifier still fails, checksum verification is false, raw effective baseline is missing, or the store path remains I/O dominated without a defensible improvement.

## Publication Rule

PR #14 must remain draft/unmerged until all of the following are true:

- Metric-contract repair is implemented with red/green tests.
- Local focused tests, static checks, formatting evidence, diff checks, and scans pass or have explicit Owner-approved blocker handling.
- Compute rerun returns `PASS`, or returns an explicit Owner-approved `WARN`.
- Product/Spec, Data, Architecture, Tooling, Compute, and Quality reports agree the new contract is publication-safe.
- Exact-head CI evidence is green before ready/merge consideration.

Do not publish or merge based on retroactive reinterpretation of job 1833 alone. The PR body must describe the metric contract, the comparison basis, the compute evidence, and any residual WARN if applicable.

## DevSpace MCP Compliance

DevSpace MCP, `vla-flywheel-devspace`, `open_workspace`, MCP read/write/edit/bash, and MCP connectors were not used as internal workflow or evidence.

## Subagent Ledger

- Child/subagents used: none.
- Retirement: retired yes after this report.

## Conclusion

APPROVE_METRIC_REPAIR_PLAN
