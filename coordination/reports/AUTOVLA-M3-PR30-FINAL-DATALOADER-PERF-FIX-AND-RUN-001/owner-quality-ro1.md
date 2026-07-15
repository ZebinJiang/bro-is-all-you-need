# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Quality RO1

## Conclusion

APPROVE_TEST_PLAN

Quality approves the validation/publication gate plan for the final PR30 dataloader performance fix and compute run. The plan is strict enough to accept a final benchmark only if actual-worker, payload, timing, missing-metric, source-dataset, and generated-artifact contracts all pass; otherwise it keeps PR #30 as an open/draft request-changes update.

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `882b24af518fe1676fdb5430e52d3877d018084a`
- Required branch/head: PASS.
- PR #30 state requirement from task card: existing PR only, open/draft, no ready, no merge.
- Current local untracked state to preserve:
  - previous PR30 `manager-summary.md`
  - previous PR30 `owner-quality-w1-publication.md`
  - new active task card
  - generated ignored evidence under `runs/tmp/**`, `runs/slurm_debug/**`, and `datasets/working/**`

## Inputs Reviewed

- `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-quality-w1-publication.md`
- `README.md`
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
- `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
- Current git status and generated artifact status.

## Current-State Findings

- Current PR #30 head is the request-changes WIP commit `882b24af518fe1676fdb5430e52d3877d018084a`.
- The current module/test already expose the relevant guard surfaces: `actual_worker_count`, `BenchmarkBatch`, payload rejection, WebDataset row, RoboDM-style row, local-v3 row, ffmpeg materialization hook, aggregate recomputation, missing metric rows, and `NO_BACKEND_WINNER` / `REQUEST_CHANGES_REMAIN` semantics.
- Prior generated outputs and pycache evidence are ignored/untracked. They must remain excluded from publication.
- No dependency/protected path diff is present at RO1 inspection time.
- Worktree-local wrapper env is not required for this planning gate; direct validation should use the healthy root project-local toolenv unless the implementation wave explicitly changes that requirement.

## Recommended Fast Gate

After Data implementation, Quality should run these login-node-safe checks:

```bash
/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_actual_dataloader_worker_bakeoff.py -v
PYTHONPYCACHEPREFIX=runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/quality-pycache /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile <changed-python-files>
/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' <changed-python-source-and-tests>
/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json <changed-python-source-and-tests>
/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 <each-changed-python-file>
git diff --check
```

Required focused test coverage:

- actual worker counts are numeric and match observed workers for RUN rows;
- unmeasured worker rows cannot be RUN;
- `BenchmarkBatch` rejects camera-ref/proof-only/preloaded rows;
- WebDataset streaming/tar route is comparable and non-cheating;
- RoboDM-style candidate preserves explicit persistent/container grouping semantics;
- local-v3 cache/index behavior is explicit and not silently preloaded;
- v2.1 ffmpeg/materialization cost is included or D1 remains blocking;
- raw timing aggregate recomputation catches mismatches;
- missing/defaulted core metrics produce blocking rows;
- README/docs consistency tests prevent backend-winner or training-readiness overclaims.

## Compute-Node Evidence Requirements

Compute-W1 must provide wrapper-backed source-dataset evidence:

- project wrapper route and reproducibility command recorded;
- readonly source dataset path used as input only;
- no output under `datasets/readonly/**`;
- requested worker/matrix combinations executed with exit codes;
- output root under task-local `runs/tmp/**` and working generated root under governed `datasets/working/**`;
- D1-D5 mandatory candidates measured or explicitly fail-closed;
- D6 optional status explicit;
- per-batch timing rows, summary JSON/CSV/Markdown tables, source mutation check, generated artifact ledger, and command log index emitted;
- actual-worker count/process evidence present for RUN rows;
- missing timing/persistent/prefetch metrics block final PASS;
- no real training, GPU training, model/checkpoint/tokenizer load, HF/W&B network, endpoint, or robot behavior.

Quality must not accept final numeric ranking unless raw command logs, raw JSON, CSV/Markdown tables, and README/PR-body numbers agree.

## Final Gate

Final Quality validation must include:

- all fast gate commands above;
- parse/read checks for final compute output JSON, CSV, Markdown, and command logs;
- recomputation of p50/p95/p99 or equivalent aggregate values from raw per-batch timings;
- verification that all blocking rows in missing metric tables are either resolved or explicitly dispositioned;
- README and docs consistency scan;
- `git diff --check`;
- no dependency diff;
- no generated artifact tracking;
- no source dataset mutation;
- no secrets/private endpoints;
- no large/binary/model/checkpoint/dataset artifact files;
- PR #30 remains open/draft and is updated in place only.

## Publication Scan List

Before commit/push/PR update:

- changed-file scope scan includes only allowed source/tests/docs/coordination paths;
- `git ls-files runs/tmp runs/slurm_debug datasets/working datasets/readonly checkpoints` must not show generated publication candidates;
- dependency/protected scan covers `pyproject.toml`, `requirements/**`, `Makefile`, `.github/**`, `scripts/quality/**`, `AGENTS.md`, `code-input/**`, `datasets/readonly/**`, and `checkpoints/**`;
- ignored docs intended for PR visibility must be explicitly force-staged by narrow pathspec;
- staged scans must include `git diff --cached --check`, staged name/stat review, secret/private endpoint scan, generated path scan, dependency/protected scan, artifact-extension scan, large-file scan, and binary/non-UTF8 scan;
- do not stage `runs/**`, `datasets/working/**`, `datasets/readonly/**`, `checkpoints/**`, pycache, `.pytest_cache`, or `.ruff_cache`.

## Acceptance Criteria

Use PASS/final-draft-ready only when:

- required local gates pass;
- Compute evidence completes mandatory source-dataset matrix;
- D1 is safely measured or explicitly Owner/user-dispositioned;
- raw timing rows and summary aggregates agree;
- missing metric blockers are closed or accepted with explicit decision;
- docs/README/PR body are numerically consistent and conservative;
- scans show no generated/protected/dependency/secret/artifact issue.

Use REQUEST_CHANGES when:

- candidate is publication-safe as draft evidence but final benchmark blockers remain;
- PR body/docs must list exact remaining blockers and preserve do-not-merge posture.

Use BLOCKED_METRICS_INSTRUMENTATION at task level when:

- timing, persistent/prefetch, raw aggregate, or actual-worker instrumentation cannot produce required evidence.

Use BLOCKED_SCAN when:

- generated artifacts, datasets, checkpoints, private endpoints/secrets, dependency drift, or protected paths appear in candidate/staged publication files.

Use BLOCKED_TOOL_ENV when:

- root project-local toolenv is unavailable and no authorized recovery path exists.

Use BLOCKED_SCOPE when:

- worktree/branch/head/PR state/scope differs from the task card, or PR #30 would be marked ready/merged/duplicated.

## DevSpace MCP Compliance

DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash were not used.

## Subagent Ledger

- Subagents used: none.
- Review mode: direct read-only Quality Owner planning.
- Retired: yes.
