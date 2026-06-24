# GVLA-M2-REMOTE-CI-003 Owner Architecture Review

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- published_head_before_hardening: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- workspace_check: `PASS`
- status_short_before_report:
  - `M .github/workflows/genesisvla.yml`
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml`
  - `M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
  - `M scripts/quality/bootstrap_project_local_tools.sh`
  - `M tests/meta/test_repo_policy.py`
  - `?? coordination/reports/GVLA-M2-HARDEN-001/`
  - `?? coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/manager-summary.md`
  - `?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`
  - `?? coordination/reports/GVLA-M2-MILESTONE-AUDIT-001/`
  - `?? coordination/reports/GVLA-M2-REMOTE-CI-003/`
  - `?? coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml`
  - `?? coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
  - `?? coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
  - `?? coordination/tasks/active/GVLA-M2-PR2-VERIFY-003.yaml`
  - `?? coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml`

Architecture did not modify source, tests, workflow, bootstrap, tooling, task state, PR state, git index, branch, or remote. This review report is the only Architecture write.

## Decision

`APPROVE`

Q-W1 preserves public gate semantics and is acceptable from Architecture review. A-W1 contract hardening may proceed after this review under Manager's serial Wave 2 dispatch, with no parallel write.

## Files / Diff Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
- `coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml`
- `coordination/reports/GVLA-M2-HARDEN-001/wave1-manager-synthesis.md`
- `coordination/reports/GVLA-M2-HARDEN-001/wave2-quality-dispatch.md`
- `coordination/reports/GVLA-M2-REMOTE-CI-003/owner-quality.md`
- `runs/tmp/GVLA-M2-HARDEN-001/quality/remote-ci-plan.md`
- `.github/workflows/genesisvla.yml`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- Focused Q-W1 diff for:
  - `.github/workflows/genesisvla.yml`
  - `scripts/quality/bootstrap_project_local_tools.sh`
  - `tests/meta/test_repo_policy.py`

Focused `git diff --name-status` confirms Q-W1 changed only:

- `M .github/workflows/genesisvla.yml`
- `M scripts/quality/bootstrap_project_local_tools.sh`
- `M tests/meta/test_repo_policy.py`

## Evidence Checked

- Quality report conclusion: `PASS`.
- Quality recorded:
  - `bash -n scripts/quality/bootstrap_project_local_tools.sh`: `PASS`
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -q`: `PASS`, `21 passed`
  - `bash scripts/quality/bootstrap_project_local_tools.sh`: `PASS`
  - `make genesis-check`: `PASS`, product pytest `131 passed`, product Black/Ruff/Pyright passed, governance pytest `21 passed`
  - `make governance-check`: `PASS`
  - `make genesis-build-check`: `PASS`
  - `git diff --check`: `PASS`
  - bidi-control scan: `PASS`
- Architecture reran only lightweight read-only inspection:
  - `git diff --check`: `PASS`
  - focused diff/name-status inspection for the Q-W1 files

I did not rerun broad gates because Quality already recorded fresh green local gate evidence for this Q-W1 change and this review only needed Architecture confirmation of public gate semantics.

## Gate / Bootstrap Assessment

Public gate semantics are preserved:

- Existing `make genesis-check` and `make governance-check` workflow steps remain present.
- Q-W1 adds `make genesis-build-check` after the existing genesis and governance gates; it does not replace or weaken them.
- Workflow path filters now include `requirements/quality/**`, matching the quality-lock dependency surface.
- The workflow uses `actions/cache@v4` for the wheelhouse and pip cache only.

Offline-first bootstrap behavior is preserved:

- The normal bootstrap command remains `bash scripts/quality/bootstrap_project_local_tools.sh`.
- Missing wheelhouse distributions without `--fill-wheelhouse` still print the missing list and exit `66`.
- `--fill-wheelhouse` writes a project-local missing-requirements file and downloads only the missing pinned distributions from the wheelhouse check.
- If the wheelhouse is already complete, `--fill-wheelhouse` creates an empty missing-requirements file and skips unnecessary downloads.
- Offline installation still uses `--no-index` and `--find-links`.

Dependency drift is not hidden:

- The wheelhouse fingerprint includes Python/platform data plus hashes for `quality-requirements.txt`, `quality-constraints.txt`, and `pyproject.toml`.
- The CI cache key includes runner OS, runner architecture, Python `py3.10`, and the same quality lock/pyproject hashes.
- The bootstrap script re-runs missing-wheel verification, writes/verifies the wheelhouse manifest, and validates installed package versions against constraints.

Cache policy is bounded:

- Cached paths are limited to `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/wheelhouse` and `runs/tmp/m1-tool-pip-cache`.
- The cache block does not include `runs/tmp/m1-tool-venv`, clean-install venvs, or broad `runs/tmp/**`.

Meta policy coverage matches the public gate contract:

- `tests/meta/test_repo_policy.py` now asserts workflow path filters, cache path restrictions, cache-key inputs, `--fill-wheelhouse`, build gate presence, exit 66/missing-requirements behavior, and bidi-control rejection.
- These tests tighten governance around the gate rather than weakening product validation.

## Scope / Protected Path Assessment

`PASS`

No protected product source, dataloader, model, training, deployment, acceleration, dataset, code-input, feature-list pass field, PR state, git index, branch, or remote mutation is part of Q-W1. The changed files are limited to the Quality-owned workflow/bootstrap/meta-policy scope plus the Quality report.

## Blockers

None from Architecture for Q-W1.

Residual known blockers remain outside this review:

- Exact remote CI success is not yet proven because Q-W1 was not allowed to commit/push/update PR. That belongs to `GVLA-M2-PR2-VERIFY-003`.
- M3-blocking M2 public contract/data issues remain for the later serial A-W1 and D-W1 tasks.

## A-W1 Proceed Decision

`YES_FROM_ARCHITECTURE`

A-W1 contract hardening may proceed after this Architecture review, assuming Manager maintains the approved Wave 2 serial order and does not run any parallel writer. This review approves only Q-W1 gate/bootstrap semantics; A-W1 must still follow the amended `GVLA-M2-CONTRACT-HARDEN-002` scope and its own validation/reporting requirements.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, new worktree, new Python environment, stage, commit, push, PR edit, merge, stash, reset, restore, clean, rm, feature-list pass update, or completion-state update was used.

## Subagent Retirement Ledger

No short-lived Architecture subagent was used for this read-only review. The review was performed directly in the persistent Architecture Owner thread. No child subagent remains active.

## Parallelism Note

Read-only Architecture review only; no parallel write.
