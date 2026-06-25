# GVLA-PACKAGING-RUNS-EXCLUDE-001 Wave 3 Architecture Pre-Publication Review

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
  - `?? coordination/reports/GVLA-PACKAGING-RUNS-EXCLUDE-001/`
  - `?? coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/`
  - `?? coordination/tasks/active/GVLA-PACKAGING-RUNS-EXCLUDE-001.yaml`
  - `?? coordination/tasks/active/GVLA-PACKAGING-RUNS-PUBLISH-001.yaml`
  - `?? coordination/tasks/active/GVLA-WORKTREE-CONSOLIDATE-RESUME-001.yaml`
- `git diff --cached --name-only`: empty
- workspace_check: PASS

## Files And Diffs Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/architecture/packaging-boundary-review.md`
- `runs/tmp/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/quality/failing-before-analysis.md`
- `coordination/reports/GVLA-PACKAGING-RUNS-EXCLUDE-001/owner-quality.md`
- `coordination/reports/GVLA-ROOT-BUILD-SCAN-RECOVERY-001/owner-quality-implementation.md`
- `pyproject.toml`
- `tests/meta/test_repo_policy.py`
- `scripts/quality/genesis_build_verify_project_local.sh`
- current `git diff -- pyproject.toml tests/meta/test_repo_policy.py scripts/quality/genesis_build_verify_project_local.sh`
- current `git diff --name-only f4ab90dfa790a99fbfc47b1c4dfd601661f9af91`
- current `git diff -- runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation`

## Architecture Findings

1. The implementation is the approved narrow packaging-boundary fix.
   `pyproject.toml` adds only `runs` and `runs.*` to `[tool.setuptools.packages.find].exclude`.

2. `scripts/quality/genesis_build_verify_project_local.sh` is unchanged.
   The strict `wheel_content_scan` still rejects top-level `runs`, `datasets`, and `cache`, plus protected artifact suffixes. No allowlist or scanner weakening was introduced.

3. Regression coverage is appropriate.
   `tests/meta/test_repo_policy.py` now covers:
   - explicit `pyproject.toml` package-discovery excludes for `runs` and `runs.*`;
   - namespace-package discovery behavior, proving `runs.*` would be discoverable without excludes and is excluded while `genesisvla` packages remain discoverable;
   - scanner strictness, proving the existing top-level `runs/` rejection contract remains active.

4. No legitimate package is excluded.
   The change targets only the governed project-local run/evidence root. The test fixture confirms GenesisVLA package discovery still includes `genesisvla` and `genesisvla.example` while excluding `runs` and `runs.*`.

5. Package include allowlist migration remains deferred with acceptable rationale.
   A full allowlist migration would be a broader package-discovery refactor and is not needed for this recovery. The current exclude-list approach matches the existing `pyproject.toml` pattern, fixes the root build blocker, and avoids changing public package discovery beyond the `runs/**` evidence boundary.

6. No public runtime API, M1/M2 behavior, or M3 implementation changed.
   Current diff paths are limited to Manager state plus `pyproject.toml` and `tests/meta/test_repo_policy.py`; no `genesisvla/**`, runtime scripts, feature-list pass fields, or M3 implementation paths are modified.

7. Root-preservation evidence was not modified.
   `git diff -- runs/tmp/GVLA-PR2-MERGE-MAIN-SYNC-001/root-preservation` is empty, and Quality recorded preservation hash comparison PASS after the follow-up.

## Validation Evidence Relied On From Quality

Quality recorded:

- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`: PASS
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`: PASS, `25 passed`
- `make governance-check`: PASS
- `make genesis-build-check`: PASS, including `wheel_content_scan`
- `make genesis-check`: PASS, including product pytest `202 passed`, Black/Ruff/Pyright PASS, governance pytest `25 passed`
- `git diff --check`: PASS
- preservation hash comparison after follow-up: PASS

Architecture also observed the current index is empty and the current scanner/build-wrapper diff is empty.

## Publication Readiness

Current dirty scope is acceptable for the next publication wave:

- expected Manager coordination/task/report state is present;
- hotfix code/config scope is limited to `pyproject.toml` and `tests/meta/test_repo_policy.py`;
- no staged files exist;
- no source/runtime/tooling script/feature-list/M1/M2 completion-state/M3 implementation mutation was found;
- root-preservation evidence remains intact.

## Decision

Conclusion: APPROVE

Architecture approves this hotfix for publication. It preserves the strict wheel gate, fixes only the package discovery boundary for project-local `runs/**` evidence, and includes sufficient regression coverage.

## DevSpace MCP Compliance

PASS. This review used local repository files and local read-only git/shell inspection only. DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash were not used as workflow or evidence.

## No-Mutation Evidence

- No stage, unstage, commit, push, PR creation, merge, reset, restore, clean, rm, or stash was performed by Architecture.
- No source, tests, tooling, task-state, feature-list, M1/M2 completion state, root-preservation evidence, or M3 implementation was modified by Architecture.
- Only this allowed Architecture review report was written.

## Subagent Retirement Ledger

- Short-lived subagents used: none.
- Architecture pre-publication review was performed directly in this Owner thread.
- Retirement status: none used; ledger complete.
- Parallelism: read-only review only; no parallel write.
