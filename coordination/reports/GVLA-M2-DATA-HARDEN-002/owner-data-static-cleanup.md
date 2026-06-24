# GVLA-M2-DATA-HARDEN-002 Data Static-Hiding Cleanup

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- workspace_check: PASS
- `git status --short`: showed the existing Q-W1/A-W1/D-W1 dirty worktree plus Data hardening files and report directories. Data did not stage, commit, push, PR, merge, stash, reset, restore, clean, rm, create a worktree, or create a Python environment.

## Files changed

- `genesisvla/dataloader/transforms/__init__.py`
- `tests/dataloader/test_action_mode_transform.py`
- `tests/dataloader/test_image_transforms.py`
- `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data-static-cleanup.md`

## Exact static-hiding removal summary

- Removed `cast(Any, ...)` from production transform factory reconstruction in `genesisvla/dataloader/transforms/__init__.py`.
- Added local typed parser/narrowing helpers for:
  - image channel order: `HWC` / `CHW`
  - image input range: `0_255` / `0_1`
  - image augment mode: `none` / `horizontal_flip`
  - action mode: `absolute` / `delta` / `relative`
  - reference frame: `world` / `previous_action` / `state`
  - first-step policy: `absolute` / `zero`
- Replaced `tests/dataloader/test_action_mode_transform.py` `cast(Any, "camera")` with invalid runtime input through `TransformSpec` and `default_transform_registry().create(...)`.
- Replaced `tests/dataloader/test_image_transforms.py` `# type: ignore[arg-type]` with invalid runtime input through `TransformSpec` and `default_transform_registry().create(...)`.
- Public behavior is unchanged: invalid JSON/spec values still fail through explicit runtime validation, but no type checker suppression is used for these cases.

## Validation results

- RED static-hiding scan before cleanup:
  - Command: `rg -n "type: ignore|pyright: ignore|# pyright|cast\\(Any" genesisvla/dataloader genesisvla/testing/fixtures tests/dataloader docs/genesisvla/m2_transform_data_contract.md`
  - Result: matched the four Quality blockers in `tests/dataloader/test_action_mode_transform.py`, `tests/dataloader/test_image_transforms.py`, and `genesisvla/dataloader/transforms/__init__.py`.

- Final static-hiding scan:
  - Command: `rg -n "type: ignore|pyright: ignore|# pyright|cast\\(Any" genesisvla/dataloader genesisvla/testing/fixtures tests/dataloader docs/genesisvla/m2_transform_data_contract.md`
  - Result: no matches; command exited `1` as expected for clean `rg` search.

- Focused tests:
  - Command: `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_transform_registry.py tests/dataloader/test_image_transforms.py tests/dataloader/test_action_mode_transform.py -q`
  - Result: `29 passed in 0.16s`.

- Pyright:
  - Command: `PYTHONDONTWRITEBYTECODE=1 runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`
  - Result: `0 errors, 0 warnings, 0 informations`.

- Full wrapper:
  - Command: `make genesis-check`
  - First rework run: product tests and Pyright passed, but Black/Ruff reported formatting/import-order issues in the allowed files. Those were fixed within the same narrow scope.
  - Final result: PASS.
  - Final wrapper evidence included product py_compile PASS, product pytest `158 passed in 0.48s`, product Black PASS, product Ruff PASS, product Pyright `0 errors, 0 warnings, 0 informations`, governance py_compile PASS, governance pytest `21 passed in 0.05s`, governance Black PASS, and governance Ruff PASS.

- Diff whitespace:
  - Command: `git diff --check`
  - Result: PASS.

## DevSpace MCP compliance

PASS. No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, or DevSpace-derived evidence was used.

## Subagent ledger

- D-W1 narrow static cleanup: performed directly by persistent `30-OWNER · Data`.
- Short-lived subagents: none used.
- Retirement status: no child subagents remain active; this narrow cleanup is retired at report handoff.

## Parallelism note

Single writer only. No parallel write occurred.

## Conclusion

PASS

## Quality re-review readiness

Quality re-review may proceed. The exact static-hiding blockers are removed, required focused validation passed, the full `make genesis-check` wrapper passed, and no protected paths or unrelated files were modified for this narrow rework.
