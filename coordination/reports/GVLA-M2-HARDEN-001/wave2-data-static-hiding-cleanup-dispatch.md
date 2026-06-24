# GVLA-M2-HARDEN-001 Wave 2 Data Static-Hiding Cleanup Dispatch

## Trigger

- Child task: `GVLA-M2-DATA-HARDEN-002`
- Data report: `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data.md`
- Architecture review: `APPROVE`
- Quality review: `REQUEST_CHANGES`

Quality found remaining static diagnostic hiding in D-W1 diff. Wave 3 must not proceed until this is fixed or explicitly accepted by Manager with rationale.

## Blocking Finding

The D-W1 diff contains static type bypasses in Data-owned transform/test surfaces:

- `tests/dataloader/test_action_mode_transform.py`: `cast(Any, ...)`
- `tests/dataloader/test_image_transforms.py`: `# type: ignore[arg-type]`
- `genesisvla/dataloader/transforms/__init__.py`: production factory `cast(Any, ...)`

Manager readback confirmed those findings. The cleanup should remove static-hiding patterns rather than blanket-ignore them.

## Dispatch Decision

Route a narrow cleanup back to `30-OWNER · Data` as the sole writer.

Allowed write scope:

- `genesisvla/dataloader/transforms/__init__.py`
- `tests/dataloader/test_action_mode_transform.py`
- `tests/dataloader/test_image_transforms.py`
- `coordination/reports/GVLA-M2-DATA-HARDEN-002/**`

Expected report:

- `coordination/reports/GVLA-M2-DATA-HARDEN-002/owner-data-static-cleanup.md`

## Required Validation

- Static-hiding scan over relevant D-W1 surfaces must be clean for `type: ignore`, `pyright: ignore`, `# pyright`, and `cast(Any`.
- Focused tests covering changed files must pass.
- Pyright must pass.
- `make genesis-check` must pass.
- `git diff --check` must pass.

## Constraints

- No DevSpace MCP.
- No stage, commit, push, PR update, merge, stash, reset, restore, clean, rm, or deletion.
- No new worktree or environment.
- No protected-path edits.
- No M2 completion or M3 start.

## Parent State

- Parent remains `BLOCKED_TEST`.
- `request_changes` remains true.
- Wave 3 remains blocked pending Data cleanup and Quality re-review.
