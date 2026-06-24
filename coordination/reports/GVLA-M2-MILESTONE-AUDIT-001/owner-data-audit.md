# GVLA-M2-MILESTONE-AUDIT-001 Wave 5 Data Roadmap Audit

## Conclusion

REQUEST_CHANGES

Data audit completed read-only. The published M2 branch has strong local gate evidence and a real Draft PR, but the Data roadmap is not ready to treat M2 as complete for M3 entry. The main M3-blocking gaps are production transform reconstruction, zero first-step action invertibility policy, and the canonical batch/action-mask/source contract for training consumers.

- F2 matrix count: PASS 2, PARTIAL 7, FAIL 0, NOT_APPLICABLE_WITH_USER_APPROVAL 0.
- P0 findings: 0.
- P1 Data findings: 3.
- M3 blocked from Data perspective: YES, until the P1 Data contract findings below are resolved or Manager records explicit scope deferral.
- Remote CI context: PR #2 remote `genesis-check` is already recorded as failed because the GitHub runner is missing wheelhouse distributions and bootstrap exits 66. This report records that context only and does not attempt a fix.

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required published head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- workspace_check: PASS

`git status --short` before this report write:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml
 M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml
?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md
```

PR summary:

- Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- PR head: `dev/feat-m2-transform-data-contract-v2-restacked` at `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- PR base: `dev/starvla-engineering-base` at `5e42b775f97d438ae58752f986284da9c4adf98b`
- Local `dev/starvla-engineering-base` currently resolves to `c5c2e37885d7c67fa2fd59504c74ffa4509543e6`; audit used the task-provided PR base SHA for diff context.
- Remote CI: `BLOCKED_TEST`, `genesis-check` fails in bootstrap with missing wheelhouse distributions and exit 66.

## Evidence Reviewed

Required files read:

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
- `coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
- `coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`
- `coordination/reports/GVLA-M2-DATA-TYPING-001/owner-data-wave1.md`
- `coordination/reports/GVLA-M2-INTEGRATE-AUDIT-001/owner-data-prepub-review.md`
- `docs/coordination/plans/GVLA-M2-PLAN.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- `genesisvla/core/protocols/transform.py`
- `genesisvla/dataloader/**`
- `genesisvla/testing/fixtures/**`
- `tests/dataloader/**`
- local PR diff against `5e42b775f97d438ae58752f986284da9c4adf98b...HEAD`

Validation was not rerun in this Wave 5 audit because the assignment allowed only the report write, and dataloader tests use `tmp_path`. Instead, this audit inspected the Wave 4 local evidence in `owner-quality.md`: bootstrap PASS, `make genesis-check` PASS with product pytest `131 passed`, product Pyright `0 errors`, governance pytest `20 passed`, `make genesis-build-check` PASS, staged scans PASS, push PASS, and Draft PR creation PASS.

## F2.1-F2.9 Roadmap Matrix

| Feature | Status | Evidence | Finding |
| --- | --- | --- | --- |
| F2.1 TransformProtocol | PASS | `genesisvla/core/protocols/transform.py` defines structural `RawSample -> RawSample`; exported in protocols `__init__`. | Minimal but sufficient for M2. |
| F2.2 ComposeTransform | PARTIAL | Ordering, input/output guards, unknown-transform failure, canonical fingerprint, and test transform roundtrip exist. | Production transforms do not implement `serialize()`, and no production registry/factory roundtrip reconstructs `ImageResize`, `ImageNormalize`, `ImageAugment`, `StateActionNormalize`, or `ActionModeTransform`. P1. |
| F2.3 ImageResize / ImageNormalize / ImageAugment | PARTIAL | HWC resize, HWC normalize, deterministic flip, and invalid layout are tested. CHW code paths exist. | CHW resize/normalize and augment edge cases (`probability=0`, unsupported mode) are not tested; production transform serialization is absent. P2. |
| F2.4 StateActionNormalize / StateActionUnnormalize | PASS | mean/std roundtrip, min/max roundtrip, masked padding preservation, zero-variance identity, and dimension mismatch are tested. | Meets M2 Data expectation. |
| F2.5 ActionModeTransform | PARTIAL | absolute, delta with first-step `absolute`, relative with explicit mapping, empty horizon, invalid reference frame, and missing relative mapping are tested. | `first_step_policy="zero"` is accepted but not invertible for non-zero first actions and is not tested or documented as lossy. P1. |
| F2.6 DatasetStatistics schema/cache | PARTIAL | schema/checksum/fingerprint roundtrip, stale fingerprint rejection, JSON metadata rejection, and `os.replace` atomic write are tested. | Durability is only atomic replace; no file/directory fsync or crash-durability contract. P2. |
| F2.7 Tiny LeRobot fixture | PARTIAL | deterministic generated `RawSample` fixture with provenance, masks, stats, and CPU E2E use exists. | It is explicitly `lerobot-like-in-memory`, not a real minimum LeRobot directory/load format. P2 unless Manager accepts in-memory-only scope. |
| F2.8 Tiny Parquet fixture | PARTIAL | deterministic generated records with provenance and padding mask exist. | It is explicitly `parquet-like-in-memory`, with no pyarrow/parquet file and no real load path. P2 unless Manager accepts in-memory-only scope. |
| F2.9 Legacy dataloader adapter | PARTIAL | explicit robot_tag injection, action-dim rejection, unsupported-field warning/preservation are tested. | Failure modes for metadata type, missing images/language, required modalities, state_dim mismatch, and original robot_tag provenance are not covered in Data tests. P2. |

## PARTIAL Feature Details

### F2.2 ComposeTransform

- File/symbol: `genesisvla/dataloader/transforms/compose.py:129`, `ComposeTransform.serialize`; production transforms in `genesisvla/dataloader/transforms/image.py`, `state_action.py`, `action_mode.py`.
- Behavioral defect: `ComposeTransform.serialize()` only works for transform instances that provide a custom `serialize()` method. The shipped production transforms do not provide one, so the advertised production transform config roundtrip is not available.
- Missing test: production reconstruction roundtrip for a config containing real M2 transforms, including `ImageNormalize`, `StateActionNormalize`, and `ActionModeTransform`.
- Severity: P1.
- Responsible Owner: Data, with Architecture review for public transform contract shape.
- Proposed task ID: `GVLA-M2-DATA-COMPOSE-SERIALIZATION-003`.
- Blocks M3: YES. M3 should not depend on a transform config surface that cannot reconstruct the production transforms it declares.

### F2.3 Image Transforms

- File/symbol: `genesisvla/dataloader/transforms/image.py:13`, `ChannelOrder`; `ImageResize`, `ImageNormalize`, `ImageAugment`.
- Behavioral defect: CHW branches exist but are not covered by Data tests. Augment probability zero and unsupported mode are also untested.
- Missing test: CHW resize, CHW normalize, invalid resize size, channel-stat mismatch, probability zero no-op, unsupported augment mode, and multi-image mapping.
- Severity: P2.
- Responsible Owner: Data.
- Proposed task ID: `GVLA-M2-DATA-IMAGE-COVERAGE-004`.
- Blocks M3: NO for HWC-only M3 entry; YES if M3 consumers advertise CHW image pipelines without adding tests first.

### F2.5 ActionModeTransform

- File/symbol: `genesisvla/dataloader/transforms/action_mode.py:78-97`, `_absolute_to_delta`, `_delta_to_absolute`.
- Behavioral defect: with `first_step_policy="zero"`, converting absolute actions with a non-zero first step to delta drops the first absolute action; inverse reconstruction starts at zero, so roundtrip is lossy unless the first absolute action is already zero.
- Missing test: zero-policy roundtrip behavior and explicit failure/documentation for lossy non-zero first step.
- Severity: P1.
- Responsible Owner: Data, with Architecture review if the public action-mode contract changes.
- Proposed task ID: `GVLA-M2-DATA-ACTIONMODE-ZERO-005`.
- Blocks M3: YES until the zero policy is either made invertible with stored/reference first action, rejected for inverse use, or documented and excluded from M3 reversible pipelines.

### F2.6 DatasetStatistics Schema/Cache

- File/symbol: `genesisvla/dataloader/statistics/cache.py:12-24`, `save_statistics`; `schema.py:184-261`, `DatasetStatistics`.
- Behavioral defect: cache writes are atomic via same-directory temp file and `os.replace`, but no file fsync or directory fsync is performed. This is atomicity, not full crash durability.
- Missing test: crash/durability behavior is not tested; no explicit documentation that durability is best-effort atomic replace only.
- Severity: P2.
- Responsible Owner: Data, Quality for filesystem test feasibility.
- Proposed task ID: `GVLA-M2-DATA-STATS-DURABILITY-006`.
- Blocks M3: NO for CPU/local M3 entry; should be resolved before claiming durable dataset-stat cache semantics.

### F2.7 Tiny LeRobot Fixture

- File/symbol: `genesisvla/testing/fixtures/tiny.py:15-82`, `TinyLeRobotFixture`, `tiny_lerobot_fixture`.
- Behavioral defect: fixture is generated in memory and marked `lerobot-like-in-memory`; it is not a real minimum LeRobot file/directory format.
- Missing test: real minimum fixture load path, provenance check against on-disk layout, and adapter from real fixture to `RawSample`.
- Severity: P2.
- Responsible Owner: Data.
- Proposed task ID: `GVLA-M2-DATA-REAL-FIXTURE-007`.
- Blocks M3: NO if Manager explicitly accepts in-memory-only M2 fixtures; YES before M3 uses fixture evidence to claim real LeRobot compatibility.

### F2.8 Tiny Parquet Fixture

- File/symbol: `genesisvla/testing/fixtures/tiny.py:24-29`, `TinyParquetFixture`; `tiny.py:85-104`, `tiny_parquet_fixture`.
- Behavioral defect: fixture is a tuple of in-memory mappings and marked `parquet-like-in-memory`; no real Parquet file is created or read.
- Missing test: real minimal parquet load path and schema validation, or explicit Manager approval that parquet-like records are sufficient for M2.
- Severity: P2.
- Responsible Owner: Data.
- Proposed task ID: `GVLA-M2-DATA-REAL-FIXTURE-007`.
- Blocks M3: NO if M3 starts from in-memory `RawSample`; YES before claiming real Parquet dataset compatibility.

### F2.9 Legacy Dataloader Adapter

- File/symbol: `genesisvla/dataloader/legacy/__init__.py:46-71`, `LegacyDataloaderAdapter.to_raw_sample`; `genesisvla/core/compat/legacy_sample.py:50-103`, `from_legacy_dict`.
- Behavioral defect: main happy path and unsupported-field preservation are covered, but several adapter failure modes are not exercised. Adapter also overwrites legacy `robot_tag` with injected `robot_tag`, which is intentional injection but loses original robot tag provenance unless it was also in metadata.
- Missing test: metadata non-mapping, missing image/language, required modality mismatch, `state_dim` mismatch, original robot_tag preservation policy, and warning behavior for nested unsupported payloads.
- Severity: P2.
- Responsible Owner: Data.
- Proposed task ID: `GVLA-M2-DATA-LEGACY-ADAPTER-HARDEN-008`.
- Blocks M3: NO for M3 native RawSample input; YES if M3 plans to consume legacy dataloader payloads directly.

## Mandatory TDD Audit

| Required item | Status | Evidence / Gap |
| --- | --- | --- |
| Transform ordering | COVERED | `tests/dataloader/test_transform_registry.py::test_should_apply_transforms_in_order`. |
| Production serialization roundtrip | MISSING | Only a test-only `AppendMetadataStep` implements `serialize`; production transforms lack serialization methods/factories. P1. |
| Unknown transform failure | COVERED | `test_should_fail_on_unknown_transform`. |
| mean/std roundtrip | COVERED | `test_should_normalize_and_unnormalize_meanstd`. |
| min/max roundtrip | COVERED | `test_should_normalize_and_unnormalize_minmax`. |
| masked padding preservation | COVERED | `test_should_preserve_masked_padding_dims`; CPU E2E also checks valid/invalid action dims. |
| deterministic mixture sampling | PARTIAL | Same seed/epoch and different epoch covered; worker split covered by positions. Rank behavior is not modeled. |
| mixture weight behavior | COVERED | `test_should_respect_weights_within_tolerance`. |
| real fixture load path | MISSING | Fixtures are generated in-memory `*-like`; no real LeRobot or Parquet loader path. P2. |
| legacy adapter failure modes | PARTIAL | robot_tag injection, action_dim rejection, unsupported field preservation covered; other negative modes missing. P2. |

## Transforms And Action Semantics

- `TransformProtocol` is intentionally minimal and adequate for M2.
- `ComposeTransform` enforces input `RawSample`, per-step output `RawSample`, left-to-right ordering, and unknown-transform failure through `TransformRegistry`.
- Production transform reconstruction is incomplete because production transforms do not serialize themselves, and no canonical production registry maps shipped names/params to concrete objects.
- `ImageResize` and `ImageNormalize` implement explicit HWC/CHW branches, and `ImageAugment` is deterministic by fixed seed. Test evidence currently covers HWC only.
- `ActionModeTransform` covers `absolute/world`, `delta/previous_action`, and `relative/state` with explicit `state_to_action_indices`. Relative mode correctly avoids assuming `state[:action_dim]`.
- `first_step_policy="zero"` is not invertible for non-zero first absolute actions. This is the most important action-semantics gap for M3.

## Normalization, Batching, Statistics, And Mixture

- `StateActionNormalize` and `StateActionUnnormalize` roundtrip valid dimensions for mean/std and min/max; invalid/padded dimensions preserve original values.
- `FeatureStatistics` validates method, 1-D numeric stats, valid-mask shape, finite values, zero-variance policy, and names length.
- `DatasetStatistics` validates schema version, non-negative count, at least one feature family, metadata JSON safety, and checksum on load. Fingerprint mismatch rejection is covered.
- `save_statistics` uses same-directory temp file plus `os.replace`, so atomic replacement is covered. Full crash durability is not covered.
- `collate_raw_samples` remains a simple `dict[str, Any]` batch boundary. It does not expose `CollatedBatch`/`SampleSource`, does not normalize metadata `sample_source`, and does not enforce canonical action-mask shape `(B, H, A)`.
- `_collate_action_mask` stacks `metadata["action_mask"]` directly. Tiny fixtures provide `(A,)`, so the resulting mask shape is `(B, A)`, not canonical `(B, H, A)` for action element validity.
- Variable horizon/action dimension policy is implicit through `np.stack` failures rather than explicit validation/errors.
- `MixtureDataset` is deterministic by seed and epoch and splits workers by global position. It does not model rank/world-size, and sample metadata omits worker/rank fields even though the Wave 1 contract proposal called for source/provenance fields.

## Fixtures, Legacy, And E2E

- Tiny fixtures are generated, deterministic, CPU-only, and provenance-tagged as project-generated.
- The fixtures are not real minimum LeRobot or Parquet formats. They are `lerobot-like-in-memory` and `parquet-like-in-memory` by design.
- Legacy adapter injects a configured `robot_tag`, converts via M1 `from_legacy_dict`, validates optional action/state dims, warns on unsupported fields, and preserves unsupported fields in metadata.
- Silent field loss is partially addressed: unsupported fields are preserved, and `episode_id` is preserved by the core compat adapter. Known fields consumed by conversion are not retained as original raw values; original `robot_tag` can be overwritten by adapter injection without a dedicated provenance field.
- Structural sharing/copy cost: RawSample construction copies arrays to read-only; image resize/augment also copy image mappings. This is safe for M2 immutability but creates extra CPU copies that M3 should account for before large-batch training.
- CPU tiny E2E covers a minimum transform/config/cache/collate roundtrip, but it does not exercise production transform serialization or real fixture loading.

## Findings Summary

| ID | Severity | Area | Owner | Blocks M3 | Summary |
| --- | --- | --- | --- | --- | --- |
| D-AUDIT-P1-001 | P1 | Compose/production transform config | Data + Architecture review | YES | Production transforms cannot be serialized/reconstructed through the advertised config path. |
| D-AUDIT-P1-002 | P1 | ActionMode zero policy | Data + Architecture review | YES | `first_step_policy="zero"` loses non-zero first absolute action on roundtrip. |
| D-AUDIT-P1-003 | P1 | Collate/mask/source/mixture provenance | Data | YES | No typed batch contract, no canonical `(B,H,A)` mask expansion, no source/rank metadata contract. |
| D-AUDIT-P2-001 | P2 | Image CHW/augment coverage | Data | Conditional | CHW and augment edge cases are implemented but under-tested. |
| D-AUDIT-P2-002 | P2 | Statistics cache durability | Data + Quality | NO | Atomic replace exists; fsync/durability contract is absent. |
| D-AUDIT-P2-003 | P2 | Tiny real fixture formats | Data | Conditional | Fixtures are in-memory `*-like`; no real minimum LeRobot/Parquet load path. |
| D-AUDIT-P2-004 | P2 | Legacy adapter hardening | Data | Conditional | Additional negative modes and provenance policy need tests. |
| CONTEXT-Q-P1 | Context | Remote CI | Quality | Blocks completion, not this audit | PR remote `genesis-check` fails before local gate due missing wheelhouse/bootstrap exit 66. |

## Recommended Follow-Up Tasks

- `GVLA-M2-DATA-COMPOSE-SERIALIZATION-003`: add production transform specs/factories/serialization and tests for real transform reconstruction.
- `GVLA-M2-DATA-ACTIONMODE-ZERO-005`: define zero first-step invertibility semantics; either make it reversible with stored/reference first action, reject inverse use, or mark it lossy and exclude it from reversible pipelines.
- `GVLA-M2-DATA-BATCH-MASK-SOURCE-009`: implement typed batch/source contract, canonical `(B,H,A)` action mask expansion, explicit variable horizon/action-dim validation, and mixture worker/rank/source metadata.
- `GVLA-M2-DATA-IMAGE-COVERAGE-004`: add CHW and augment edge tests.
- `GVLA-M2-DATA-STATS-DURABILITY-006`: decide and document atomic-only vs fsync durability, then test the chosen contract.
- `GVLA-M2-DATA-REAL-FIXTURE-007`: either add real minimum LeRobot/Parquet fixture loaders or record Manager/user approval that in-memory `*-like` fixtures are sufficient for M2.
- `GVLA-M2-DATA-LEGACY-ADAPTER-HARDEN-008`: add legacy adapter negative/provenance tests.

## DevSpace MCP Compliance

PASS. This audit did not use DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, source/test/tooling edits, task-state edits, staging, commit, push, PR, merge, stash, reset, restore, clean, rm, new worktree, new environment, or M3 implementation.

## Subagent Retirement Ledger

No short-lived read-only subagents were spawned for this audit. D-RO2/D-RO3/D-RO4 were not used; the persistent Data Owner performed the read-only inspection directly, and no child context remains active.

## Parallelism Note

No write-capable subagent and no parallel write. This report is the only file written by Data in this Wave 5 audit.
