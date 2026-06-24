# GVLA-M2-MILESTONE-AUDIT-001 Owner Architecture Audit

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required_published_head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- workspace_check: `PASS`
- status_short_before_report:
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml`
  - `M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
  - `?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`

PR summary:

- Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- PR head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- PR base: `dev/starvla-engineering-base` at `5e42b775f97d438ae58752f986284da9c4adf98b`
- Local stale branch note: local `dev/starvla-engineering-base` is not the audit base; this audit used the explicit PR base commit above.
- Remote CI context: Quality recorded remote `genesis-check` failure because wheelhouse distributions were unavailable and bootstrap exited `66`. This remains a publication/CI environment blocker, not an Architecture source-contract fix in this audit.

Architecture did not modify source, tests, tooling, task state, feature-list passes, PR state, git index, or completion state. This report is the only Architecture write.

## Decision

`REQUEST_CHANGES`

P0 count: `0`

P1 count: `2`

M3 entry architecturally blocked: `YES`, until the P1 public-contract risks below are resolved or explicitly converted by Manager into a documented non-M3-blocking limitation with follow-up ownership.

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
- `coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
- `coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`
- `coordination/reports/GVLA-M2-CORE-STATIC-002/owner-architecture.md`
- `coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/owner-architecture-prepub-review.md`
- `docs/coordination/plans/GVLA-M2-PLAN.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- PR/local diff against base commit `5e42b775f97d438ae58752f986284da9c4adf98b`
- Key public-contract files:
  - `genesisvla/core/protocols/transform.py`
  - `genesisvla/core/protocols/__init__.py`
  - `genesisvla/core/types/action.py`
  - `genesisvla/dataloader/transforms/compose.py`
  - `genesisvla/dataloader/transforms/action_mode.py`
  - `genesisvla/dataloader/transforms/image.py`
  - `genesisvla/dataloader/transforms/state_action.py`
  - `genesisvla/dataloader/statistics/schema.py`
  - `genesisvla/dataloader/statistics/cache.py`
  - `genesisvla/dataloader/datasets/mixture.py`
  - `genesisvla/dataloader/legacy/__init__.py`
  - `tests/dataloader/**`

PR diff summary against the explicit PR base: `72 files changed, 6823 insertions(+), 33 deletions(-)`.

## Findings

### P1: Dataset statistics arrays are mutable and can alias caller-owned inputs

Evidence:

- `genesisvla/dataloader/statistics/schema.py:33-40` converts arrays with `np.asarray(value, dtype=np.float64)` and returns the result without a defensive copy or read-only flag.
- `genesisvla/dataloader/statistics/schema.py:43-50` does the same for `valid_mask`.
- `genesisvla/dataloader/statistics/schema.py:117-121` stores those arrays on a frozen dataclass, but the contained NumPy arrays remain mutable.

Impact:

`FeatureStatistics` and `DatasetStatistics` are public M2 cache/schema objects. A caller that passes an existing `float64` or bool array can mutate the original array after construction, or mutate the stored array directly, changing normalization behavior and serialized checksum output without constructing a new statistics object. That weakens mutable data ownership, reproducibility, and cache integrity before M3 training/runner code consumes statistics as stable inputs.

Required Architecture follow-up:

Defensively own statistics arrays at construction time. Prefer `np.array(..., dtype=..., copy=True)` plus `setflags(write=False)` for `mean`, `std`, `minimum`, `maximum`, and `valid_mask`; add focused tests showing source-array mutation and direct stored-array writes cannot mutate the public statistics contract.

### P1: Transform/statistics fingerprints do not encode transform implementation or contract version

Evidence:

- `genesisvla/dataloader/transforms/compose.py:52-67` defines `TransformSpec` as only `name` plus mutable `params`.
- `genesisvla/dataloader/transforms/compose.py:70-74` computes the transform fingerprint only from each spec's canonical name/params payload.
- `genesisvla/dataloader/statistics/cache.py:36-45` treats the stored `transform_fingerprint` as the stale-cache guard.

Impact:

If a transform implementation changes while its name and params remain the same, existing statistics cache files can still pass the transform-fingerprint check. That is a public schema/versioning risk for M3, where statistics may become training-affecting evidence. Also, because `TransformSpec.params` is stored as a `Mapping` without canonical defensive ownership, caller mutation of a backing dict can change later fingerprints for an already-created spec.

Required Architecture follow-up:

Add a stable transform/schema versioning strategy before M3 depends on cached statistics. Acceptable shapes include an explicit transform implementation/contract version in `TransformSpec` or registry metadata, and immutable/canonical params owned at `TransformSpec` construction. The fingerprint should cover the versioned public transform contract, not only current name/params.

## Contract Surface Assessment

Public protocols:

- `TransformProtocol` is correctly placed under `genesisvla/core/protocols` and remains a structural `RawSample -> RawSample` protocol.
- No runtime `isinstance` checks against the protocol, `runtime_checkable`, or altered protocol semantics were found in the reviewed contract path.

Registry/factory API:

- `TransformRegistry.register` rejects duplicate names and `create` rejects unknown names.
- Tokenizer/processor/device-transfer fields are rejected at the generic transform-spec boundary, which keeps M2 data transforms model-agnostic.
- The registry API is acceptable for M2, subject to the P1 version/fingerprint follow-up.

TransformSpec and Compose API:

- `ComposeTransform` executes sequential `RawSample` transforms and verifies each step returns `RawSample`.
- Serialization/deserialization through `TransformSpec` and `ComposeConfig` is clear enough for M2.
- The public API should not be promoted into M3 dependency without resolving versioned fingerprints and params ownership.

Serialization/deserialization:

- Statistics JSON checksum support and atomic cache write are present.
- Residual P2 risk: `DatasetStatistics.from_json_dict` currently coerces `schema_version`, `dataset_fingerprint`, `transform_fingerprint`, `count`, metadata keys, and feature names through `str(...)`/`int(...)` in `genesisvla/dataloader/statistics/schema.py:245-259`. This is not a P1 blocker for M2 audit, but stricter schema decoding should be considered before externally authored statistics files are accepted.

Schema and implementation versioning:

- Statistics schema version is explicit as `2.0`.
- Transform implementation/contract version is not represented in the fingerprint model. This is a P1 public-contract gap before M3.

Transform/statistics fingerprints:

- Dataset and transform fingerprint checks exist.
- Transform fingerprint is config-only and therefore insufficient for implementation-version invalidation.

Mutable data ownership:

- `RawSample`/`ActionChunk` ownership and read-only behavior remain preserved.
- Statistics object ownership is not yet strong enough because arrays can remain mutable/aliased.

M1 compatibility:

- No M1 public contract break was found.
- `ImageLike: TypeAlias = NumericArray` and bool-only `ActionMask` remain compatible with the accepted M1/M2 direction.
- M2 does not introduce torch, runner/model/training/deployment semantics, or M1 public API redesign.

Scope:

- The PR diff adds M2 transform/data-contract surfaces and related tests/docs/tooling evidence.
- No M3 runtime, model, training, deployment, dataset dump, checkpoint, or code-input dependency was found in the reviewed Architecture path.

## Validation / Evidence Commands

Architecture did not rerun broad gates in this read-only milestone audit. Reviewed evidence includes Quality's local PASS records:

- `bash scripts/quality/bootstrap_project_local_tools.sh`: `PASS`
- `make genesis-check`: local `PASS`, `131 passed`, product Pyright `0 errors`
- `make governance-check`: `PASS`
- `make genesis-build-check`: `PASS`
- `git diff --check`: `PASS`
- publication scans: `PASS`
- remote CI: `BLOCKED_TEST` due missing wheelhouse/bootstrap exit `66`

Read-only audit commands used for this report:

- workspace verification commands
- `git diff --shortstat 5e42b775f97d438ae58752f986284da9c4adf98b..HEAD`
- scoped `git diff --name-status` against the same base
- line-level inspection of the reviewed public-contract files

## Required Follow-Up

Blocking before M3 Architecture entry:

1. Fix statistics array ownership/read-only behavior and add focused tests.
2. Add versioned transform/statistics fingerprint semantics and immutable/canonical `TransformSpec` params ownership.

Non-blocking but recommended before accepting external statistics files:

- Tighten `DatasetStatistics.from_json_dict` and `FeatureStatistics.from_json_dict` to reject unexpected coercions instead of silently converting schema/count/name fields.

Remote CI follow-up:

- Quality/Manager must address the recorded remote CI bootstrap/wheelhouse mismatch separately. Architecture did not attempt to fix or reclassify that CI failure.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, new worktree, new Python environment, stage, unstage, commit, push, PR update, merge, stash, reset, restore, clean, rm, source/test/tooling edit, feature-list pass update, or completion-state update was used.

## Subagent Retirement Ledger

No short-lived Architecture subagent was used. A-RO2 was considered unnecessary because the public-contract evidence was available from the published diff and prior Owner reports. No subagent retirement was required.

## Parallelism Note

Read-only Architecture milestone audit only; no parallel write.
