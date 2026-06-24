# GVLA-M2-DATA-HARDEN-002 Owner Quality Review

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- workspace_check: `PASS`
- `git status --short`: shows pre-existing Q-W1/A-W1/coordination dirtiness plus D-W1 dataloader, fixture, and test changes. No staging, commit, push, PR edit/create, merge, stash, reset, restore, clean, rm, or feature-list update was performed by Quality.

## Decision

`REQUEST_CHANGES`

Wave 3 should not proceed yet, even if Architecture also approves, until the static diagnostic hiding findings below are addressed or explicitly accepted by Manager with rationale.

## Reviewed evidence

- Task card: `coordination/tasks/active/GVLA-M2-DATA-HARDEN-002.yaml`
- Parent task card: `coordination/tasks/active/GVLA-M2-HARDEN-001.yaml`
- Dispatch: `coordination/reports/GVLA-M2-HARDEN-001/wave2-data-review-dispatch.md`
- Data report: `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data.md`
- Contract Architecture report: `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-architecture.md`
- Contract Quality review: `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-quality-review.md`
- Relevant diffs under:
  - `genesisvla/dataloader/**`
  - `genesisvla/testing/fixtures/**`
  - `tests/dataloader/**`
  - `docs/genesisvla/m2_transform_data_contract.md`

## Validation evidence assessment

Data-reported validation evidence is internally consistent and sufficient except for the static-hiding blocker:

- Focused post-implementation dataloader command: `PASS`, `65 passed`.
- Required `tests/dataloader`: `PASS`, `66 passed`.
- Required Pyright: `PASS`, `0 errors, 0 warnings, 0 informations`.
- Final `make genesis-check`: `PASS`; product pytest `158 passed`, product Black/Ruff/Pyright passed, governance pytest `21 passed`, governance Black/Ruff passed.
- Dispatch report independently repeats the required `66 passed`, Pyright clean, and final `make genesis-check` PASS evidence.

Quality did not rerun broad gates because the prompt requested lightweight read-only checks unless necessary and Data already recorded full gate PASS.

## Checks run by Quality

- `git diff --check`: `PASS`.
- `git diff --cached --name-only`: empty; no staged files.
- `git diff --cached --name-only -- datasets runs checkpoints code-input .ruff_cache`: empty; no staged forbidden runtime/artifact paths.
- Relevant diff name/status and stat reviewed for `genesisvla/dataloader/**`, `genesisvla/testing/fixtures/**`, `tests/dataloader/**`, and the M2 contract doc.
- Static hiding scan:
  - Command: `rg -n "type: ignore|pyright: ignore|# pyright|cast\\(Any" genesisvla/dataloader genesisvla/testing/fixtures tests/dataloader docs/genesisvla/m2_transform_data_contract.md`
  - Result: `FAIL` for this review focus; exact findings below.

## Findings / blockers

### P1: Static diagnostic hiding remains in Data D-W1 diff

The review focus explicitly required no static diagnostic hiding, blanket ignores, or test-only contract weakening. The D-W1 diff still contains targeted static bypasses:

- `tests/dataloader/test_image_transforms.py:124`: `# type: ignore[arg-type]`
- `tests/dataloader/test_action_mode_transform.py:89`: `cast(Any, "camera")`
- `genesisvla/dataloader/transforms/__init__.py:108`: `cast(Any, _string_param(...))`
- `genesisvla/dataloader/transforms/__init__.py:154`: `cast(Any, _string_param(...))`

The test cases appear intended to exercise runtime validation for invalid literal-like values, and the production casts appear to bridge JSON strings into typed constructors. That intent is understandable, but the current implementation still hides static diagnostics instead of using typed validation helpers or another explicit narrowing path. Because this was a named Quality review focus, this blocks approval.

## Test coverage assessment

The D-W1 test suite is otherwise meaningful and not merely smoke coverage:

- Production transform serialization/registry roundtrip: tests verify JSON-safe specs, fresh registry deserialization, and numerical-equivalent outputs.
- Image semantics: tests cover HWC resize/normalize, CHW flip axis, deterministic context-derived augmentation, invalid channel layout, and unsupported augment mode.
- ActionMode semantics: tests cover roundtrip behavior, invalid references/mappings, empty horizon rejection, zero first-step inverse failure without reference, and explicit reference restoration.
- Normalization/masks: tests cover mean/std and min/max roundtrip, padding-dimension preservation, zero-variance identity policy, dimension mismatch, and per-sample action-mask preservation.
- Collation: tests cover typed batch, canonical `[B,H,D]` masks, legacy `[D]` broadcast at collate boundary, variable horizon/action-dim padding, and legacy dict compatibility.
- Statistics/cache: tests cover stale fingerprints, checksum mismatch, atomic write via `os.replace`, fsync behavior, non-JSON metadata, array ownership/no aliasing, and read-only arrays.
- Mixture/fixtures/legacy: tests cover finite positive weights, unique dataset names, rank/worker deterministic split metadata, generated `real_format=false` fixtures, legacy unsupported-field preservation, required modality/state/action validation, and robot-tag provenance.

## Scope/protected-path assessment

- D-W1 changes are confined to the Data task surfaces: `genesisvla/dataloader/**`, `genesisvla/testing/fixtures/**`, `tests/dataloader/**`, `docs/genesisvla/m2_transform_data_contract.md`, and the Data Owner report.
- No staged `datasets/**`, `runs/**`, checkpoints, model weights, `code-input/**`, or `.ruff_cache/**` candidates were present.
- No model, training, deployment, acceleration, feature-list pass fields, PR/remote state, or git index changes were made by Quality.
- Pre-existing Q-W1 and A-W1 changes remain present and were not reverted.

## DevSpace MCP compliance

`PASS`. DevSpace MCP / `vla-flywheel-devspace` / MCP connector / `open_workspace` / MCP read/write/edit/bash were not used as workflow or evidence.

## Subagent retirement ledger

- Quality read-only review: performed directly in the persistent Quality Owner thread; retired: `yes`.
- Short-lived subagents: none used; no active subagent contexts remain.

## Parallelism note

- Quality review was read-only.
- No parallel write was used.
- No source, tests, docs, tooling, config, task state, git index, branch, remote, or PR state was modified by Quality.

## Recommendation

Return to Data for a narrow static-hiding cleanup in the same touched surfaces. Suggested direction: replace `cast(Any, ...)` and `# type: ignore[arg-type]` with explicit typed validation/narrowing helpers or tests that drive invalid runtime values through JSON/spec/factory boundaries without suppressing the type checker. After that, rerun the focused Data validation and allow Quality re-review.
