# GVLA-M2-MILESTONE-AUDIT-001 Training Consultation

## Conclusion

`REQUEST_CHANGES`

M2 is a coherent numpy-only transform/data layer and does not leak model-specific
tokenization, device transfer, runner, checkpoint, or distributed training
behavior into the data boundary. However, M3 training consumers should not enter
implementation against the current public API without addressing three P1
readiness gaps: no stable typed batch object, no transform execution context for
epoch/worker/rank/sample-position determinism, and no serializable data-pipeline
manifest sufficient for checkpoint reconstruction.

P0 count: 0

P1 count: 3

P2 count: 2

M3 readiness decision: `NOT_READY_FOR_M3_ENTRY_WITHOUT_M2_PUBLIC_API_HARDENING`

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required published head: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- Draft PR: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/2`
- PR head: `dev/feat-m2-transform-data-contract-v2-restacked` at `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- PR base: `dev/starvla-engineering-base` at `5e42b775f97d438ae58752f986284da9c4adf98b`
- local `origin/dev/starvla-engineering-base`: `5e42b775f97d438ae58752f986284da9c4adf98b`
- local branch `dev/starvla-engineering-base`: `c5c2e37885d7c67fa2fd59504c74ffa4509543e6`, stale relative to PR base; no sync was attempted.
- `git merge-base HEAD 5e42b775f97d438ae58752f986284da9c4adf98b`: `5e42b775f97d438ae58752f986284da9c4adf98b`
- PR/local diff against `origin/dev/starvla-engineering-base...HEAD`: 72 files changed, 6823 insertions, 33 deletions.

Initial `git status --short` before this report:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml
 M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml
 M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml
?? coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md
```

Remote CI readiness context from the required Quality report: PR #2 has recorded
`genesis-check` failures because the GitHub runner lacks committed/cached
wheelhouse distributions and `scripts/quality/bootstrap_project_local_tools.sh`
exits 66 with the instruction to run `--fill-wheelhouse`. This Training
consultation did not fix or attempt to fix remote CI.

## Governance Deviation Note

`DEVIATION_RECORDED`

During the first report write, the patch operation created
`/home/cz-jzb/workspace/vla-flywheel/coordination/reports/GVLA-M2-MILESTONE-AUDIT-001/owner-training-consult.md`
under the main checkout instead of the required canonical worktree path. I then
detected that the canonical worktree path did not contain the report and, before
receiving the Manager convergence/correction instruction, used `apply_patch` to
delete the mistaken main-checkout report file and add the report at the
canonical worktree path. Therefore the main-checkout stray report file was
already deleted before the correction instruction arrived.

After the correction instruction, no further cleanup, removal, deletion,
`rm`, `git restore`, `git reset`, `git clean`, stash, stage, commit, push, PR,
merge, source/test/tooling edit, or task-state edit was performed. This
correction only updates the canonical report with the deviation record.

## Required Inputs Read

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
- `coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`
- `docs/coordination/plans/GVLA-M2-PLAN.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- Relevant public core types and protocols:
  `genesisvla/core/types/action.py`,
  `genesisvla/core/types/sample.py`,
  `genesisvla/core/types/framework.py`,
  `genesisvla/core/protocols/transform.py`,
  `genesisvla/core/protocols/runner.py`,
  `genesisvla/core/protocols/policy.py`
- Relevant dataloader APIs:
  `genesisvla/dataloader/collate.py`,
  `genesisvla/dataloader/datasets/mixture.py`,
  `genesisvla/dataloader/transforms/*.py`,
  `genesisvla/dataloader/statistics/*.py`,
  `genesisvla/dataloader/legacy/__init__.py`
- Relevant M2 tests under `tests/dataloader/**`
- Current diff/stat/name-status against `origin/dev/starvla-engineering-base...HEAD`
  and the exact PR base SHA `5e42b775f97d438ae58752f986284da9c4adf98b...HEAD`.

## Findings

### P1-1 - M3 has no stable typed mini-batch contract to consume

- Area: `genesisvla/dataloader/collate.py`, public dataloader API.
- Evidence:
  - `collate_raw_samples()` returns a plain `dict[str, Any]` with keys
    `images`, `language`, `actions`, `state`, `robot_tag`, `action_mask`, and
    `metadata` at `genesisvla/dataloader/collate.py:51-66`.
  - `genesisvla/dataloader/__init__.py:1-5` exports only
    `collate_raw_samples`.
  - The CPU E2E test asserts dictionary shape directly at
    `tests/dataloader/test_cpu_tiny_e2e.py:57-73`.
- Why it matters for Training: M3 runners, checkpoint resume, model input
  adapters, and masked loss setup need a stable public object or protocol with
  documented shape semantics. A raw dictionary forces M3 to either depend on
  string keys and ad hoc `Any` values or redesign the M2 public API immediately.
- Fix direction: add an additive numpy-only typed batch/dataclass/protocol
  before M3, with explicit fields for images, language, actions, state,
  robot tags, masks, metadata, and provenance. Keep `collate_raw_samples()` as a
  compatibility helper if needed, but make the typed batch the Training-facing
  contract.

### P1-2 - Transform execution lacks epoch/worker/rank/sample context

- Area: transform protocol, image augment, mixture sampling.
- Evidence:
  - `TransformProtocol.__call__` accepts only `RawSample` and returns
    `RawSample` at `genesisvla/core/protocols/transform.py:10-14`.
  - `ImageAugment.__call__` creates a fresh RNG from the same seed on every
    sample at `genesisvla/dataloader/transforms/image.py:125-128`, so the
    augmentation decision is fixed per transform instance rather than derived
    from epoch/sample/worker/rank context.
  - `MixtureDataset.sample()` supports `epoch`, `worker_id`, and
    `worker_count` at `genesisvla/dataloader/datasets/mixture.py:49-80`, but
    it has no explicit rank field or shared transform context.
  - Tests cover same-seed/epoch determinism and worker position splitting in
    `tests/dataloader/test_mixture_dataset.py:39-80`, but there is no rank or
    transform-context test. Image augmentation tests only fixed-seed repeatability
    in `tests/dataloader/test_image_transforms.py:57-66`.
- Why it matters for Training: M3 distributed training will need deterministic
  resume and reproducible data order/augmentation across epoch, data-loader
  workers, and ranks. M3 can fold rank into a global worker id for the sampler,
  but transforms still have no public context path. Relying on mutable metadata
  conventions would be a hidden contract.
- Fix direction: add an immutable `TransformContext` or equivalent public
  execution context carrying epoch, rank, worker id/count, global sample
  position, and seed material. Make stochastic transforms derive RNG from that
  context. Add tests for multi-rank/global-worker determinism and resume from a
  recorded position.

### P1-3 - Checkpoint reconstruction cannot be derived from the public M2 state

- Area: transform serialization, statistics provenance, M3 checkpoint/resume.
- Evidence:
  - `ComposeTransform.serialize()` requires each step to implement
    `serialize()` at `genesisvla/dataloader/transforms/compose.py:129-140`.
  - Concrete production transforms such as `StateActionNormalize`,
    `StateActionUnnormalize`, `ActionModeTransform`, `ImageResize`,
    `ImageNormalize`, and `ImageAugment` do not expose public `serialize()`
    methods in their implementation files.
  - The CPU E2E test reconstructs the transform with registry lambdas that
    close over local `action_stats` and ignores most `TransformSpec.params`
    at `tests/dataloader/test_cpu_tiny_e2e.py:31-56`.
  - `DatasetStatistics` records `dataset_fingerprint`,
    `transform_fingerprint`, checksum, count, and feature statistics at
    `genesisvla/dataloader/statistics/schema.py:184-226`, but it is not a full
    training data-pipeline manifest.
- Why it matters for Training: M3 checkpoint resume must reconstruct the exact
  data pipeline, not just validate a statistics file. Without a serializable
  transform/stats/sampler manifest, checkpoints cannot reliably prove the
  action mode, normalization stats, image config, sampler seed, epoch, and
  position that produced a batch stream.
- Fix direction: add a public M2/M3 data-pipeline manifest tying
  `ComposeConfig`, concrete transform specs, statistics fingerprint/checksum,
  dataset fingerprint, sampler seed, epoch/position policy, and schema version.
  Add a checkpoint reconstruction test that round-trips this manifest without
  closures.

### P2-1 - Action mask semantics are split between dimension masks and horizon masks

- Area: action/mask shape documentation and batch contract.
- Evidence:
  - `ActionChunk.mask` must match full action value shape `(horizon, action_dim)`
    at `genesisvla/core/types/action.py:57-63`.
  - M2 dataloader examples use `metadata["action_mask"]` as a one-dimensional
    action-dimension mask in `tests/dataloader/test_state_action_normalization.py:15-26`.
  - `collate_raw_samples()` stacks `metadata.action_mask` without distinguishing
    dimension mask vs timestep mask at `genesisvla/dataloader/collate.py:40-48`.
- Why it matters for Training: M3 masked loss and checkpoint debugging need to
  know whether a mask applies to action dimensions, timesteps, or both. The
  current behavior is usable for M2 padding-dimension normalization, but it is
  ambiguous for training losses over action chunks.
- Fix direction: name masks explicitly in the typed batch contract, for example
  `action_dim_mask`, `action_timestep_mask`, or a documented broadcast rule.

### P2-2 - Sampler rank support is implicit rather than documented

- Area: `MixtureDataset.sample()` distributed semantics.
- Evidence:
  - The sampler records `position` and `epoch` in `sample_source` metadata at
    `genesisvla/dataloader/datasets/mixture.py:65-80`.
  - Tests verify two workers avoid duplicate positions at
    `tests/dataloader/test_mixture_dataset.py:71-80`.
  - There is no explicit rank field or documented global-worker mapping.
- Why it matters for Training: M3 can map `(rank, worker_id)` into one
  `worker_id`/`worker_count`, but this must be documented and tested or resume
  bugs will be hard to diagnose.
- Fix direction: document the global worker mapping or add rank-aware parameters
  as an additive API.

## Readiness Matrix

| Audit item | Decision | Notes |
| --- | --- | --- |
| typed batch suitability | `REQUEST_CHANGES` | Plain `dict[str, Any]` is too loose for M3 runner/checkpoint/model adapters. |
| action/state/mask shapes | `PARTIAL` | Action/state dimensions are validated, but mask semantics need explicit Training-facing names/broadcast rules. |
| transform/statistics provenance | `PARTIAL` | Fingerprints/checksums are good; full transform/sampler manifest is missing. |
| deterministic epoch/worker/rank control | `PARTIAL` | Mixture covers epoch/worker positions; rank and transform context are not public. |
| checkpoint reconstruction needs | `REQUEST_CHANGES` | No complete serializable data pipeline manifest. |
| device-neutral data boundary | `PASS` | Numpy-only transforms and explicit rejection of implicit device params. |
| no model-specific processing leakage | `PASS` | Transform spec rejects tokenizer/processor names and params; docs keep tokenization out of M2. |
| M3 immediate public API redesign risk | `YES` | M3 would need to harden M2 public API before safe Training implementation. |

## Positive Training-Relevant Evidence

- `RawSample` validates non-empty images/language/robot tags and 2-D actions.
- `ActionChunk` and `ActionSpace` enforce action shapes and finite values.
- State/action normalization preserves invalid/padding dimensions and handles
  zero-variance by explicit policy.
- Action mode transforms avoid implicit `state[:action_dim]` assumptions by
  requiring explicit state-to-action mappings.
- Statistics cache uses checksum validation and stale dataset/transform
  fingerprint rejection.
- `TransformSpec` rejects model-specific tokenization and implicit device
  transfer parameters.
- The M2 test matrix covers transform config, image transforms, normalization,
  action modes, statistics cache, tiny fixtures, mixture sampling, legacy
  adapter, and CPU tiny E2E.

## Validation And Runtime Evidence

No tests, CI, build, Slurm, network, package install, or environment creation
were run by this Training consultation. This was read-only. Local pass/fail
evidence was taken from
`coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality.md`; remote
CI remains a recorded `BLOCKED_TEST` due missing wheelhouse distributions and
bootstrap exit 66.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, PR mutation, push, merge, stage, stash, reset, restore,
clean, rm command, source/test/tooling/task-state edit, new worktree, or new
environment was used during this Training consultation.

Governance caveat: a mistaken main-checkout report file was created and deleted
via `apply_patch` before the Manager correction instruction, as recorded above.
No further cleanup/removal/deletion occurred after that instruction.

## Subagent Retirement Ledger

| Subagent | Type | Used | Reason | Output collected | Retired |
| --- | --- | --- | --- | --- | --- |
| T-RO1 | short-lived read-only Training reviewer | no | Direct Owner read-only consultation was small enough and had complete local evidence; no independent write-capable work was allowed. | n/a | n/a |
| write-capable subagent | any | no | Explicitly forbidden for this consultation. | n/a | n/a |

No live Training subagent context remains.

## Rollback Notes

The canonical report is the only retained intended write from the Training
consultation. A mistaken main-checkout report copy was created and already
deleted before the Manager correction instruction; this is recorded as a
governance deviation rather than hidden cleanup. Removing
`coordination/reports/GVLA-M2-MILESTONE-AUDIT-001/owner-training-consult.md`
from the canonical worktree reverts the retained consultation artifact. No
source, tests, tooling, task state, PR, branch, or remote state was changed by
this report.
