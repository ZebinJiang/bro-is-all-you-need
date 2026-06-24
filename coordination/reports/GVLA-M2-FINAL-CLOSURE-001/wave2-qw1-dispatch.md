# GVLA-M2-FINAL-CLOSURE-001 Wave 2 Q-W1 Dispatch

Task: GVLA-M2-FIXTURE-DEPS-001
Parent: GVLA-M2-FINAL-CLOSURE-001
Owner: 60-OWNER Quality
Thread id: `019eeea5-b5e8-71a1-b0a0-fe7ae4a9e147`
Dispatch mode: serialized Quality writer
Dispatch result: sent

## Inputs

- Manager synthesis: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave1-manager-synthesis.md`
- Quality Wave 1 report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-quality-wave1-plan.md`
- Q-RO1 plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/quality/fixture-dependency-plan.md`
- Task card: `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`

## Dispatch Scope

Quality is authorized as the only Wave 2 writer for the dependency/toolchain tranche. Data D-W1 remains blocked until Q-W1 passes and Manager reviews the Q-W1 report.

Allowed write scope:

- `requirements/quality/quality-requirements.txt`
- `requirements/quality/quality-constraints.txt`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- `docs/references/upstream_sources.yaml` only if needed for PyArrow provenance
- `docs/genesisvla/m2_*` only if needed for narrow dependency/provenance wording
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/**`

Protected for Q-W1:

- `genesisvla/core/**`
- `genesisvla/dataloader/**`
- `genesisvla/testing/fixtures/**`
- `tests/dataloader/**`
- generated fixture binaries
- PR body
- git index
- `.agent-docs/feature_list.json` pass fields

## Required Validation

- `bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse`
- `bash scripts/quality/bootstrap_project_local_tools.sh`
- `runs/tmp/m1-tool-venv/bin/python -c "import pyarrow.parquet"`
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -q`
- `make governance-check`
- `make genesis-check`
- `make genesis-build-check`
- `git diff --check`

## Governance

- DevSpace MCP dependency: forbidden
- New source worktree: forbidden
- Parallel write: none
- Stage/commit/push/PR/merge: forbidden in Q-W1
- Data D-W1: not dispatched

## Expected Output

`coordination/reports/GVLA-M2-FIXTURE-DEPS-001/owner-quality-qw1.md`
