# GVLA-ROOT-BUILD-SCAN-RECOVERY-001 Architecture Hotfix Review

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `fix/genesis-build-exclude-runs`
- HEAD: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- expected_base_HEAD: `f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- `git status --short`:
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M pyproject.toml`
  - `M tests/meta/test_repo_policy.py`
  - `?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/`
  - `?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml`
  - `?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml`
  - `?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml`
- workspace_check: PASS
- index_check: `git diff --cached --name-only` was empty.

## Files And Diffs Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/architecture/packaging-boundary-review.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/failing-before-analysis.md`
- `coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/owner-quality-implementation.md`
- `pyproject.toml`
- `tests/meta/test_repo_policy.py`
- `scripts/quality/genesis_build_verify_project_local.sh`
- `git diff -- pyproject.toml tests/meta/test_repo_policy.py scripts/quality/genesis_build_verify_project_local.sh`
- `git diff --name-only f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- `git diff --stat f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- preservation hash comparison evidence under `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/`

## Hotfix Scope Assessment

The implementation matches the Architecture-approved narrow packaging-boundary fix:

- `pyproject.toml` adds only:
  - `runs`
  - `runs.*`
- The entries are added under `[tool.setuptools.packages.find].exclude`, near other project-local artifact roots.
- No package name, package-data entry, build backend, dependency, runtime source, or public API surface was changed.
- `tests/meta/test_repo_policy.py` adds a focused policy test that asserts both `runs` and `runs.*` remain present in package discovery excludes.

## Wheel Scanner And Build Wrapper Assessment

`scripts/quality/genesis_build_verify_project_local.sh` has no diff. The strict `wheel_content_scan` remains unchanged:

- top-level `runs` remains forbidden in wheel contents;
- no allowlist was added for root-preservation evidence;
- forbidden artifact suffix and path-component checks remain in place.

This preserves public gate semantics. The fix moves artifact evidence out of package discovery instead of weakening the scanner.

## Meta Policy Assessment

The added meta policy coverage is appropriate and narrow. It locks the repository packaging boundary and does not reduce gate strictness. Existing meta tests still assert that the build wrapper uses project-local paths and keeps strict wheel-content scanning.

## Root-Preservation Evidence Assessment

Quality evidence reports preservation hashes unchanged after the hotfix. Reviewed evidence:

- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hash-comparison-after-hotfix.txt`: `PASS`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/preservation-hashes-after-hotfix.txt`

The checked root-preservation hashes match the prior preflight values, including:

- `tracked-root.patch`
- `tracked-files-manifest.json`
- `untracked-files-manifest.json`
- `preservation-verification.json`
- preserved `untracked-files/tests/meta/__init__.py`

Architecture found no evidence that `runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation/**` was moved, deleted, or rewritten.

## Validation Evidence Relied On From Quality

Quality recorded:

- red focused meta test before the `pyproject.toml` fix: expected failure because `runs` was absent from package discovery excludes;
- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`: PASS;
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`: PASS, `23 passed`;
- `make genesis-build-check`: PASS, including wheel build, clean install, `pip check`, `import genesisvla`, and `wheel_content_scan`;
- `make genesis-check`: PASS, including product pytest `202 passed`, Black/Ruff/Pyright PASS, and governance pytest `23 passed`;
- `git diff --check`: PASS;
- preservation hash comparison after hotfix: PASS.

Architecture also observed `git diff --check` clean during this review.

## Scope And Publication Readiness

Current dirty scope is acceptable for the next publication wave:

- product/runtime changed files: none;
- public packaging policy changed files: `pyproject.toml`, `tests/meta/test_repo_policy.py`;
- Manager coordination state/report/task-card dirty state is expected for this recovery task;
- no staged files;
- no feature-list pass, M1/M2 completion-state, M3 implementation, source, runtime, dataset, checkpoint, or root-preservation evidence mutation was observed.

## Decision

Decision: APPROVE_HOTFIX

Architecture approves the hotfix for publication review. It is the requested narrow packaging-boundary correction, preserves strict wheel scanning, keeps root-preservation evidence byte-for-byte, and does not introduce public package/runtime scope creep.

## DevSpace MCP Compliance

PASS. This review used local repository files and local read-only git/shell inspection only. DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash were not used as workflow or evidence.

## Subagent Retirement Ledger

- Short-lived subagents used: none.
- Architecture hotfix review was performed directly in this Owner thread.
- Retirement status: none used; ledger complete.
- Parallelism: read-only review only; no parallel write.

## No-Mutation Evidence

- No stage, unstage, commit, push, PR creation, merge, reset, restore, clean, rm, or stash was performed by Architecture.
- No source, tests, tooling, task-state, feature-list, M1/M2 completion state, or M3 implementation was modified by Architecture.
- Only this allowed Architecture review report was written.
