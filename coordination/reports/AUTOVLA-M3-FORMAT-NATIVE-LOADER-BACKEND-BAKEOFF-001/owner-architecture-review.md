# Architecture Review

Task: AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001

Decision: REQUEST_CHANGES

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-data-backend-bakeoff-dashboard`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-data-backend-bakeoff-dashboard`
- branch: `dev/feat-autovla-m3-data-backend-bakeoff-dashboard`
- HEAD: `56c55bfeb2ef33f736713a454484bbee5031908d`
- status:
  - `M autovla/dataloader/perf/bakeoff.py`
  - `M docs/benchmarks/README.md`
  - `?? coordination/reports/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/`
  - `?? tests/dataloader/test_format_native_loader_bakeoff.py`
- workspace_check: PASS

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/reports/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/owner-data.md`
- `autovla/dataloader/perf/bakeoff.py`
- `tests/dataloader/test_format_native_loader_bakeoff.py`
- `docs/benchmarks/README.md`
- `docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/format-native-loader-bakeoff-report.md`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/format-native-loader-rows.json`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/benchmark-payload-contract.json`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/format-native-conversion-manifest.json`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/generated-artifact-ledger.json`

Read-only checks:

- `git check-ignore -v docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md`
- `git ls-files docs/benchmarks/README.md docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md`
- `git diff --check`
- `git status --short --branch`

## Findings

1. P1 publication blocker: tracked dashboard README links to ignored/untracked generated doc.
   - File/line: `docs/benchmarks/README.md:4`
   - The tracked README now links to `FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md`.
   - `git check-ignore -v` shows `docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md` is ignored by `.gitignore:235` through `*/**/*.md`.
   - `git ls-files` shows `docs/benchmarks/README.md` is tracked and `docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md` is not tracked.
   - Architecture classification: the ignored format-native doc is acceptable as task-local/generated evidence only if it is not referenced by a tracked publication surface. The current tracked README link would publish a broken dashboard link unless the doc is intentionally force-added under publication policy or the README link is removed/kept task-local.

2. Format-native loader contract is otherwise architecturally sound.
   - `BenchmarkPayload` records action, language, three RGB camera streams, state, action-mask policy, deterministic subset/window ids, and `worker_count=8`.
   - The five required candidate ids are present: `zjh_lerobot_v21_raw`, `lerobot_v3_converted`, `webdataset_converted`, `robodm_style_converted`, and `zarr_converted`.
   - No row is marked `PASS`; all rows remain compute-pending or dependency-blocked and `winner_eligible=false`.

3. Output safety is correctly fail-closed.
   - Symlink-only output is rejected.
   - `datasets/readonly` and source-dataset output roots are rejected.
   - Generated artifact root is `datasets/working/autovla_format_native_loader_bakeoff`.
   - The generated artifact ledger marks generated docs/reports/manifests as untracked/not staged and records `source_dataset_mutated=false`.

4. Existing PR18 historical dashboard contract remains intact.
   - The new format-native surface is additive in `autovla/dataloader/perf/bakeoff.py`.
   - Historical proxy/backend-reader rows are explicitly context-only with `historical_proxy_winner_eligible=false`.
   - Final decision remains `READY_FOR_USER_DECISION_BACKEND`, which is correct without native-loader compute evidence.

5. No runtime/model/training scope creep found.
   - No fine-tune/training/model/checkpoint/tokenizer/HF/W&B/Slurm/endpoint/robot scope is introduced.
   - No dependency changes are present in this update.
   - No PR #16 mutation was observed or required.

## Residual Risks

- The format-native loader report is currently generated under both `runs/tmp/**` and `docs/benchmarks/**`; publication intent must be made explicit. If the docs version is intended for PR visibility, it needs governed tracking/scanning. If it is task-local evidence only, tracked docs must not link to it.
- Compute/native-loader evidence remains absent. This is acceptable only because the dashboard remains `READY_FOR_USER_DECISION_BACKEND` and no winner is selected.

## Recommended Fix

Choose one publication policy:

1. Track/force-add `docs/benchmarks/FORMAT_NATIVE_LOADER_BACKEND_BAKEOFF.md` with the same publication scans used for docs artifacts; or
2. Remove the tracked link from `docs/benchmarks/README.md` and keep the format-native report as task-local generated evidence under `runs/tmp/**`.

Do not claim a final backend winner or `PASS` native-loader benchmark until W8 native-loader compute evidence exists.

## DevSpace MCP Compliance

DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, and MCP read/write/edit/bash were not used.

## No Mutation Statement

Architecture performed local read-only shell/git/file inspection and wrote only this assigned report. No source/tests/docs/dependencies were patched by Architecture; no stage/commit/push/PR mutation/merge/reset/restore/clean/stash was performed.

## Subagent Ledger

- Architecture A-R1: owner-direct read-only review; no child subagents launched; retired: yes.
