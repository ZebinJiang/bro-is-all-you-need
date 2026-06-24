# GVLA-M2-CONTRACT-HARDEN-002 Data Review

Decision: APPROVE

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- workspace_check: PASS
- git status --short:

```text
 M .github/workflows/genesisvla.yml
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml
 M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml
 M docs/genesisvla/m2_transform_data_contract.md
 M genesisvla/dataloader/__init__.py
 M genesisvla/dataloader/collate.py
 M genesisvla/dataloader/statistics/schema.py
 M genesisvla/dataloader/transforms/__init__.py
 M genesisvla/dataloader/transforms/compose.py
 M scripts/quality/bootstrap_project_local_tools.sh
 M tests/dataloader/test_dataset_statistics.py
 M tests/dataloader/test_transform_registry.py
 M tests/meta/test_repo_policy.py
?? coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/
?? coordination/reports/GVLA-M2-HARDEN-001/
?? coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/manager-summary.md
?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md
?? coordination/reports/GVLA-M2-MILESTONE-AUDIT-001/
?? coordination/reports/GVLA-M2-REMOTE-CI-003/
?? coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml
?? coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml
?? coordination/tasks/active/GVLA-M2-HARDEN-001.yaml
?? coordination/tasks/active/GVLA-M2-PR2-VERIFY-003.yaml
?? coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml
?? genesisvla/dataloader/contracts.py
?? tests/dataloader/test_collate.py
```

The status includes A-W1 contract changes, Q-W1 toolchain/workflow changes, and
pre-existing coordination/report/task state. This Data review only wrote this
report.

## Files and evidence reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
- `coordination/reports/GVLA-M2-HARDEN-001/wave2-contract-review-dispatch.md`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-architecture.md`
- `runs/tmp/GVLA-M2-HARDEN-001/data/transform-action-plan.md`
- `runs/tmp/GVLA-M2-HARDEN-001/data/batch-statistics-plan.md`
- `runs/tmp/GVLA-M2-HARDEN-001/data/fixture-legacy-plan.md`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/transforms/compose.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/__init__.py`
- `genesisvla/dataloader/transforms/__init__.py`
- `tests/dataloader/test_transform_registry.py`
- `tests/dataloader/test_collate.py`
- `tests/dataloader/test_dataset_statistics.py`
- `docs/genesisvla/m2_transform_data_contract.md`
- `git diff --stat`, `git diff --name-only`, and focused diffs for A-W1
  contract files. Note: untracked `genesisvla/dataloader/contracts.py` and
  `tests/dataloader/test_collate.py` are not included by default diff output,
  so they were inspected directly.

## Review findings

No Data blocker found.

The A-W1 contract surface is usable for D-W1:

- `TransformSpec` is now dataloader-owned, versioned, strict JSON-safe,
  immutable from caller mutation, and includes implementation version fields
  that can participate in stable fingerprints.
- `SerializableTransformProtocol.to_spec()` gives Data a public serialization
  hook for production transforms without relying on dynamic `getattr()`.
- `ComposeTransform` now fails serialization clearly for runtime-only transforms
  and can deserialize through a registry supplied by Data D-W1.
- `TransformContext` includes the minimum deterministic execution fields Data
  needs for image augmentation and mixture/dataset provenance: seed, epoch,
  sample key/index, worker id/count, rank/world size, and JSON-safe metadata.
- `CollatedBatch` establishes the typed numpy-only batch surface Data requested:
  actions and masks are batch-major `[B,H,D]`, arrays are defensively owned and
  read-only, per-sample metadata/source provenance is represented, and legacy
  `[D]` masks are accepted only at the collate conversion boundary.
- `FeatureStatistics` and `DatasetStatistics` now defensively own arrays, mark
  them read-only, reject non-finite statistic values, and canonicalize metadata
  through the strict JSON contract.

Architecture did not over-implement Data-owned production factories or
action-mode policy. It added a generic registry and serialization contract
surface, but did not implement concrete production transform factories,
ActionMode zero-policy/reference behavior, image HWC/CHW augmentation policy,
mixture RNG, real fixture acceptance, or legacy adapter hardening.

Canonical action-mask semantics are acceptable for Data D-W1: sample actions
remain `[H,D]`, batch actions/masks are `[B,H,D]`, and legacy `[D]` masks are
limited to a documented collate boundary broadcast.

## Residual Data-owned work

The following remain expected D-W1 tasks, not blockers against A-W1:

- Add concrete production transform `to_spec()` implementations and registry
  factories for Data-owned transforms.
- Define and test ActionMode inverse/reference behavior, especially lossy
  `first_step_policy="zero"` handling.
- Complete HWC/CHW image behavior and context-derived deterministic
  augmentation.
- Extend normalization to combine statistics masks with per-sample action masks.
- Implement variable horizon/action-dim padding policy on the Data collate path.
- Harden statistics cache durability/concurrency beyond the Architecture-owned
  schema ownership changes.
- Add mixture worker/rank/sample deterministic sampling semantics.
- Resolve real Tiny Parquet/LeRobot fixture scope/dependency decisions and
  harden the legacy adapter.

## Blockers

None from Data review.

## Validation commands

- `git diff --check`: PASS. No whitespace errors were reported. The shell
  emitted the existing benign `whoami: cannot find name for user ID 2000`
  environment warning, but the command exited successfully.

Broad gates were not rerun because Architecture recorded full gate PASS and this
assignment requested only lightweight read-only checks unless necessary.

## Protected path and M1 regression assessment

APPROVE. The relevant A-W1 contract files stay within the amended Architecture
scope and the dataloader contract surface. No Data-visible model, training,
deployment, acceleration, dataset, code-input, feature-list pass, M1 completion,
git index, branch, remote, or PR state change was required for this review.

M1 public contracts remain usable from Data perspective. Core
`TransformProtocol` remains the minimal `RawSample -> RawSample` boundary, and
the new dataloader contract surface does not introduce a core-to-dataloader
dependency.

## Whether Data D-W1 may proceed

Yes, from Data perspective. D-W1 may proceed after Manager receives the remaining
required review outcome and confirms the serial handoff. D-W1 should use the
Architecture-owned contract surface instead of defining parallel Data-only
public types.

## DevSpace MCP compliance

PASS. This review used repository-local shell reads and one lightweight
read-only `git diff --check`. It did not use DevSpace MCP,
`vla-flywheel-devspace`, MCP connectors, `open_workspace`, or MCP
read/write/edit/bash.

## Subagent ledger

No short-lived Data subagent was used for this review. The review was performed
directly by the persistent Data Owner in read-only mode.

## Parallelism note

Read-only Data and Quality reviews may proceed in parallel per dispatch. No
parallel write occurred. Data D-W1 should remain a single serial writer after
contract review acceptance.
