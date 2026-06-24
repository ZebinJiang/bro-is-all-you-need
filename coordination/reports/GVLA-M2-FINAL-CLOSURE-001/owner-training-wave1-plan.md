# GVLA-M2-FINAL-CLOSURE-001 Training Owner Wave 1 Plan

Owner: 20-OWNER Training
Wave: 1 parallel read-only planning / M3 consumer check
Decision: REQUEST_CHANGES
M3 consumer readiness: NOT READY until final M2 P1 findings are closed
Manager may proceed after Wave 1 synthesis: YES, to planned final-closure hardening only

## Workspace Verification

```text
pwd: /home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked
git_root: /home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked
branch: dev/feat-m2-transform-data-contract-v2-restacked
HEAD: 53449a8e3d667998f8ffd0c5e09aa0e2947de29f
git status --short:
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
 M coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml
 M coordination/tasks/active/GVLA-M2-HARDEN-001.yaml
 M coordination/tasks/active/GVLA-M2-PR2-VERIFY-003.yaml
 M coordination/tasks/active/GVLA-M2-REMOTE-CI-003.yaml
 M coordination/tasks/active/GVLA-M2-REMOTE-CI-004.yaml
?? coordination/reports/GVLA-M2-FINAL-CLOSURE-001/
?? coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md
?? coordination/reports/GVLA-M2-HARDEN-001/owner-architecture-wave5-final-review.md
?? coordination/reports/GVLA-M2-HARDEN-001/owner-data-wave5-final-review.md
?? coordination/reports/GVLA-M2-HARDEN-001/owner-model-wave5-final-review.md
?? coordination/reports/GVLA-M2-HARDEN-001/owner-quality-wave5-final-review.md
?? coordination/reports/GVLA-M2-HARDEN-001/owner-training-wave5-final-review.md
?? coordination/reports/GVLA-M2-HARDEN-001/wave4b-remote-ci-004-dispatch.md
?? coordination/reports/GVLA-M2-HARDEN-001/wave5-final-review-dispatch.md
?? coordination/reports/GVLA-M2-REMOTE-CI-004/
?? coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml
?? coordination/tasks/active/GVLA-M2-FINAL-DATA-001.yaml
?? coordination/tasks/active/GVLA-M2-FINAL-PUBLISH-001.yaml
?? coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml
```

Verification result: PASS. The worktree, branch, and HEAD match the required canonical review target. Existing dirty state is governance evidence already noted by Manager preflight. Training made no source/test/tooling/workflow/task-state/git-index/PR edits.

## Reports Written

- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/training/m3-readiness-plan.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-training-wave1-plan.md`

No other writes were performed by Training.

## Reviewed Evidence

- `coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- `coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave0-manager-preflight.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave1-dispatch.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `genesisvla/core/types/sample.py`
- `genesisvla/core/compat/legacy_sample.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/action_mode.py`
- `genesisvla/dataloader/datasets/mixture.py`
- `genesisvla/dataloader/legacy/__init__.py`
- `genesisvla/testing/fixtures/tiny.py`
- focused `tests/dataloader/**` files for fixtures, collate, statistics, transforms, mixture determinism, e2e, and legacy adapter coverage.

## M3 Consumer Requirements

P0:

- Final M2 must provide generated actual LeRobot-format and Parquet-format fixture evidence with `real_format=true`, deterministic reload, schema validation, malformed-file failures, and RawSample adaptation.
- M3 must consume a stable shape contract: `RawSample.actions=[H,D]`, `CollatedBatch.actions=[B,H,D]`, `CollatedBatch.action_mask=[B,H,D]`, plus `action_horizon` and `action_dim` for padded batches.
- Bool masks must be strict before Training uses them for loss masking. Silent truthy coercion in action masks or statistics masks is M3-blocking.
- Dataset/statistics provenance must validate dataset fingerprint, transform fingerprint, schema, count, feature stats, metadata, and checksum before training starts.
- M3 checkpoint/resume must persist the M2 data-pipeline primitives it consumes: transform config/fingerprint, statistics payload/path/checksum, dataset fingerprint, fixture/dataset format provenance, sampler seed/epoch/worker/rank/world fields, global position or consumed-sample cursor, and batch shape policy.

P1:

- Final tests should cover deterministic real-file reload and negative/malformed paths for both fixture formats.
- Final tests should cover non-bool mask rejection in collate, state/action normalization, and statistics.
- Final tests should cover strict statistics invariants: negative std, `maximum < minimum`, empty/duplicate names, non-finite values, and valid-mask typing.
- Final tests should confirm real-file fixtures remain CPU/local and do not introduce M3 training, model-specific processing, device transfer, or Slurm behavior.

P2:

- Make image modality key handling deterministic independent of insertion order.
- Reject invalid image normalization stats beyond zero std.
- Explicitly reject multidimensional/temporal state in relative action mode for the M2 contract, unless Architecture deliberately changes the state representation contract.
- Add M3 follow-up checks for framework tensor conversion cost and avoidable CPU/device copies.

## Blocking Risks

- `F2_FINAL_001` and `F2_FINAL_002` are M3-blocking: current tiny fixtures are in-memory and record `real_format=false`; user explicitly rejected accepting that scope reduction.
- `F2_FINAL_004` is M3-blocking: action masks are currently converted via `np.asarray(..., dtype=np.bool_)`, which can silently coerce invalid mask inputs.
- `F2_FINAL_007` is M3-blocking: statistics currently permit incomplete invariants including negative std, invalid ranges, and non-strict valid-mask coercion.
- M2 must not be treated as accepted M3 input until exact-SHA local and remote gates pass after these final fixes and publication.

## Non-Blocking Risks

- `F2_FINAL_003`, `F2_FINAL_005`, and `F2_FINAL_006` should still be fixed in final closure, but Training treats them as M3-readiness hardening rather than immediate public API redesign blockers if the fixes remain validation-tightening.
- Final fixture files must remain generated test artifacts and must not be committed as binary data or wheel payloads.
- M3 still needs its own checkpoint manager and training consumer tests; those are M3 responsibilities and should not be implemented in M2 final closure.

## API Redesign Assessment

Training does not see a need for M3 API redesign if final closure fixes remain scoped to real-format fixture evidence and stricter invariant validation. `RawSample`, `CollatedBatch`, `TransformSpec`, `ComposeConfig`, `TransformContext`, `DatasetStatistics`, and deterministic mixture provenance are adequate M3 planning primitives.

The one watchpoint is state representation: supporting temporal or multidimensional state in M2 relative action mode would require a clearer M3-facing state contract. Training recommends explicit rejection for M2 final closure.

## DevSpace MCP Compliance

PASS. Training did not use DevSpace MCP, `vla-flywheel-devspace`, MCP connectors, `open_workspace`, MCP read/write/edit/bash, or DevSpace-derived evidence. Local shell/git inspection and the permitted report writes were used.

## Subagent Ledger

- T-RO1 used: yes.
- Agent id: `019ef7dc-d480-7f71-8857-15b6285bd4e5`.
- Role: read-only Training planning subagent.
- Output: compact M3 readiness memo with `REQUEST_CHANGES` recommendation.
- Wrote files: no.
- Closed/retired by Owner: yes.
- Write-capable subagents used: no.

## Wave 1 Decision

REQUEST_CHANGES. Training supports Manager Wave 1 synthesis and the planned final-closure hardening sequence, but M3 consumer readiness cannot pass until the open P1 final findings close and are verified at exact PR head. Manager may proceed after Wave 1 synthesis; Manager must not mark M2 complete or start M3 from the current state.
