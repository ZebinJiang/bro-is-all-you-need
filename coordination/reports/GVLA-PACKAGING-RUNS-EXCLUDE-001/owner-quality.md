# GVLA-PACKAGING-RUNS-EXCLUDE-001 · Owner Quality Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `fix/genesis-build-exclude-runs`
- HEAD: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- origin/main: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- `git status --short` before follow-up edits:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
 M pyproject.toml
 M tests/meta/test_repo_policy.py
?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml
```

- workspace_check: PASS. Current branch matches `fix/genesis-build-exclude-runs`; source writes remained limited to `pyproject.toml` and `tests/meta/test_repo_policy.py`.

## Files Changed

Quality-owned code/test changes:

- `pyproject.toml`
- `tests/meta/test_repo_policy.py`

Reports/evidence:

- `coordination/reports/GVLA-PACKAGING-RUNS-EXCLUDE-001/owner-quality.md`
- `coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/owner-quality-implementation.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/**`

Manager-owned recovery state present but not staged/committed:

- `coordination/PROGRAM_STATE.yaml`
- `coordination/TASK_INDEX.yaml`
- `coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml`
- `coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml`
- `coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml`

## Implementation Summary

- Added `runs` and `runs.*` to `[tool.setuptools.packages.find].exclude` in `pyproject.toml`.
- Kept `scripts/quality/genesis_build_verify_project_local.sh` unchanged.
- Kept strict `wheel_content_scan` semantics unchanged.
- Preserved `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/**` byte-for-byte.

## Required Regression Checks

All three required regression checks now exist in `tests/meta/test_repo_policy.py`:

- pyproject explicit runs exclusion: `test_should_exclude_project_local_runs_from_package_discovery`
- namespace package discovery behavior: `test_should_exclude_runs_namespace_packages_while_discovering_genesisvla`
- scanner strictness contract: `test_should_keep_wheel_scanner_rejecting_runs_entries`

Coverage details:

- The explicit pyproject test asserts configured package discovery excludes contain both `runs` and `runs.*`.
- The discovery behavior test builds a temporary tree containing `genesisvla/example/__init__.py` and `runs/tmp/task/root-preservation/untracked-files/tests/meta/__init__.py`, verifies the synthetic `runs.*` namespace would be discoverable without excludes, then verifies configured excludes preserve `genesisvla`/`genesisvla.example` while excluding all `runs`/`runs.*` packages.
- The scanner contract test reads the existing build wrapper policy and verifies a synthetic wheel entry beginning with `runs/` is rejected by the same top-level forbidden path rule.

## Validation Results

- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`: PASS
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`: PASS, `25 passed`
- `make governance-check`: PASS
  - initial run found Black formatting needed for `tests/meta/test_repo_policy.py`; the allowed test file was formatted with project-local Black and the full command was rerun successfully.
- `make genesis-build-check`: PASS
  - wheel build/install/pip check/import: PASS
  - wheel content scan: PASS, `entries=229`
- `make genesis-check`: PASS
  - product pytest: PASS, `202 passed`
  - product Black/Ruff/Pyright: PASS, Pyright `0 errors, 0 warnings, 0 informations`
  - governance pytest: PASS, `25 passed`
  - governance Black/Ruff: PASS
- `git diff --check`: PASS
- preservation hash comparison against prior known hashes: PASS
  - `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hash-comparison-after-followup.txt`
- `git status --short` after validation:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
 M pyproject.toml
 M tests/meta/test_repo_policy.py
?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml
```

- `git diff --name-only` after validation:

```text
coordination/PROGRAM_STATE.yaml
coordination/TASK_INDEX.yaml
pyproject.toml
tests/meta/test_repo_policy.py
```

- `git diff --cached --name-only`: empty

Final `git status --short` after report writes:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
 M pyproject.toml
 M tests/meta/test_repo_policy.py
?? coordination/reports/GVLA-PACKAGING-RUNS-EXCLUDE-001/
?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml
```

Final `git diff --cached --name-only`: empty.

## Preservation Safety

The root-preservation evidence was not modified or deleted. Hash comparison PASS covered:

- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/tracked-root.patch`
- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/tracked-files-manifest.json`
- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/untracked-files-manifest.json`
- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/preservation-verification.json`
- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/untracked-files/tests/meta/__init__.py`

## Compliance

- DevSpace MCP / `vla-flywheel-devspace` / MCP connector / `open_workspace` / MCP read/write/edit/bash used: no.
- Stage/unstage/commit/push/PR/merge performed: no.
- Reset/restore/clean/rm/stash performed: no.
- `scripts/quality/genesis_build_verify_project_local.sh` changed: no.
- feature_list passes, M1/M2 completion state, M3 implementation changed: no.

## Subagent Retirement Ledger

- Q-W1 continuation writer: completed focused regression tests, validation, preservation hash comparison, and report; retired: yes.
- Additional subagents: none used.
- Parallelism: no parallel write.

## Conclusion

`PASS`

The packaging hotfix now has all three required regression checks and all required local validation commands pass.
