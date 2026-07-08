# Product/Spec R1 Publication Wording Review

Task: `AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001`
Role: `70-OWNER · Product/Spec`
Runtime override recorded: `model=gpt-5.5`, `thinking=high`
Decision: `APPROVE_PUBLICATION_WORDING`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- Required baseline HEAD before current local diffs: `882b24af518fe1676fdb5430e52d3877d018084a`
- `git status --short --branch --ignored -uall`: current local diffs include tracked changes to `README.md`, `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`, `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`, `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`, source/test files outside this Product/Spec write scope, task-owned untracked reports, and ignored `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`.

## Reviewed Docs And Evidence

- `README.md` PR30 section
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
- `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w3-docs.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-w2.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-compute-benchmark-w2.md`

## Findings

Public wording is honest and reviewable for a draft PR. The docs identify Compute-W2 as bounded dataloader benchmark evidence through the project wrapper, not as training, GPU200 model execution, fine-tuning, model quality, deployment, endpoint, robot, or production-readiness evidence.

No backend winner is claimed. The docs preserve `NO_BACKEND_WINNER`, `REQUEST_CHANGES_REMAIN`, and `NO_BACKEND_WINNER_INSUFFICIENT_NATIVE_V21_AND_METRICS` in the top-level README/status surfaces. D4 WebDataset tar is described only as fastest among bounded runnable rows, and `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md` explicitly says the ranking is not a final backend winner.

The request-changes posture remains clear. D1a native v21 remains `NOT_RUN_UNSAFE_OR_UNAVAILABLE`, D6 zarr remains `NOT_IMPLEMENTED_IN_CURRENT_PR`, and prompt-contract missing telemetry / metric completeness gaps remain blocking. The user-visible next action is therefore to clear the native-v21 safety route and prompt-contract metric completeness before any backend-selection or merge-ready claim.

The PR-facing docs are suitable for draft PR review, not merge readiness. They support reviewer discussion of bounded Compute-W2 metrics while keeping the result in a conservative request-changes state.

## Ignored Markdown Publication Issue

`docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md` exists but is ignored by the broad Markdown ignore rule:

- `git check-ignore -v docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`: `.gitignore:235:*/**/*.md`
- `git ls-files` does not list `docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`
- `git status --short --ignored -uall` shows it as `!! docs/benchmarks/PR30_FINAL_DATALOADER_PERFORMANCE.md`

This is not a Product/Spec wording blocker because README avoids a Markdown link to that ignored file and describes it as a detailed final evidence draft requiring Quality publication handling if it should become PR-visible. If final PR #30 publication intends that draft doc to appear, Quality/publisher must explicitly force-add the exact path or keep it out of the PR-facing link surface.

## Residual Communication Risks

- Reviewers may still overread the primary ranking as a winner unless PR summary text repeats `NO_BACKEND_WINNER` and `REQUEST_CHANGES_REMAIN`.
- `PR30_FINAL_DATALOADER_PERFORMANCE.md` is useful but currently ignored; publication handling must be explicit before relying on it as a PR-visible doc.
- The README still contains historical next-action context alongside PR30-specific blockers. This is acceptable for draft review, but PR summary should foreground the PR30 blockers: D1a native route, D6 zarr absence, and prompt-contract metric completeness.

## Compliance

- DevSpace MCP: not used.
- Read-only review: yes, except this assigned Product/Spec report write.
- Source/tests/config/docs/runtime evidence edits by Product/Spec: none.
- Stage, commit, push, PR mutation, merge, mark-ready: not performed.
- External effects: none.
- Subagent ledger: none used.
- Retirement status: retired yes.

## Conclusion

`APPROVE_PUBLICATION_WORDING`
