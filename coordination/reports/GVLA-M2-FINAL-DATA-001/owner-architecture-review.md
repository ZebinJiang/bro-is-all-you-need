# GVLA-M2-FINAL-DATA-001 Owner Architecture Review

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace_check: PASS
- git status reviewed: existing Q-W1/D-W1 dirty coordination, docs, dataloader, fixture, quality, and test paths were present. Architecture did not stage, commit, push, PR, merge, rebase, reset, restore, clean, rm, stash, or edit any file except this report.
- `git diff --cached --name-only`: empty.
- `git diff --check`: PASS.

## Decision

REQUEST_CHANGES.

## Files and evidence reviewed

- `coordination/reports/GVLA-M2-FINAL-DATA-001/owner-data-dw1.md`
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/owner-quality-qw1.md`
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/owner-architecture-review.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave1-manager-synthesis.md`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- D-W1 diffs under `docs/genesisvla/**`, `docs/references/upstream_sources.yaml`, `genesisvla/dataloader/**`, `genesisvla/testing/fixtures/**`, and `tests/dataloader/**`.
- Read-only checks:
  - `git diff --name-status`
  - `git diff --stat`
  - `git diff --check`
  - `git diff --cached --name-only`
  - protected-path diff check for datasets, code-input, checkpoints, model/training/deployment/acceleration, and feature-list paths
  - focused `rg` scans for PyArrow, LeRobot/package/download references, real-format provenance, and generated binary tracking.

## Findings ordered by severity

### P1 - `CollatedBatch` direct constructor still coerces non-bool `action_mask`

- File: `genesisvla/dataloader/contracts.py`
- Evidence: `strict_bool_array()` rejects non-bool dtype at lines 175-180, but `CollatedBatch._owned_action_mask()` converts explicit masks with `np.asarray(self.action_mask, dtype=np.bool_)` before strict validation at line 393. That means direct public construction of `CollatedBatch(action_mask=np.asarray(..., dtype=int))` can silently coerce numeric/string-like truthy values to bool before `_readonly_bool_array()` sees them.
- Impact: D-W1 closes strict bool behavior for collate metadata, state/action normalization, statistics `valid_mask`, and parquet fixture schema tests, but the public typed batch contract still has a bypass. This conflicts with the Wave 1 acceptance contract that action masks/statistics masks must reject numeric/string/object coercion.
- Required change: replace the coercing conversion in `_owned_action_mask()` with the existing strict bool helper before shape validation, and add a focused direct `CollatedBatch` constructor regression test for numeric/string/object masks. Do not widen public contracts or add ignores.

## Contract / public API assessment

- Generated real-format fixture evidence was not downgraded to in-memory-only evidence. `tiny_lerobot_fixture(root)` writes metadata plus parquet data/episode shards and reloads them; `tiny_parquet_fixture(path)` writes and reloads an actual parquet file. Tests assert `real_format=true`, LeRobot v3 target provenance, metadata/data relationships, fixed-size-list column types, and corrupt/malformed failure paths.
- PyArrow remains outside dataloader public API and product runtime dependency declarations. References are limited to `requirements/quality/**`, `scripts/quality/bootstrap_project_local_tools.sh`, `tests/meta/test_repo_policy.py`, `docs/references/upstream_sources.yaml`, and generated fixture helpers/tests under `genesisvla/testing/fixtures/**` / `tests/dataloader/**`.
- No full `lerobot` package dependency, download path, copied source, or generated binary tracking was found.
- Collation ordering, image statistics, relative action mode one-dimensional state policy, and FeatureStatistics/DatasetStatistics invariants are architecturally coherent, except for the direct `CollatedBatch` bool-mask bypass above.
- No M1 public contract break, M3/model/training scope creep, or protected-path diff was observed.

## Fixture / dependency / provenance assessment

- LeRobot format target is recorded as `v0.5.1`, upstream revision `1396b9fab7aecddd10006c33c47a487ffdcb54b4`, dataset format target `v3.0`, format-target only, no copied/adapted source.
- PyArrow is pinned as `pyarrow==18.1.0`, Apache-2.0, test/quality-only, dependency-only/no copied source.
- `git ls-files` found no tracked `.parquet`, `.mp4`, `.arrow`, `.npy`, `.npz`, model-weight, checkpoint, or binary fixture artifacts. Untracked files were coordination/task/report artifacts only.
- Generated fixture files are produced under pytest `tmp_path` or explicit governed output paths and are not intended as source-tracked assets.

## DevSpace MCP compliance

PASS. This review used local shell/git/project-file inspection only. DevSpace MCP, `vla-flywheel-devspace`, MCP connectors, `open_workspace`, MCP read/write/edit, and MCP bash were not used.

## Subagent ledger

- No subagents were used.
- No subagent retirement was required.

## Parallelism note

Read-only review only, with one allowed Architecture report write. No parallel write.
