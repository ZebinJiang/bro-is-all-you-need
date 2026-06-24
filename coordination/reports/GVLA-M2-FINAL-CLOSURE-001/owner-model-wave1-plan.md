# GVLA-M2-FINAL-CLOSURE-001 Owner Model Wave 1 Plan

Owner: 40-OWNER Model
Wave: 1 parallel read-only planning / M4 consumer check
Decision: REQUEST_CHANGES
Manager final synthesis may proceed after Wave 1: yes, for dispatching the planned final hardening work only. Do not mark M2 complete or start M3/M4 from the current head.

## Workspace Verification

Verification was run first in the canonical worktree before report writes.

```text
pwd
/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked

git rev-parse --show-toplevel
/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked

git branch --show-current
dev/feat-m2-transform-data-contract-v2-restacked

git rev-parse HEAD
53449a8e3d667998f8ffd0c5e09aa0e2947de29f

git status --short
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

Verification result: PASS. The root, branch, and HEAD match the dispatch. Existing dirty/untracked coordination state was preserved. Model Owner writes were limited to the two allowed output files, plus creating the missing parent directory for the allowed `runs/tmp/.../model` output.

## Reviewed Evidence

- `coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- `coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/dataloader/transforms/action_mode.py`
- `genesisvla/testing/fixtures/tiny.py`
- `tests/dataloader/test_collate.py`
- `tests/dataloader/test_state_action_normalization.py`
- `tests/dataloader/test_action_mode_transform.py`
- `tests/dataloader/test_image_transforms.py`
- `tests/dataloader/test_dataset_statistics.py`
- M-RO1 read-only planning result

## M4 Consumer Risks

P0 count: 0

P1 count: 3

- Strict action mask typing is required before M4 masked loss can trust `action_mask`. Current reviewed surfaces silently coerce masks in collate, state/action normalization, and direct `CollatedBatch` construction.
- Strict action statistics validation is required before normalized action decode can be treated as safe for model-output validation. Invalid std/ranges/masks/names can corrupt decode or bind loss dimensions incorrectly.
- Real-format Parquet and LeRobot fixture evidence is required before downstream training/data planning can claim real file-format coverage. This is Data-owned but still affects model-consumer confidence in provenance and adapter output.

P2 count: 4

- Image collation should be deterministic for matching modality key sets independent of insertion order.
- Image normalization should reject negative and non-finite values, not only zero std.
- Relative action mode should reject multidimensional/temporal state under the minimal M2 one-dimensional state policy.
- Direct padded `CollatedBatch(..., action_mask=None)` should be documented or guarded so future model code does not accidentally mark padded regions true outside the collator path.

## Compatibility Decision

M4 consumer readiness can be achieved by the planned M2 final hardening. No M2 API redesign is required if the fixes preserve these invariants:

- `RawSample.actions` remains `[H,D]`.
- `CollatedBatch.actions` remains `[B,H,D]`.
- `CollatedBatch.action_mask` remains strict bool `[B,H,D]`.
- False mask entries remain authoritative for padded horizon, padded action dimension, and invalid target elements.
- Legacy `[D]` masks are accepted only at the collate boundary, only as bool input, and only by broadcast to `[H,D]`.
- Normalization and unnormalization preserve masked false elements and expose enough transform/statistics/action-mode provenance for decode validation.

Current head should receive REQUEST_CHANGES because P1 model-facing safety gaps remain open. The requested final fixes are compatible with later action heads and masked loss when implemented as validation tightening and fixture/provenance evidence, not as shape or field renames.

## Expected Final Hardening Acceptance

- Non-bool masks are rejected before conversion in collate, state/action normalization, and `CollatedBatch`.
- Variable horizon/action-dim padding continues to produce false masks for padded regions.
- Valid normalized action entries can be decoded with recorded transform/statistics/action-mode provenance.
- Real-format Parquet and LeRobot fixtures parse generated file/dir formats into `RawSample` and record provenance without committing generated binaries.
- M2 docs and tests lock the canonical action/mask semantics for future M4 consumers.
- No model implementation, model weights, checkpoints, acceleration, deployment, training, M3, or M4 code is added.

## DevSpace MCP Compliance

Compliant. No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, or DevSpace-derived evidence was used.

## Subagent Ledger

- M-RO1 used: yes
- Agent id: `019ef7df-60e5-7a22-86d0-00f48d608788`
- Role: short-lived read-only model-consumer planning check
- Result: REQUEST_CHANGES, no M2 API redesign needed
- Writes by subagent: none
- DevSpace/MCP by subagent: none reported
- Retired: yes

## File Write Scope

Allowed outputs written:

- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/model/m4-readiness-plan.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-model-wave1-plan.md`

No source, tests, dependencies, workflows, PR body, git index, feature_list, task state, or M3/M4 code was modified by Model Owner.
