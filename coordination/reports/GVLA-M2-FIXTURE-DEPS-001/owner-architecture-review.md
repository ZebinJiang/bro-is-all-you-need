# GVLA-M2-FIXTURE-DEPS-001 Owner Architecture Review

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- required base head at Wave 1 review: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace_check: PASS.
- `git status --short` before this report write showed existing coordination/task/report dirt plus Q-W1 changes to quality requirements, bootstrap, meta policy, and provenance. Architecture did not stage, commit, push, PR, merge, rebase, reset, restore, clean, rm, stash, start Data D-W1, start M3, or modify feature-list pass fields.

## Files reviewed

- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/owner-quality-qw1.md`
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/manager-qw1-review.md`
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`
- `requirements/quality/quality-requirements.txt`
- `requirements/quality/quality-constraints.txt`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- `docs/references/upstream_sources.yaml`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave1-manager-synthesis.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-architecture-wave1-plan.md`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/architecture/final-contract-review.md`
- focused read-only checks:
  - `git diff --name-status`
  - `git diff --check`
  - `git diff --cached --name-only`
  - `rg -n "pyarrow|PyArrow" genesisvla pyproject.toml Makefile .github/workflows tests/dataloader tests/meta docs/references/upstream_sources.yaml requirements/quality scripts/quality`

## Decision

APPROVE.

Data D-W1 proceed recommendation: YES.

## Findings / blockers

No Architecture blockers.

## PyArrow dependency assessment

`pyarrow==18.1.0` is acceptable as a test/quality-only dependency for the M2 real-format Parquet fixture closure. It is added to `requirements/quality/quality-requirements.txt` and pinned in `requirements/quality/quality-constraints.txt`; it is not added to `pyproject.toml`, Makefile public package metadata, GenesisVLA source imports, or dataloader public APIs.

The focused PyArrow reference scan found references only in:

- `requirements/quality/**`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- `docs/references/upstream_sources.yaml`

No references were found in `genesisvla/**`, `tests/dataloader/**`, `pyproject.toml`, `Makefile`, or `.github/workflows/**`.

## Bootstrap / wheelhouse / CI semantics assessment

The project-local bootstrap semantics are preserved. Q-W1 keeps the existing wheelhouse fingerprint and manifest flow, still installs with `--no-index --find-links "$WHEELS"`, and still uses project-local `runs/tmp/m1-tool-*` paths. The only bootstrap script diff is adding `pyarrow` to the direct installed-package health/stamp list so the ready stamp tracks the new quality dependency.

Quality recorded an initial network/proxy failure for `--fill-wheelhouse`, followed by a proxy-scoped retry using the project-approved proxy from `AGENTS.md`, then successful offline bootstrap, PyArrow import, meta tests, governance check, genesis check, build check, and `git diff --check`. This is sufficient for Q-W1 Architecture approval; final publication/remote exact-SHA evidence remains a later Quality/publication responsibility.

## Provenance / license assessment

`docs/references/upstream_sources.yaml` records PyArrow as Apache Arrow / PyPI `pyarrow==18.1.0`, license `Apache-2.0`, reuse type `test_quality_dependency`, dependency-only/no copied source, and a note that PyArrow must not be exposed from GenesisVLA public APIs without separate Architecture approval. This is architecturally sufficient for Q-W1.

## Meta coverage / gate assessment

`tests/meta/test_repo_policy.py` now checks the PyArrow quality dependency pin and includes an actual Parquet write/read smoke under pytest `tmp_path`. The smoke verifies Parquet magic bytes, row count, column names, and round-trip values. This adds coverage for the dependency needed by D-W1 and does not weaken public gate semantics.

`git diff --check` passed. `git diff --cached --name-only` was empty. No protected product/runtime paths or generated fixture binaries are staged.

## Scope assessment

Q-W1 stayed within the dependency/tooling/provenance/meta scope. It did not modify `genesisvla/core/**`, `genesisvla/dataloader/**`, `genesisvla/testing/fixtures/**`, `tests/dataloader/**`, model/training/deployment/acceleration paths, datasets, code-input, PR body, git index, or feature-list pass fields.

## Data D-W1 recommendation

YES. Data may proceed after Manager records this approval. D-W1 should use PyArrow only for generated real-format Parquet fixture tests/fixture helpers, keep generated files under `tmp_path` or governed `runs/tmp/**`, avoid publishing generated binaries, and preserve the Wave 1 Architecture contract for F2.7/F2.8, strict bool masks, one-dimensional relative state, image normalization invariants, and statistics invariants.

## DevSpace MCP compliance

PASS. This Architecture review used local shell/git/project-file inspection only. DevSpace MCP, `vla-flywheel-devspace`, MCP connectors, `open_workspace`, MCP read/write/edit, and MCP bash were not used.

## Subagent retirement ledger

No subagents were used for this review. No subagent retirement was required.

## Parallelism

Read-only Architecture review with one allowed report write. No parallel write.
