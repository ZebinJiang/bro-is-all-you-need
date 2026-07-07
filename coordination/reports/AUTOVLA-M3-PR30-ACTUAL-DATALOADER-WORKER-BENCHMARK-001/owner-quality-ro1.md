# AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 Quality RO1 Plan

## Decision

Conclusion: APPROVE_TEST_PLAN

Quality approves the read-only acceptance/scans plan for the actual dataloader/native-loader worker benchmark. The future acceptance token `PASS_ACTUAL_DATALOADER_BENCHMARK_READY_FOR_USER_REVIEW` requires real measured worker evidence, raw-JSON-to-doc traceability, scan-clean publication scope, and PR #30 remaining open/draft. If the implementation is useful but cannot meet every fairness/traceability gate, the publishable fallback token is `REQUEST_CHANGES_DRAFT_PR_UPDATED`.

## Workspace Verification

- Role: 60-OWNER · Quality
- Dispatch override recorded: model=gpt-5.5, thinking=high; no xhigh/max used in this report.
- DevSpace MCP: not used.
- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- Workspace status at RO1:
  - Branch tracks `origin/dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`.
  - Untracked task card present: `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`.
- Expected starting HEAD: matched.
- PR #30 requirement: must remain open/draft; RO1 did not live-mutate or live-query PR #30.
- Shell note: commands print `whoami: cannot find name for user ID 2000`; this is environment identity noise and did not affect command results.

## Inputs Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `.agent-docs/git_workflow.md`
- `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- `README.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `tests/dataloader/test_fair_native_loader_bakeoff.py`

Current baseline observations:

- PR30 adapter-v1 evidence is explicitly diagnostic-only.
- Existing docs say `worker_count_label=configured_8` and `actual_worker_count=not_measured`.
- Existing tests cover fair materialized payloads, adapter-v1 stage outputs, camera-ref rejection, required timing fields, invalidation docs, and CLI help.
- Existing tests do not yet prove actual dataloader worker execution; this is the core new acceptance gap.

## Quality Gate Overview

The next implementation must add an actual worker benchmark, not another configured-worker label. Quality will block or request changes if the evidence only proves that `worker_count=8` was requested, configured, or displayed.

The benchmark must prove:

1. The same source sample/window manifest is used across all candidates.
2. Each candidate emits materialized RGB/state/action/action_mask/language payloads, not `camera_refs` or path-only payloads.
3. Dataloader/native-loader workers actually executed, with observed worker identities and per-worker work attribution.
4. README and benchmark docs derive numeric claims from task-local raw JSON and command logs.
5. Generated artifacts remain under `runs/tmp/**` and `datasets/working/**`, ignored/untracked.
6. No source dataset, dependency, model/checkpoint/tokenizer, HF/W&B, endpoint, robot, or training surface is mutated or executed.

## Anti-Cheating Checks

Required tests and evidence must reject these failure modes:

- `actual_worker_count` equals configured label without observed worker ids.
- `worker_count_label=configured_8` is reported as actual W8 evidence.
- A single-process loop is reported as dataloader-worker execution.
- Worker ids are fabricated constants rather than collected from worker context/process identity.
- Per-worker sample counts are absent, all zero, or inconsistent with total measured samples.
- A worker reports activity but has no batch/sample attribution.
- The benchmark changes sample windows, batch size, materialization contract, candidate list, or payload fields between candidates.
- Converted candidates use cached/persistent rows while raw uses a different, non-materialized comparison path, unless the report labels the rows non-comparable and refuses winner selection.
- The code preloads all `SourceSample` payloads before timing and then reports the timing as native dataloader-worker performance.
- `camera_refs`, path-only media refs, or precomputed payload objects are accepted as materialized RGB payloads.
- `not_measured`, `unknown`, `null`, blank, or omitted values appear in required RUN rows for worker evidence, timing, payload completeness, or traceability fields.

Minimum actual-worker evidence fields:

- `requested_worker_count`
- `observed_worker_count`
- `worker_execution_mode`
- `worker_ids`
- `worker_sample_counts`
- `worker_batch_counts`
- `total_batches`
- `total_samples`
- `per_worker_first_sample_id` or equivalent provenance
- `worker_evidence_status`
- `actual_worker_count_source`
- command/log path that generated the row

Quality pass criteria:

- For an actual W8 claim: `observed_worker_count == requested_worker_count == 8`, all eight worker ids have nonzero attributed work, and totals reconcile with row sample/batch counts.
- If fewer workers actually execute, the row may be published only as REQUEST_CHANGES or non-comparable diagnostic evidence, not as PASS actual-W8 evidence.

## Traceability / Consistency Audit

Every README/doc number must trace back to raw JSON and command logs.

Required raw evidence paths:

- `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/<run>/actual-dataloader-worker-bakeoff.json`
- matching `.csv` and `.md` tables
- generated artifact ledger
- shared sample/window manifest
- command log containing the exact command, environment, start/end timestamps, exit code, and output root
- compute log/status if run on a compute node

Required consistency checks:

- README candidate rows match raw JSON values exactly or with documented rounding.
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md` matches the raw JSON.
- `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md` lists each published number, raw JSON pointer/path, command log path, and pass/fail status.
- PR body must cite the same evidence root and cannot introduce numbers absent from raw JSON.
- Existing adapter-v1 numbers in `ADAPTER_PERFORMANCE_AUDIT_PR30.md` and `FAIR_NATIVE_LOADER_BAKEOFF_V2.md` must remain labelled diagnostic-only unless superseded by actual-worker evidence.
- Any older PR30 unfair/preloaded numbers must remain invalidated.

Required test shape:

- A focused test should parse the generated actual-worker JSON fixture and assert README/doc rows match raw JSON.
- A focused test should fail if a doc table contains an untraceable numeric value.
- A focused test should fail if a raw JSON RUN row lacks command/log provenance.
- A focused test should fail if doc wording claims final backend winner without Product/Data/Architecture approval.

## Required Tests And Local Gates

Login-node-safe checks before compute:

- `runs/tmp/m1-tool-venv/bin/python -m py_compile <changed-python-files>`
- Focused tests:
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_fair_native_loader_bakeoff.py -v`
  - New actual-worker tests, likely in `tests/dataloader/test_actual_dataloader_worker_bakeoff.py` or equivalent.
- Broader safe tests:
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader tests/meta -q`
- Ruff:
  - `runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' <changed-python-and-test-paths> tests/meta`
- Pyright:
  - `runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json <changed-python-and-test-paths>`
- Black:
  - Prefer single-file changed-path checks with `--workers 1`.
  - If combined Black hangs, record timeout and use single-file checks as bounded fallback.
- `git diff --check`
- JSON parse:
  - all generated run JSON
  - generated artifact ledger
  - shared sample/window manifest
  - consistency audit JSON if produced

Project wrapper:

- Use direct root project-local tools when the worktree lacks its own `runs/tmp/m1-tool-venv` readiness stamp.
- Do not install dependencies or fill wheelhouse in this Quality task.
- A wrapper failure caused only by missing worktree-local readiness stamp is not a source/test failure. A missing package or broken root project-local env is `BLOCKED_TOOL_ENV`.

Compute/runtime validation:

- Actual dataloader-worker benchmark execution is compute-node work unless explicitly bounded as lightweight by Compute/HPC.
- No GPU200/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot execution is allowed.
- If compute routing is unavailable, the correct blocker is `BLOCKED_COMPUTE_ENV` or task-specific execution blocker, not a fake PASS.

## Generated Artifact And Forbidden-Path Scans

Before publication, run or provide equivalent evidence for:

- `git diff --name-only`
- `git status --short --ignored -uall -- runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 datasets/working/autovla_actual_worker_bakeoff_v1 docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
- `git ls-files runs/tmp datasets/working datasets/readonly checkpoints`
- dependency/protected path scan:
  - `pyproject.toml`
  - `requirements/**`
  - `Makefile`
  - `.github/**`
  - `scripts/quality/**`
  - `AGENTS.md`
  - `datasets/readonly/**`
  - `checkpoints/**`
  - `code-input/**`
- secret/private endpoint scan over changed text and staged content.
- artifact extension scan over staged files and candidate publication paths for `.pt`, `.pth`, `.ckpt`, `.safetensors`, `.onnx`, `.bin`, `.parquet`, `.arrow`, `.npy`, `.npz`, `.zip`, `.tar`, `.tar.gz`, `.tgz`, `.zst`, `.mp4`, `.avi`, `.mov`, `.jpg`, `.jpeg`, `.png`, `.webp`.
- large-file scan over staged files.
- large text-diff scan.
- hidden/bidi control scan over changed text files.

Pass criteria:

- `runs/tmp/**` and `datasets/working/**` may contain ignored generated evidence only; they must not be staged or tracked.
- `datasets/readonly/**` must remain unmodified.
- No dependency files may change.
- No generated dataset/media/checkpoint/model artifact may be publication material.
- No PR #16 mutation or dependency-route bleed-through.

## PR30 Draft Update Expectations

PR #30 must remain:

- open
- draft
- base `main`
- head branch `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- not marked ready
- not merged

Draft PR body update should include:

- status token:
  - `PASS_ACTUAL_DATALOADER_BENCHMARK_READY_FOR_USER_REVIEW` when all gates pass, or
  - `REQUEST_CHANGES_DRAFT_PR_UPDATED` when the update is useful but fairness/worker/traceability evidence is incomplete.
- exact commit SHA
- exact evidence root
- raw JSON/log traceability summary
- actual worker evidence summary
- candidate comparability status for D1-D5 and optional D6 if present
- explicit no-final-backend-winner unless all fairness gates and Owner decisions approve stronger wording
- generated artifact exclusion statement
- source dataset immutability statement
- no dependency diff
- no GPU200/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot

Publication must use explicit pathspecs only. Do not use `git add .`, `git add -A`, or `git add -u`.

## REQUEST_CHANGES_DRAFT_PR_UPDATED Publishability

`REQUEST_CHANGES_DRAFT_PR_UPDATED` is publishable when:

- the branch update is scan-clean;
- PR #30 remains draft/open;
- the evidence clearly identifies the blocker;
- docs/PR body do not overclaim;
- generated artifacts remain ignored/untracked;
- the update improves traceability, tests, instrumentation, or blocker clarity.

Examples of publishable REQUEST_CHANGES states:

- actual worker count is less than requested, but correctly reported with no false W8 claim;
- D1-D5 were attempted but one candidate is fail-closed with exact blocker and no winner selected;
- compute-node execution produced logs but fairness comparability failed;
- README/docs are updated to say the benchmark is blocked or non-comparable with exact evidence;
- PR #30 remains a draft review artifact, not ready/merge material.

Not publishable:

- fabricated actual worker evidence;
- missing raw JSON/log traceability for published numbers;
- generated artifacts staged;
- dependency/protected-path changes without authorization;
- any source dataset mutation;
- any final winner/training readiness claim without full evidence and Owner approval.

## Known Risks / Blockers

- The task starts from a state where adapter-v1 docs explicitly say `actual_worker_count=not_measured`; the new task must not silently reinterpret those numbers as actual worker evidence.
- Existing `tests/dataloader/test_fair_native_loader_bakeoff.py` needs additional actual-worker/traceability tests before a PASS acceptance.
- Compute/HPC routing is required for any non-lightweight actual-worker benchmark run.
- New docs may be ignored by repository policy and need explicit publication handling.
- Untracked active task card is present at RO1; publication must decide whether it is intended governance publication material or local task-state only.

## Compliance And Ledger

- DevSpace MCP / vla-flywheel-devspace / open_workspace / MCP read/write/edit/bash: not used.
- Source/test/docs mutation by Quality: none. Only this report was written.
- Git/PR mutation: none. No stage, commit, push, PR update, ready, merge, reset, restore, clean, or stash.
- Dependency install/recovery: not run.
- GPU200/training/Slurm/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: not run by Quality RO1.
- Subagent ledger: none used.
- Retirement: Quality RO1 planning complete; retired yes.
