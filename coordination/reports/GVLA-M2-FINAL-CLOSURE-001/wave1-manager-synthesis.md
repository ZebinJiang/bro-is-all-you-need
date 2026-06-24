# GVLA-M2-FINAL-CLOSURE-001 Wave 1 Manager Synthesis

Task: GVLA-M2-FINAL-CLOSURE-001
Mode: PLAN -> OWNER_READONLY_PLANNING -> MANAGER_SYNTHESIS -> SERIAL_QW1
Canonical worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
Branch: `dev/feat-m2-transform-data-contract-v2-restacked`
Base head under review: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`

## Manager Decision

Wave 1 planning is complete. Manager may proceed to serialized Wave 2 by dispatching only `GVLA-M2-FIXTURE-DEPS-001` Q-W1 to Quality.

Do not dispatch Data D-W1 until Q-W1 passes, the project-local tool environment can import `pyarrow.parquet`, and the dependency/bootstrap changes are reviewed as required.

Current conclusion: `WAVE1_COMPLETE_QW1_DISPATCHED`.

M2 engineering is not complete. M3/M4 work must not start from the current head.

## Owner Planning Results

- Architecture: `PASS_PLAN`
  - Report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-architecture-wave1-plan.md`
  - Contract: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/architecture/final-contract-review.md`
  - Decision: proceed with Q-W1 first, then D-W1 serially.
- Data: `PASS_PLAN`
  - Report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-data-wave1-plan.md`
  - Plans:
    - `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/lerobot-format-plan.md`
    - `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/parquet-format-plan.md`
    - `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/residual-contract-plan.md`
  - Decision: Q-W1 dependency/toolchain work must precede D-W1 because PyArrow is not present.
- Quality: `PASS_PLAN`
  - Report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-quality-wave1-plan.md`
  - Plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/quality/fixture-dependency-plan.md`
  - Decision: add pinned test/quality-only `pyarrow==18.1.0`, then validate offline bootstrap and meta smoke.
- Training: `REQUEST_CHANGES`
  - Report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-training-wave1-plan.md`
  - Plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/training/m3-readiness-plan.md`
  - Decision: M3 readiness is not ready until P1 final findings close, but Manager may proceed with final-closure hardening.
- Model: `REQUEST_CHANGES`
  - Report: `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-model-wave1-plan.md`
  - Plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/model/m4-readiness-plan.md`
  - Decision: no M2 API redesign is required, but strict mask/statistics/real-format evidence must close before M4 confidence.

## Contract Synthesis

- F2.7 PASS requires generated actual LeRobot-format fixture evidence with `real_format=true`. Current in-memory lookalike evidence remains partial.
- F2.8 PASS requires generated actual `.parquet` files written and read during tests with `real_format=true`.
- LeRobot format target is pinned to LeRobotDataset v3.0, release selector `v0.5.1`, upstream commit `1396b9fab7aecddd10006c33c47a487ffdcb54b4`.
- Full `lerobot` package execution is not mandatory for M2 final closure unless a later scoped review explicitly expands acceptance.
- Q-W1 dependency recommendation is `pyarrow==18.1.0`, test/quality-only, Apache Software License, exact-pinned in quality constraints.
- Relative action mode must reject multidimensional or temporal state under M2; no implicit flattening.
- Action masks and statistics masks must reject numeric/string/object coercion. Bool arrays and Python bool-only sequences may be accepted and copied to owned `np.bool_` arrays.
- The final fixes are M2 Draft hardening, not M1 public contract breaks.

## Required Q-W1 Scope

Primary Owner: Quality.

Allowed Q-W1 write scope:

- `requirements/quality/quality-requirements.txt`
- `requirements/quality/quality-constraints.txt`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `tests/meta/test_repo_policy.py`
- `docs/references/upstream_sources.yaml` only if needed for PyArrow provenance
- `docs/genesisvla/m2_*` only if needed for narrow dependency/provenance wording
- `coordination/reports/GVLA-M2-FIXTURE-DEPS-001/**`
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`

Q-W1 must not edit dataloader/source fixture implementation, `tests/dataloader/**`, generated fixture binaries, feature-list pass fields, PR body, or git index.

Required Q-W1 validation:

- `bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse`
- `bash scripts/quality/bootstrap_project_local_tools.sh`
- `runs/tmp/m1-tool-venv/bin/python -c "import pyarrow.parquet"`
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -q`
- `make governance-check`
- `make genesis-check`
- `make genesis-build-check`
- `git diff --check`

## D-W1 Gate

Data D-W1 remains blocked until Q-W1 passes and Manager performs synthesis/review dispatch. D-W1 must close generated real-format fixture evidence and residual contract findings, but it must not implement M3, commit generated binaries, or change M1 public contracts.

## DevSpace MCP Compliance

- Manager used DevSpace MCP: no
- Architecture Owner used DevSpace MCP: no
- Data Owner used DevSpace MCP: no
- Quality Owner used DevSpace MCP: no
- Training Owner used DevSpace MCP: no
- Model Owner used DevSpace MCP: no
- Evidence depends on DevSpace MCP: no
- Result: PASS

## Subagent Retirement Ledger

- A-RO1: used by Architecture; timed out/no output; retired yes.
- D-RO1/D-RO2/D-RO3: not spawned as separate tool contexts; direct Data planning; retired at handoff.
- Q-RO1: used by Quality; output written; retired yes.
- T-RO1: used by Training; read-only memo returned; retired yes.
- M-RO1: used by Model; read-only memo returned; retired yes.
- No write-capable short-lived subagent was used in Wave 1.
- No new persistent Owner threads were created or archived.

## Parallelism

Wave 1 planning used read-only parallel Owner routing. No parallel write occurred. Wave 2 must be serial: Quality dependency writer first, then Data implementation writer only after Q-W1 passes.

## Next Step

Dispatch `GVLA-M2-FIXTURE-DEPS-001` Q-W1 to Quality as the sole writer. Stop before Data D-W1 until the Q-W1 Owner report and required validation are available.
