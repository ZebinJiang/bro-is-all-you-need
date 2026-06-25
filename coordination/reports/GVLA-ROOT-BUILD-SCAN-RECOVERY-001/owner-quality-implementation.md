# GVLA-ROOT-BUILD-SCAN-RECOVERY-001 / Wave 2 Q-W1 Quality Implementation

## Workspace Verification Before Branch Creation

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `main`
- HEAD: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- origin/main: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- `git status --short` before branch switch:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml
```

- pre-branch dirty-scope check: PASS. Status contained only Manager-approved recovery coordination/task/report diffs.
- existing branch check: `git show-ref --verify --quiet refs/heads/fix/genesis-build-exclude-runs` returned `1`, so the local hotfix branch did not exist.

## Branch Creation Evidence

Command:

```text
git switch -c fix/genesis-build-exclude-runs origin/main
```

Result:

- branch created: yes
- current branch after switch: `fix/genesis-build-exclude-runs`
- HEAD after switch: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- upstream: `origin/main`
- Manager coordination diffs preserved: yes

Post-branch `git status --short` before implementation:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml
?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml
```

## Files Changed

Quality Q-W1 changed only:

- `pyproject.toml`
- `tests/meta/test_repo_policy.py`
- `coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/owner-quality-implementation.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/**` evidence from Wave 1/2

Manager-owned preexisting dirty coordination/task files remained present and were not edited by this Q-W1 implementation beyond this allowed Owner report path.

## Fix Summary

Implemented the Architecture-approved packaging-boundary hotfix:

- Added `runs` and `runs.*` to `[tool.setuptools.packages.find].exclude` in `pyproject.toml`, near other project-local artifact roots.
- Added focused meta-policy coverage in `tests/meta/test_repo_policy.py`:
  `test_should_exclude_project_local_runs_from_package_discovery`.
- Kept `scripts/quality/genesis_build_verify_project_local.sh` and strict `wheel_content_scan` unchanged.
- Did not modify or delete `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/**`.

TDD evidence:

- Red: `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py::test_should_exclude_project_local_runs_from_package_discovery -q`
  failed before the `pyproject.toml` fix because `"runs"` was absent from package discovery excludes.
- Green: after adding `runs` and `runs.*`, full `tests/meta/test_repo_policy.py -v` passed.

## Validation Results

- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`: PASS
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`: PASS, `25 passed`
- `make genesis-build-check`: PASS
  - wheel build: PASS
  - clean wheel install: PASS
  - `pip check`: PASS
  - `import genesisvla`: PASS
  - `wheel_content_scan`: PASS, `entries=229`
- `make genesis-check`: PASS
  - product pytest: PASS, `202 passed`
  - product Black/Ruff/Pyright: PASS, Pyright `0 errors, 0 warnings, 0 informations`
  - governance pytest: PASS, `25 passed`
  - governance Black/Ruff: PASS
- `git diff --check`: PASS
- preservation hashes after hotfix compared to Wave 1/preflight hashes: PASS
  - comparison file: `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hash-comparison-after-hotfix.txt`
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

## Preservation Hashes

Hotfix after-hash file:

- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hashes-after-hotfix.txt`

Key hashes remained unchanged:

```text
61164db2843a8473bc76ed5f7995374a86239214bd4ae10cdfbee0109503dab4  runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/tracked-root.patch
faa3ebc2b9ae3457adda0bb037d519a53a2d3dd3b3ba0cc1c1cb50d45521b908  runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/tracked-files-manifest.json
d6d73885bfb446b1ec54c52bf6db0480045ae6d6ed000dbf275fc4cfb96fc50a  runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/untracked-files-manifest.json
326d80cd85d70c8ac03815ce9c5fdaf22d42ee1156bb1736ac7ae065f1dba1d6  runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/preservation-verification.json
7e794ed6bf875cb575efab3386d8e8d5f6a774393e9587d2b194b633b4d5b16b  runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/untracked-files/tests/meta/__init__.py
```

Result: PASS. Preservation evidence remained byte-for-byte unchanged for the checked files.

## Follow-up Regression Coverage

Manager follow-up requested two additional focused regression tests beyond the original pyproject-string assertion. Q-W1 continuation added and validated all three required checks:

- pyproject explicit runs exclusion: `test_should_exclude_project_local_runs_from_package_discovery`
- namespace package discovery behavior: `test_should_exclude_runs_namespace_packages_while_discovering_genesisvla`
- scanner strictness contract: `test_should_keep_wheel_scanner_rejecting_runs_entries`

The discovery behavior test creates a temporary package tree with `genesisvla/example/__init__.py` and `runs/tmp/task/root-preservation/untracked-files/tests/meta/__init__.py`, verifies `runs.*` would be discoverable without excludes, then verifies configured excludes still discover GenesisVLA packages while excluding `runs` and every `runs.*` package.

The scanner contract test keeps `scripts/quality/genesis_build_verify_project_local.sh` unchanged and verifies the existing top-level forbidden path policy rejects a synthetic wheel entry beginning with `runs/`.

Latest continuation validation:

- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`: PASS
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`: PASS, `25 passed`
- `make governance-check`: PASS
- `make genesis-build-check`: PASS
- `make genesis-check`: PASS
- `git diff --check`: PASS
- preservation hash comparison after follow-up: PASS, `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hash-comparison-after-followup.txt`

## Compliance And Scope

- DevSpace MCP / `vla-flywheel-devspace` / MCP connector / `open_workspace` / MCP read/write/edit/bash used: no.
- `scripts/quality/genesis_build_verify_project_local.sh` modified: no.
- `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/**` modified/deleted: no.
- feature_list passes modified: no.
- M1/M2 completion state modified: no.
- M3 implementation started: no.
- stage/unstage/commit/push/PR/merge performed: no.
- reset/restore/clean/rm/stash performed: no.

## Subagent Retirement Ledger

- Q-W1 Quality writer: completed implementation, validation, preservation hash comparison, and report; retired: yes.
- Short-lived subagents: none used.
- Parallelism: no parallel write.

## Conclusion

`PASS_HOTFIX_VALIDATED`

The package discovery defect is fixed locally on `fix/genesis-build-exclude-runs`. The strict wheel scanner remains unchanged and now passes with root-preservation evidence still present and byte-for-byte preserved.
