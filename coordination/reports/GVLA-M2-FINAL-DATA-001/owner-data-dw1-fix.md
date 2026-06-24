# GVLA-M2-FINAL-DATA-001 D-W1-FIX Owner Data Report

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace_check: PASS
- git status: existing D-W1 / Q-W1 dirty worktree state remained present. This fix did not stage, commit, push, PR, merge, rebase, reset, restore, clean, rm, stash, or mutate git index.

## Files changed

D-W1-FIX touched only the allowed follow-up scope:

- `genesisvla/dataloader/contracts.py`
- `tests/dataloader/test_collate.py`
- `coordination/reports/GVLA-M2-FINAL-DATA-001/owner-data-dw1-fix.md`

## Exact blocker fixed

Architecture blocker:

- `CollatedBatch._owned_action_mask()` converted explicit `action_mask` with `np.asarray(self.action_mask, dtype=np.bool_)` before strict validation, allowing direct public `CollatedBatch(...)` construction to accept numeric/string/object masks through coercion.

Fix:

- Replaced the coercing conversion with `strict_bool_array(self.action_mask, name="action_mask")` before shape validation.
- Added direct `CollatedBatch` constructor regression tests for int, float, string, object, and mixed bool/int masks.
- Preserved bool-only sequence acceptance and direct constructor `[B,H,D]` shape validation.

TDD red evidence:

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_collate.py -q`
- Result before production fix: expected failure, `5 failed, 16 passed`, all failures from `test_direct_collated_batch_should_reject_non_bool_action_mask_values[...]`.

## Validation results

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_collate.py -q`
  - PASS, `21 passed`.
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q`
  - PASS, `110 passed`.
- `PYTHONDONTWRITEBYTECODE=1 runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`
  - PASS, `0 errors, 0 warnings, 0 informations`.
- `make genesis-check`
  - PASS.
  - Product pytest: `202 passed`.
  - Product Black: PASS.
  - Product Ruff: PASS.
  - Product Pyright: `0 errors, 0 warnings, 0 informations`.
  - Governance pytest: `22 passed`.
  - Governance Black/Ruff: PASS.
- `git diff --check`
  - PASS, no output.

## Artifact/staging safety statement

- No files were staged or committed.
- No PR body, M1 branch, feature_list pass fields, M2 completion state, M3/M4 code, datasets, code-input, checkpoints, model weights, generated fixture binaries, or git index state were modified.
- This fix did not create generated parquet/media/dataset/checkpoint artifacts.

## DevSpace MCP compliance

- PASS. No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, or DevSpace-derived evidence was used.

## Subagent retirement ledger

- D-W1-FIX implementation writer: current Owner thread only; retired after this report.
- Short-lived subagents: none used.

## Current conclusion

PASS.
