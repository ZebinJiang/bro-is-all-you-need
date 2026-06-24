# GVLA-M2-FINAL-CLOSURE-001 Data Owner Wave 1 Plan

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- expected_head: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace_check: PASS
- `git status --short`: current dirty state is coordination/task/report evidence only, including FINAL-CLOSURE task cards/reports, HARDEN manager summary/reviews, and REMOTE-CI evidence. Data made no source/test/tooling/task-state/git-index changes in Wave 1.

## Reviewed evidence

- `coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml`
- `coordination/tasks/active/GVLA-M2-FINAL-DATA-001.yaml`
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave0-manager-preflight.md`
- `coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- `docs/references/upstream_sources.yaml`
- `genesisvla/testing/fixtures/README.md`
- `genesisvla/testing/fixtures/tiny.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/dataloader/transforms/action_mode.py`
- `genesisvla/dataloader/statistics/schema.py`
- Relevant `tests/dataloader/**`
- Official upstream references:
  - LeRobot v0.5.1 release: `https://github.com/huggingface/lerobot/releases/tag/v0.5.1`
  - LeRobot v0.5.1 commit: `https://github.com/huggingface/lerobot/commit/1396b9fab7aecddd10006c33c47a487ffdcb54b4`
  - LeRobotDataset v3.0 docs: `https://huggingface.co/docs/lerobot/lerobot-dataset-v3`

## Conclusions

Decision: PASS_PLAN.

- User decision supersedes prior non-blocking fixture deferral. F2.7/F2.8 must move from `real_format=false` to generated actual file-format evidence before M2 can be ready for next stage.
- Q-W1 must run before Data D-W1 because current `runs/tmp/m1-tool-venv` does not have PyArrow available.
- Data D-W1 can implement the real-format fixtures and residual contract fixes without M3 behavior, without real dataset downloads, and without committing generated fixture binaries.
- Mandatory official LeRobot package loader verification is not recommended because it would expand mandatory dependencies beyond the M2 fixture boundary. Data should validate LeRobot v3 layout/schema directly and record upstream release/revision provenance.

## Required planning outputs

- D-RO1 LeRobot format plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/lerobot-format-plan.md`
- D-RO2 Parquet fixture plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/parquet-format-plan.md`
- D-RO3 residual contract plan: `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/data/residual-contract-plan.md`

## Proposed Q-W1 then D-W1 serial flow

### Q-W1 first: fixture dependency/toolchain

Quality should implement `GVLA-M2-FIXTURE-DEPS-001` before Data writes tests that import PyArrow:

- Add pinned PyArrow or approved equivalent to test/quality dependency scope.
- Record version, license, wheel availability, and provenance.
- Update wheelhouse/bootstrap behavior so fresh-runner offline gates still pass.
- Add meta tests and a tiny PyArrow write/read smoke under Quality scope.
- Validate:
  - `bash scripts/quality/bootstrap_project_local_tools.sh --fill-wheelhouse`
  - `bash scripts/quality/bootstrap_project_local_tools.sh`
  - `runs/tmp/m1-tool-venv/bin/python -c "import pyarrow.parquet"`
  - `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta -q`
  - `git diff --check`

### D-W1 second: real-format fixtures and residual contracts

Data should implement after Q-W1 and Architecture/Quality dependency review:

- Generate LeRobot v3 camera-free fixture directories under `tmp_path` or approved `runs/tmp/**`.
- Generate actual PyArrow Parquet files and read them back into `RawSample`.
- Update tiny fixture provenance to `real_format=true` for real-format paths; rename/label old in-memory helpers as `*-like` if retained.
- Add malformed fixture tests for missing metadata, missing data shard, bad episode bounds, missing columns, wrong dtypes, and corrupt Parquet footer.
- Close residual Data-contract findings:
  - deterministic image modality key-set collation;
  - strict bool action masks and valid masks;
  - finite/positive `ImageNormalize` stats;
  - one-dimensional state requirement for relative action mode;
  - stricter statistics invariants and fingerprints.
- Update `docs/genesisvla/m2_transform_data_contract.md`, ADR, and upstream source registry as needed.

## Proposed D-W1 write scope

- `genesisvla/testing/fixtures/**`
- `genesisvla/dataloader/**`
- `tests/dataloader/**`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- `docs/references/upstream_sources.yaml`
- `coordination/reports/GVLA-M2-FINAL-DATA-001/**`

No writes should occur under `genesisvla/core/**`, model/training/deployment/acceleration, `datasets/**`, `code-input/**`, generated fixture binaries, feature_list pass fields, or M3 code.

## Risks

- PyArrow dependency integration can affect offline wheelhouse bootstrap and must be owned by Quality first.
- The exact LeRobot v3 schema details should stay pinned to `v0.5.1` / `1396b9fab7aecddd10006c33c47a487ffdcb54b4`; any later upstream change is out of scope unless Manager explicitly refreshes the target.
- Camera-free LeRobot v3 is the lowest-dependency fixture path. If Architecture requires image-light MP4 evidence, that should be a separate scope decision because it introduces video codec/dependency risk.
- Strict mask/statistics hardening may reject values previously coerced by numpy; this is intended and covered by failing-before tests.
- Generated `.parquet` and dataset directories must not be staged or packaged.

## DevSpace MCP compliance

PASS. Data used only local shell reads plus public web lookups for exact upstream references. No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, or DevSpace-derived evidence was used.

## Subagent ledger

- D-RO1: not spawned as a separate tool context; planning performed directly by persistent Data Owner; retired at handoff.
- D-RO2: not spawned as a separate tool context; planning performed directly by persistent Data Owner; retired at handoff.
- D-RO3: not spawned as a separate tool context; planning performed directly by persistent Data Owner; retired at handoff.
- No write-capable subagent was used in Wave 1.

## Parallelism note

Wave 1 was read-only planning with one report write per required output. No parallel write occurred. Manager may dispatch Q-W1 then D-W1 serially after Wave 1 synthesis.
