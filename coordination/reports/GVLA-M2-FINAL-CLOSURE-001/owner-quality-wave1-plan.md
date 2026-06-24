# GVLA-M2-FINAL-CLOSURE-001 Wave 1 Quality Plan

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- required branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required base head: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace check: PASS.
- `git status --short`: dirty coordination/report/task evidence only; no source, test,
  dependency, workflow, PR, index, feature-list, or M3 changes were made by Quality in Wave 1.

## Reviewed inputs

- `coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml`
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`
- `coordination/tasks/active/GVLA-M2-FINAL-PUBLISH-001.yaml`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave0-manager-preflight.md`
- `coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md`
- `requirements/quality/quality-requirements.txt`
- `requirements/quality/quality-constraints.txt`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `.github/workflows/genesisvla.yml`
- `Makefile`
- `tests/meta/test_repo_policy.py`
- `pyproject.toml`
- PyPI project metadata for `pyarrow==18.1.0`.

## Dependency recommendation

Decision: recommend adding `pyarrow==18.1.0` as the pinned test/quality-only Parquet backend.

Rationale:

- The final-closure findings require actual generated Parquet write/read evidence for F2.8.
- Current quality dependency lock has no Parquet backend.
- PyArrow provides direct `pyarrow.parquet` support without pulling full LeRobot into the quality
  environment.
- `pyarrow==18.1.0` is Apache Software License, supports Python `>=3.9`, lists Python 3.10 support,
  and publishes CPython 3.10 manylinux x86_64 wheels. Expected Linux wheelhouse impact is about
  40 MB for the runner platform.
- Full `lerobot` is not mandatory for this closure wave because M2 needs generated actual
  file-format fixtures and RawSample adapter coverage, not official LeRobot runtime/package
  execution. A full LeRobot dependency should be routed separately only if Manager/Architecture
  decides official loader execution is part of M2 acceptance.

Detailed Q-RO1 plan:
`runs/tmp/GVLA-M2-FINAL-CLOSURE-001/quality/fixture-dependency-plan.md`

## Required Q-W1 scope

Q-W1 should be the single Quality writer after Wave 1 synthesis. Allowed write scope should remain
the `GVLA-M2-FIXTURE-DEPS-001` surfaces:

- `requirements/quality/quality-requirements.txt`
- `requirements/quality/quality-constraints.txt`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- optionally `docs/references/upstream_sources.yaml` or `docs/genesisvla/m2_*` if Manager requires
  license/provenance wording
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/**`

Q-W1 should not edit:

- `genesisvla/core/**`
- `genesisvla/dataloader/**`
- `genesisvla/testing/fixtures/**`
- `tests/dataloader/**`
- generated fixture binaries
- `.agent-docs/feature_list.json`
- PR body or git index

Concrete implementation requirements for Q-W1:

- Add direct quality dependency `pyarrow`.
- Add exact constraint `pyarrow==18.1.0`.
- Add `pyarrow` to bootstrap readiness stamp direct-package evidence.
- Keep PyArrow out of product `[project].dependencies` unless Architecture explicitly approves.
- Keep final installation offline via project-local wheelhouse.
- Add focused meta test coverage for:
  - PyArrow lock and exact pin;
  - actual Parquet write/read smoke under pytest `tmp_path`;
  - no generated `.parquet` file under repo/runs publication scope.

## Validation plan

Q-W1 must run and record:

- `bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse`
- `bash scripts/quality/bootstrap_project_local_tools.sh`
- `runs/tmp/m1-tool-venv/bin/python -c "import pyarrow.parquet"`
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -q`
- `make governance-check`
- `make genesis-check`
- `make genesis-build-check`
- `git diff --check`

After Data D-W1 uses the dependency, Quality should require:

- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q`
- full project-local gate and build gate again before publication.

## Publication implications

- Adding PyArrow changes the quality lock and will create a new wheelhouse fingerprint.
- GitHub Actions cache key already hashes `quality-requirements.txt`,
  `quality-constraints.txt`, and `pyproject.toml`; no cache-key redesign is needed unless Q-W1
  finds a real mismatch.
- Do not stage wheelhouse, pip cache, generated Parquet files, datasets, run outputs, or binary
  artifacts.
- Final publication should include explicit pathspecs only and staged scans from
  `.agent-docs/git_workflow.md`.
- `GVLA-M2-FINAL-PUBLISH-001` should include final Wave 4B/Wave 5 and final-closure governance
  evidence in an explicit publication evidence commit if Manager wants the PR head to carry the
  complete closure record.

## DevSpace MCP compliance

PASS. Quality used local shell/git/project-file inspection and PyPI web metadata only. DevSpace MCP,
`vla-flywheel-devspace`, MCP connectors, `open_workspace`, MCP read/write/edit, and MCP bash were
not used as workflow or evidence.

## Subagent retirement ledger

- Q-RO1: used for read-only dependency and CI planning.
- Q-RO1 output:
  `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/quality/fixture-dependency-plan.md`
- Q-RO1 retired: yes.
- Other short-lived Quality subagents: none used.
- Active Quality subagent contexts remaining: none.

## Parallelism

- Wave 1 read-only planning only.
- No parallel write.
- No source/test/dependency/workflow/task-state/PR/index/feature-list mutation.

## Dispatch recommendation

Decision: PASS_PLAN.

Manager may dispatch Q-W1 after Wave 1 synthesis, provided Q-W1 remains serialized before Data
D-W1 and uses the narrow `GVLA-M2-FIXTURE-DEPS-001` write scope.
