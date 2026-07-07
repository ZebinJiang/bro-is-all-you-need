# AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001 Quality Gate Plan

## Decision

Conclusion: PASS

Quality approves the acceptance/gate plan for a bounded native-adapter performance audit and optimization pass on PR #30. The future publication conclusion `PASS_ADAPTER_AUDIT_DRAFT_READY_FOR_USER_REVIEW` is allowed only after the validation matrix below passes and the PR remains draft/open with no generated artifact, dependency, protected-path, or source-dataset mutation leak.

## Workspace Verification

- Role: 60-OWNER · Quality
- Dispatch override recorded: model=gpt-5.5, thinking=high; no xhigh/max used in this report.
- DevSpace MCP: not used.
- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `f194b6e8d3d6679448749da36e6bfc68f690ef91`
- Status: clean against `origin/dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`.
- PR state requirement for later gate: PR #30 must remain draft/open until all Owners approve and user/Manager explicitly authorizes publication progression.
- Shell note: commands print `whoami: cannot find name for user ID 2000`; this is environment identity noise and did not affect read-only command results.

## Current Evidence Baseline

Current fair-v0 evidence reviewed:

- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/manager-summary.md`
  - Conclusion: `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
  - Points to corrected fair native-loader evidence and compute status.
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/invalidation/pr30-invalidated-results-manifest.json`
  - Invalidates old PR #30 numbers because the raw comparator measured preloaded `SourceSample` payload lookup and `camera_refs`.
  - Records old generated output cleanup and `source_dataset_mutation_status: not_mutated`.
- `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.md`
  - Four runnable rows: `zjh_lerobot_v21_raw`, `zjh_lerobot_v3_local`, `zjh_webdataset_tar`, `zjh_robodm_container_v1`.
  - Each row uses worker_count=8, batch_size=8, 2048 samples, materialized RGB/state/action payloads, and `Payload complete=True`.
  - States no final backend winner is selected by this table alone.
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`
  - PR-visible dashboard preserves invalidation language and no-winner boundary.
- `tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Covers four-candidate fair run, camera-ref-only rejection, core timing-field rejection, PR30 invalidation docs, and CLI help.

Generated evidence scan:

- `git status --short --ignored -uall -- runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001 ...` shows only ignored task evidence under `runs/tmp/...`.
- `git diff --name-only` is empty at this planning checkpoint.
- Tracked native/fair surfaces include:
  - `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - `autovla/dataloader/perf/native_loader_bakeoff.py`
  - `autovla/dataloader/perf/native_loader_timing_v2.py`
  - `tests/dataloader/test_fair_native_loader_bakeoff.py`
  - related native-loader and benchmark docs.

## Acceptance Token

The exact future Quality pass token is:

`PASS_ADAPTER_AUDIT_DRAFT_READY_FOR_USER_REVIEW`

Quality may issue that token only if:

1. The audit identifies the concrete adapter/native-loader bottleneck and records whether optimization changes are code, configuration, or evidence-only.
2. Any optimization keeps the fair-v0 contract: identical shared sample/window manifest, worker_count=8, batch_size=8, materialized three-camera RGB payloads, state/action/action_mask/language presence, no `camera_refs`-only row, and no preloaded `SourceSample` timing comparator.
3. The corrected benchmark still reports no final backend winner unless Product/Data/Architecture explicitly approve a stronger decision.
4. Local login-node-safe gates pass.
5. Compute/HPC rerun evidence exists for any performance claim that changes the fair-v0 timing table or recommendation.
6. Publication scans prove generated artifacts remain ignored/untracked and source datasets remain read-only.

## Validation Matrix

### Local Login-Node-Safe Tests

Required after implementation:

- Focused audit tests:
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_fair_native_loader_bakeoff.py -v`
  - Any new audit/optimization tests, expected under `tests/dataloader/`, must cover bottleneck classification and unchanged fair-contract invariants.
- Broader dataloader tests when touched surfaces are in `autovla/dataloader/perf/**` or `autovla/dataloader/stores/**`:
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -v`
- Governance/meta tests if docs, publication policy, or report policy changes:
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`
- CLI smoke without dataset-heavy execution:
  - `runs/tmp/m1-tool-venv/bin/python -m autovla.dataloader.perf.fair_native_loader_bakeoff --help`

### Static Gates

Required after implementation:

- `git diff --check`
- Ruff on changed Python paths:
  - `runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' <changed-python-paths>`
- Pyright on changed Python paths or full AutoVLA config if practical:
  - `runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json <changed-python-paths>`
- Black:
  - Prefer single-file changed-path checks with `--workers 1`.
  - If combined Black hangs, record the timeout and use single-file checks as the bounded fallback.
- JSON parse for all task-local result JSON and generated ledgers:
  - fair/native-loader result JSON
  - shared sample/window manifest
  - generated artifact ledger
  - invalidation or audit manifests

### Wrapper / Tool Environment Gate

Quality does not require a duplicate worktree-local `runs/tmp/m1-tool-venv` when the task prompt allows project-local tools generally.

Accepted local toolenv route:

- Direct commands may use root project-local tools at:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python`
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright`
- The active wrapper is:
  - `scripts/quality/autovla_check_project_local.sh`

Wrapper policy:

- If the wrapper fails only because this worktree lacks a local readiness stamp while direct root project-local validation passes, do not classify the audit as `BLOCKED_TOOL_ENV`.
- If the wrapper fails because required packages are missing, Pyright/Ruff/Black cannot run, or bootstrap requires unauthorized dependency recovery, classify as `BLOCKED_TOOL_ENV` until Tooling repairs or authorizes the exact route.
- No global, system, Conda, or network install is allowed for this Quality gate.

### Compute/HPC Evidence

Required for any new performance claim:

- Compute/HPC-owned rerun with the project wrapper or authorized task-local Slurm wrapper.
- Evidence under task-local ignored paths, expected pattern:
  - `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/compute/**`
  - `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/<audit-output>/**`
- Rerun rows must include, for every runnable candidate:
  - candidate name and native loader name
  - worker_count
  - batch_size
  - sample_count
  - p50/p95/p99/max or equivalent timing fields
  - samples/s and frames/s
  - loader-init time
  - conversion time
  - generated file count and artifact size
  - file-open/read-throughput counters if still part of contract
  - CPU/RSS fields
  - payload completeness proof
  - external-effect booleans
  - status and recommendation
- Rerun must keep all generated candidate stores under `datasets/working/**` and task evidence under `runs/tmp/**`.
- If optimization affects only one adapter, the comparison still needs enough unchanged candidates to prove the table is comparable or must be labelled non-comparable and not used for selection.

## Scan Plan

### Changed-File Scope

Allowed likely surfaces:

- `autovla/dataloader/perf/**`
- `autovla/dataloader/stores/**` only for bounded native-loader adapter optimization or instrumentation.
- `tests/dataloader/**`
- `docs/benchmarks/**`
- `README.md`
- task-local ignored evidence under `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**`
- task report under `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/**`

Any change to `pyproject.toml`, `requirements/**`, `Makefile`, `.github/**`, `scripts/quality/**`, `AGENTS.md`, `datasets/readonly/**`, `checkpoints/**`, `code-input/**`, model/runtime/training paths, or unrelated governance requires Owner re-scope and should block Quality acceptance until explicitly authorized.

### Generated Artifact / Dataset Scan

Required commands or equivalents:

- `git diff --name-only`
- `git ls-files runs/tmp datasets/working datasets/readonly checkpoints`
- `git status --short --ignored -uall -- runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001 datasets/working/autovla_fair_native_loader_bakeoff_v1`
- Artifact-extension scan over candidate publication paths for `.pt`, `.pth`, `.ckpt`, `.safetensors`, `.onnx`, `.bin`, `.parquet`, `.arrow`, `.npy`, `.npz`, `.tar`, `.tar.gz`, `.tgz`, `.zst`, `.mp4`, `.avi`, `.mov`, `.jpg`, `.jpeg`, `.png`, `.webp`.
- Large-file scan over candidate publication paths.

Pass criteria:

- `runs/tmp/**` and `datasets/working/**` may contain ignored evidence/generated stores, but must not be staged/tracked.
- `datasets/readonly/**` must remain unmodified.
- No checkpoint, model weight, media dump, dataset shard, or generated store artifact may be publication material.

### Secret / Endpoint / External-Effect Scan

Required:

- Secret/private-key scan over changed text diff and candidate publication files.
- Private endpoint scan over changed text diff.
- External-effect scan for W&B, Hugging Face upload/download, endpoint, robot, model load, checkpoint/tokenizer load, GPU, Slurm invocation, and real training.

Pass criteria:

- Runtime code may define fail-closed external-effect flags and docs may state "not authorized"; those are not blockers.
- Quality must not run Slurm, GPU, real training, model load, checkpoint/tokenizer load, W&B/HF network, endpoint, or robot commands.
- Any new execution path that performs those actions without explicit authorization blocks acceptance.

## Known Blockers / Risks

- Fair-v0 evidence is correction/decision-support evidence, not final backend selection.
- Old PR #30 multiformat numbers must remain invalidated and must not reappear as an active winner/baseline.
- Optimization work can accidentally make rows non-comparable if it changes sample windows, batch/worker settings, payload materialization, or candidate-store conversion policy.
- Worktree-local wrapper readiness stamp may be absent. This is not a blocker if root project-local direct gates pass, but should be recorded to avoid mistaking wrapper-local setup for source failure.
- Combined Black may hang. Single-file changed-path Black with `--workers 1` is the accepted bounded workaround unless Tooling requires wrapper-level repair.
- `docs/benchmarks/**` publication surfaces may require explicit pathspec handling at publication time if ignored by repository rules.

## Publication / Draft PR Gate

Before PR #30 can be left as `PASS_ADAPTER_AUDIT_DRAFT_READY_FOR_USER_REVIEW`, Quality requires:

- All relevant Owners have accepted the audit/optimization scope and evidence.
- PR #30 remains draft/open; no ready/merge action is performed by this gate.
- Local tests/static gates/scans pass.
- Compute/HPC rerun evidence exists for any changed performance claim.
- PR body or Manager summary clearly states:
  - prior PR #30 numbers invalidated
  - fair-v0 or optimized rerun evidence path
  - no final backend winner unless separately approved
  - generated artifacts ignored/untracked
  - no source dataset mutation
  - no dependency diff unless explicitly approved
  - no training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot authorization

## Compliance And Ledger

- DevSpace MCP / vla-flywheel-devspace / open_workspace / MCP read/write/edit/bash: not used.
- Source/test/docs/config edits by Quality: none.
- Git/PR mutation: none; no stage, commit, push, ready, merge, reset, restore, clean, stash, or PR mutation.
- Subagent ledger: none used.
- Retirement: Quality planning review complete; retired yes.
