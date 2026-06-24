# GVLA-M2-RESTACK-001 Owner Quality Report

## Decision

BLOCKED_TEST

Restack mechanics completed successfully, no publication action was performed, and local git-history scans passed. The blocking validation is strict Pyright: `make genesis-check` and a direct Pyright run both fail with 42 type errors. A secondary tool gap was also recorded: `python -m build` is not available in the freshly bootstrapped project-local venv, so wheel build/content inspection was not completed.

## Source And Target

- Owner: `60-OWNER · Quality`
- Task: `GVLA-M2-RESTACK-001 · Restack the existing M2 candidate onto final M1 without remote publication`
- Final M1 SHA: `5e42b775f97d438ae58752f986284da9c4adf98b`
- Old M2 branch/head: `dev/feat-m2-transform-data-contract-v2-rebased` / `984273cba4168e3c9c6a603d33150453912bcca3`
- Old base: `a244c96c4dc8638033be1e8c555c39e0b77c12b3`
- Replay range: `a244c96c4dc8638033be1e8c555c39e0b77c12b3..984273cba4168e3c9c6a603d33150453912bcca3`
- Replay commits:
  - `19f7f32618f9d972e03eab84f3aa326b0916aef3`
  - `984273cba4168e3c9c6a603d33150453912bcca3`
- Target branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- Target worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- Target HEAD after restack/provenance commit: `e59f6b34bc6c76181b630d3b446a0438bff01da8`

## Preserved Dirty State From Old M2 Worktree

Manager preservation evidence was read from `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m1-closure-integration/runs/tmp/GVLA-M2-RESTACK-001/`.

- Preserved patch SHA256: `c7b57734b0019e8dd50994acc198091f3a09a58f0cfa93557f8f7414a4a93d01`
- Preserved dirty inventory:
  - `coordination/PROGRAM_STATE.yaml`
  - `coordination/TASK_INDEX.yaml`
  - `coordination/reports/GVLA-M2-CLOSURE-001/manager-summary.md`
  - `coordination/tasks/active/GVLA-M1-CI-002.yaml`
  - `coordination/tasks/active/GVLA-M1-CONTRACT-002.yaml`
  - `coordination/tasks/active/GVLA-M2-CLOSURE-001.yaml`
  - `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
  - `coordination/tasks/active/GVLA-M2-PUBLISH-001.yaml`
- The preserved patch was not applied.

## Worktree And Commit Evidence

- Target branch/worktree pre-check: branch and path did not exist before creation.
- Created clean worktree from final M1:
  - `git worktree add -b dev/feat-m2-transform-data-contract-v2-restacked /home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked 5e42b775f97d438ae58752f986284da9c4adf98b`
- Cherry-pick mapping:
  - `19f7f32618f9d972e03eab84f3aa326b0916aef3` -> `d6d6a1e` (`M2: add transform data contract tests`)
  - `984273cba4168e3c9c6a603d33150453912bcca3` -> `feca5ed` (`feat(m2-data): Add transform pipeline data contract.`)
- Conflict list: none. Both cherry-picks applied cleanly.
- Approved stale-base/provenance update commit:
  - `e59f6b3 chore(m2): restack data contract onto final M1`
  - Changed only:
    - `docs/coordination/plans/GVLA-M2-PLAN.md`
    - `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
    - `docs/references/upstream_sources.yaml`
- No M2 behavioral hardening or semantic fixes were made.

## Range-Diff And Stale-Base Review

- `git range-diff a244c96c4dc8638033be1e8c555c39e0b77c12b3..984273cba4168e3c9c6a603d33150453912bcca3 5e42b775f97d438ae58752f986284da9c4adf98b..HEAD`
  - `1: 19f7f32 = 1: d6d6a1e M2: add transform data contract tests`
  - `2: 984273c = 2: feca5ed feat(m2-data): Add transform pipeline data contract.`
- Stale-base search initially found `a244c96...` in approved M2 provenance docs and historical M1 coordination records.
- Updated only approved stale-base/provenance fields in the three allowed docs listed above.
- Final stale-base search still finds `a244c96...` only in historical M1 coordination reports/task cards; no current M2 docs/source/tests still point M2 provenance at the old base.

## Ancestry And Changed Files

- `git merge-base --is-ancestor 5e42b775f97d438ae58752f986284da9c4adf98b HEAD`: PASS
- `git diff --stat 5e42b775f97d438ae58752f986284da9c4adf98b..HEAD`: 34 files changed, 2351 insertions, 8 deletions.
- `git diff --name-only 5e42b775f97d438ae58752f986284da9c4adf98b..HEAD`:
  - `.gitignore`
  - `docs/coordination/plans/GVLA-M2-PLAN.md`
  - `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
  - `docs/genesisvla/m2_transform_data_contract.md`
  - `docs/references/upstream_sources.yaml`
  - `genesisvla/core/protocols/__init__.py`
  - `genesisvla/core/protocols/transform.py`
  - `genesisvla/dataloader/__init__.py`
  - `genesisvla/dataloader/collate.py`
  - `genesisvla/dataloader/datasets/__init__.py`
  - `genesisvla/dataloader/datasets/mixture.py`
  - `genesisvla/dataloader/legacy/__init__.py`
  - `genesisvla/dataloader/statistics/__init__.py`
  - `genesisvla/dataloader/statistics/cache.py`
  - `genesisvla/dataloader/statistics/schema.py`
  - `genesisvla/dataloader/transforms/__init__.py`
  - `genesisvla/dataloader/transforms/action_mode.py`
  - `genesisvla/dataloader/transforms/compose.py`
  - `genesisvla/dataloader/transforms/image.py`
  - `genesisvla/dataloader/transforms/state_action.py`
  - `genesisvla/testing/__init__.py`
  - `genesisvla/testing/fixtures/README.md`
  - `genesisvla/testing/fixtures/__init__.py`
  - `genesisvla/testing/fixtures/generate_tiny_fixtures.py`
  - `genesisvla/testing/fixtures/tiny.py`
  - `tests/dataloader/test_action_mode_transform.py`
  - `tests/dataloader/test_cpu_tiny_e2e.py`
  - `tests/dataloader/test_dataset_statistics.py`
  - `tests/dataloader/test_image_transforms.py`
  - `tests/dataloader/test_legacy_dataloader_adapter.py`
  - `tests/dataloader/test_mixture_dataset.py`
  - `tests/dataloader/test_state_action_normalization.py`
  - `tests/dataloader/test_tiny_fixtures.py`
  - `tests/dataloader/test_transform_registry.py`

## Local Validation Results

- `bash scripts/quality/bootstrap_project_local_tools.sh`: PASS
  - Project-local venv: `runs/tmp/m1-tool-venv`
  - Python: `3.12.13`
  - NumPy: `2.5.0`
  - Pyright: `1.1.410`
- `make genesis-check`: FAIL, exit 2
  - `product_py_compile`: PASS
  - `product_pytest`: PASS, 131 passed
  - `product_black_filelist_each`: PASS
  - `product_ruff`: PASS
  - `product_pyright`: FAIL, 42 errors
  - `governance_py_compile`: PASS
  - `governance_pytest`: PASS, 18 passed
  - `governance_black`: PASS
  - `governance_ruff`: PASS
- `make governance-check`: PASS, 18 passed
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q`: PASS, 39 passed
- `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`: FAIL, 42 errors
- `runs/tmp/m1-tool-venv/bin/python -m build --version`: FAIL, `No module named build`
  - Wheel build/content inspection was not run because the build module was not provided by the bootstrap environment.
- `git diff --check`: PASS
- `git diff --cached --check`: PASS
- `git status --short` before writing this report: clean

Pyright blocker file list:

- `genesisvla/core/types/action.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/datasets/mixture.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/testing/fixtures/tiny.py`
- `tests/dataloader/test_image_transforms.py`

Classification: strict typing gate failure. The reported diagnostics are mostly unknown/partially-unknown NumPy call/member types (`np.all`, `np.any`, `np.stack`, `reshape`, `copy`, `astype`, random choice, and related array inference). Because this task forbids M2 hardening, semantic fixes, and M1 public-contract edits, no code fix was attempted in this restack gate.

## Git-History Scan Results

- Branch check: PASS, `dev/feat-m2-transform-data-contract-v2-restacked`
- Whitespace check:
  - `git diff --check`: PASS
  - `git diff --cached --check`: PASS
- Conflict-marker check: PASS using strict conflict marker pattern. A broad first grep produced false positives from historical pytest separator lines in old reports; the exact conflict marker scan was clean.
- Secret scan over index/tracked working tree: PASS
- Staged artifact-extension scan: PASS; no staged candidate after local commits
- Large staged-file scan: PASS; no staged candidate after local commits
- Large staged text-diff scan: PASS; no staged candidate after local commits
- Final-M1..HEAD artifact-extension scan: PASS
- Final-M1..HEAD large-file scan: PASS
- Final-M1..HEAD large text-diff scan: PASS
- Upstream archive/source-tree exclusion over Final-M1..HEAD: PASS
- Wheel content inspection: not run because `python -m build` is unavailable in the bootstrapped venv.

## No-Publication And Worktree Boundaries

- No push was performed.
- No PR was created or updated.
- No merge was performed.
- No force operation was performed.
- No stash operation was performed.
- `git add .` was not used.
- The Manager-preserved coordination patch was not applied.
- Dirty main checkout `/home/cz-jzb/workspace/vla-flywheel` was not modified.
- Old dirty M2 candidate worktree `/home/cz-jzb/workspace/vla-flywheel/.worktrees/feat-m2-transform-data-contract-v2-rebased` was not modified.
- Branches `dev/starvla-engineering-base` and `dev/m1-closure-integration` were not modified.
- Feature-list pass fields were not modified.

## DevSpace MCP Compliance

PASS. DevSpace MCP, `vla-flywheel-devspace`, MCP connector tools, `open_workspace`, MCP read/write/edit/bash were not used as internal workflow or evidence.

## Subagent Retirement Ledger

No short-lived subagents were used. No active short-lived contexts remain.

## Parallelism

No parallel write. Only read-only local shell diagnostics/scans were run in parallel after the local restack commits were complete.

## Recommendation

Do not publish or continue M2-HARDEN from this branch yet. Route a follow-up fix decision for the strict Pyright failures, and separately decide whether `scripts/quality/bootstrap_project_local_tools.sh` should include the `build` module or whether build/wheel inspection should be handled by a dedicated project-local tooling task.
