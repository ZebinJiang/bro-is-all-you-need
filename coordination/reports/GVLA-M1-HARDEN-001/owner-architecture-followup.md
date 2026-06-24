# GVLA-M1-HARDEN-001 Architecture Follow-up

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `dev/starvla-engineering-base`
- head: `645850d92b9d2217c060ffe2205b266d04dae541`
- workspace_check: `PASS`

Initial `git status --short` confirmed existing historical dirty/untracked
files. They were preserved; no reset, restore, clean, staging, stash, commit,
push, merge, force-push, PR, M1 completion, feature-list pass update, M2 work,
or code-input upstream edit was performed.

## Conclusion

`PASS`

The narrow Quality `BLOCKED_TEST` follow-up blockers were fixed in the allowed
scope. Project-local wrapper, focused pytest, and whitespace diff checks now
pass.

## Changed Files

- `Makefile`
- `scripts/quality/genesis_check_project_local.sh`
- `scripts/maintenance/delete_from_cleanup_manifest.py`
- `scripts/slurm/discover_slurm_environment.py`
- `genesisvla/config/loader/validate.py`
- `genesisvla/core/types/action.py`
- `tests/config/test_loader.py`
- `tests/core/test_action.py`
- `tests/maintenance/test_delete_cleanup_manifest.py`
- `tests/slurm/test_discover_slurm_environment.py`
- `tests/meta/test_repo_policy.py`
- `coordination/reports/GVLA-M1-HARDEN-001/owner-architecture-followup.md`

## Fixes Made

- Updated `tests/meta/test_repo_policy.py` stale expected Makefile/wrapper
  fragments so the new `tests/maintenance tests/slurm` gate scope is accepted.
- Fixed Ruff `RUF043` in `tests/core/test_action.py` by using a raw regex for
  the mask bool assertion.
- Fixed Pyright strictness in `genesisvla/core/types/action.py` without blanket
  ignores by casting action names to `tuple[object, ...]` before runtime checks.
- Replaced private cleanup helper import with public
  `checked_delete_path(...)` and updated cleanup tests.
- Added cleanup coverage for absolute outside paths, `../` escape, missing
  confirmation token/no-delete behavior, and allowed in-repo deletion after
  safety checks.
- Added Slurm coverage for empty cluster write blocking, absolute and nested
  run-id rejection, config `../` escape, output absolute escape, and direct
  assertion that `os.replace` receives a temp path in the target directory.
- Tightened Slurm helper typing with explicit `Mapping`/`Sequence` annotations
  so strict Pyright accepts tests and helpers.
- Added direct config tests for unknown top-level/model/data/runner keys and a
  named CLI typo override test.

## Validation Results

- `bash scripts/quality/genesis_check_project_local.sh`: `PASS`
  - `py_compile`: `PASS`
  - `pytest`: `83 passed`
  - Black file-list check: `PASS`
  - Ruff: `PASS`
  - Pyright: `0 errors, 0 warnings`
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/config tests/core tests/meta tests/maintenance tests/slurm -v`: `PASS`, `83 passed`
- `git diff --check`: `PASS`, no output
- `git status --short`: completed; historical dirty/untracked files remain,
  plus this task's allowed-scope hardening changes and report.

## Remaining Risks

- The workspace still contains unrelated historical dirty/untracked files
  outside this follow-up approval boundary.
- No staging, commit, push, or PR update was performed by this Architecture
  follow-up.
- Quality should independently re-run or review before publication if Manager
  requires a separate owner gate.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, global dependency install, `/tmp` tool environment, or
M2 branch/worktree workflow was used.

## Subagent Retirement Ledger

None used. This follow-up was performed directly and serially by Architecture
Owner, per Manager instruction.

## Parallelism

No parallel writes. Local validation commands were run after the serial fixes.
