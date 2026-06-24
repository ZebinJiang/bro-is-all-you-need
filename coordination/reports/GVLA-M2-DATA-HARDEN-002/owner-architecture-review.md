# GVLA-M2-DATA-HARDEN-002 Owner Architecture Review

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- published_head_before_hardening: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- draft_pr: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- workspace_check: `PASS`
- status_short_reviewed: working tree contains expected Q-W1, A-W1, and D-W1 diffs plus coordination/report/task state. No staging, commit, push, PR edit, reset, restore, clean, stash, or deletion was performed by Architecture.

## Decision

`APPROVE`

Data D-W1 is architecturally coherent with the A-W1 public contract surface. Wave 3 may proceed from Architecture perspective after Quality also approves.

## Reviewed Evidence

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
- `coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
- `coordination/tasks/active/GVLA-M2-CONTRACT-HARDEN-002.yaml`
- `coordination/reports/GVLA-M2-HARDEN-001/wave2-data-review-dispatch.md`
- `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data.md`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-architecture.md`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-data-review.md`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-quality-review.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- Relevant source/test/docs under:
  - `genesisvla/dataloader/**`
  - `genesisvla/testing/fixtures/**`
  - `tests/dataloader/**`

## Validation / Inspection

- `git diff --check`: `PASS`.
- Protected-path diff check for `genesisvla/core`, `genesisvla/model`, `genesisvla/training`, `genesisvla/deployment`, `genesisvla/acceleration`, `datasets`, `code-input`, and `.agent-docs/feature_list.json`: no changed paths reported.
- DevSpace dependency scan over D-W1 task/report/docs/source/tests: no internal DevSpace workflow dependency found; only the Data report's compliance statement matched.
- D-W1 Data report recorded:
  - focused dataloader TDD validation: `65 passed`
  - `tests/dataloader`: `66 passed`
  - direct Pyright: `0 errors, 0 warnings, 0 informations`
  - final `make genesis-check`: `PASS`, product pytest `158 passed`, product Black/Ruff/Pyright passed, governance pytest `21 passed`

Broad gates were not rerun by Architecture because Data already recorded fresh full-gate evidence and this assignment requested lightweight read-only validation unless necessary.

## Findings / Blockers

No blocking Architecture findings.

Non-blocking residual note:

- `genesisvla/dataloader/transforms/__init__.py` uses narrow `cast(Any, ...)` bridges when converting JSON string params back into Literal-typed constructor arguments. This does not currently block acceptance because the target constructors validate the literal domains at runtime and Pyright/gates are green. A later polish task may replace these with Literal-specific parser helpers if Quality wants to avoid any `Any` casts in production code.

## Contract Boundary Assessment

`APPROVE`

D-W1 uses the A-W1 contract surface instead of defining a parallel public contract:

- Concrete transforms implement `to_spec()` returning A-W1 `TransformSpec`.
- `default_transform_registry()` reconstructs concrete Data transforms through A-W1 `TransformRegistry`.
- `ComposeTransform` remains the shared composition/serialization path.
- `TransformContext` is reused for deterministic image augmentation.
- `CollatedBatch` remains the typed batch contract for batch-major actions, masks, action horizon/dim metadata, metadata, and sample source.

Core remains clean: `genesisvla/core/**` was not modified by D-W1, and `TransformProtocol` remains the minimal `RawSample -> RawSample` boundary.

## Public Semantics Assessment

`APPROVE`

- Transform serialization/factories: D-W1 added production transform roundtrip through `to_spec()` and a fresh default registry without reintroducing dynamic `getattr()` as a public mechanism.
- Statistics/cache: D-W1 keeps `DatasetStatistics` / `FeatureStatistics` schema ownership and adds cache durability via same-directory temp file, file fsync, atomic replace, and best-effort directory fsync.
- Collate/mask semantics: variable horizon/action-dim padding now preserves canonical `[B,H,D]` mask semantics, records per-sample action sizes, and keeps legacy dict collation compatible.
- Action semantics: zero first-step inverse is explicitly rejected unless a first-action reference is supplied, which is preferable to silent lossy recovery.
- Image semantics: HWC/CHW and context-derived deterministic augmentation are explicit and remain numpy-only.
- Mixture metadata: worker/rank/world metadata and deterministic sample-source records are now explicit.
- Fixtures/legacy behavior: generated fixtures are labeled `real_format=false`; no real LeRobot/Parquet adapter or dependency-heavy fixture backend was smuggled into M2.

## Scope / Protected Path Assessment

`PASS`

D-W1 stayed within `genesisvla/dataloader/**`, `genesisvla/testing/fixtures/**`, `tests/dataloader/**`, and the M2 data contract doc/report scope. No model, training, deployment, acceleration, dataset, code-input, M1 public contract, feature-list pass field, PR, remote, or git index mutation was required.

## Deferrals

Accepted as non-blocking for this D-W1 review:

- Real LeRobot fixture loading and real Parquet fixture loading remain deferred because the current scope is tiny in-memory, dependency-light fixtures.
- Real LeRobot/Parquet adapters, dataset conversion, streaming datasets, model/training integration, and M3 runtime behavior remain future scoped work.
- PR #2 remote update and remote CI verification remain Quality/Manager publication work, not D-W1 Architecture scope.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, new worktree, new Python environment, stage, commit, push, PR edit/create, merge, force push, stash, reset, restore, clean, rm, feature-list pass update, or milestone completion update was used by Architecture.

## Subagent Ledger

No short-lived Architecture subagent was used for this read-only review. Review was performed directly in the persistent Architecture Owner thread. No child subagent remains active.

## Parallelism Note

Read-only Architecture review only. No parallel write. Wave 3 may proceed after Quality also approves.
