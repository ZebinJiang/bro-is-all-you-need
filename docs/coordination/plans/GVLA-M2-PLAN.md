# GVLA-M2-PLAN · Transform Pipeline + Data Contract

## M2 Objective

M2 establishes the first GenesisVLA data/transform contract on branch
`dev/m2-transform-data-contract-v2`, based on commit
`eef5efbc85c38e4b81150d71af59810ae5ab90ee`. It introduces a small,
typed transform pipeline around accepted M1 sample contracts without changing
M1 public behavior.

This plan is intentionally branch-local. M1 publication remains blocked by
`GVLA-M1-PUBLISH-001B = BLOCKED_PR_TOOL_OR_AUTH`; M1 is not complete and M2 is
not complete.

## Non-Goals

- Do not modify M1 public contracts.
- Do not mark M1 or M2 milestone passes true.
- Do not create PRs while GitHub auth remains blocked.
- Do not touch `/home/cz-jzb/workspace/vla-flywheel-m2-planexec`.
- Do not apply, drop, or pop the M1 preservation stash.
- Do not write `datasets/**`, checkpoints, model weights, large fixtures, or
  runtime artifacts.
- Do not implement real LeRobot, Parquet, streaming, conversion, or
  dependency-heavy image backends in this task.
- Do not use DevSpace MCP as project-internal execution evidence.

## Proposed Package Layout

```text
genesisvla/
  core/
    protocols/
      transform.py
      __init__.py
  dataloader/
    __init__.py
    transforms/
      __init__.py
      compose.py
      state_action.py
      action_mode.py
    statistics/
      __init__.py
      schema.py
      cache.py
tests/
  core/
    test_transform_protocol.py
  dataloader/
    __init__.py
    test_compose_transform.py
    test_state_action_normalize.py
    test_action_mode_transform.py
    test_dataset_statistics.py
```

Optional Tranche B may later add `genesisvla/dataloader/transforms/image.py`
and fake in-memory dataset utilities only if Tranche A gates pass and no new
dependency or fixture ambiguity remains.

## Public Contract Draft

`TransformProtocol` belongs in `genesisvla/core/protocols/transform.py` because
it is the shared structural interface that Data, Model, and Runner layers may
consume. It should be a plain `typing.Protocol`:

```python
class TransformProtocol(Protocol):
    def __call__(self, sample: RawSample) -> RawSample:
        ...
```

Concrete transforms belong in `genesisvla/dataloader/transforms/**`.
`ComposeTransform` executes `TransformProtocol` instances left-to-right, stores
them immutably as a tuple, treats an empty sequence as identity, and rejects
non-`RawSample` inputs or outputs with clear errors.

State/action normalization uses `DatasetStatistics` from
`genesisvla/dataloader/statistics/**`. Statistics cache helpers require
explicit caller-provided paths and must not infer repo root cache paths, system
`/tmp`, user caches, or global environments.

Action modes are intentionally minimal:

- `abs`: requires actions and leaves values unchanged.
- `delta`: requires 2-D actions; preserves `out[0] = actions[0]` and computes
  `out[t] = actions[t] - actions[t - 1]`.
- `relative`: requires actions and 1-D state; subtracts `state[:action_dim]`
  from each action row and rejects state shorter than the action dimension.

## Tranche A Execution Plan

Tranche A is mandatory for this task:

1. Add `TransformProtocol` and export wiring.
2. Add `ComposeTransform`.
3. Add `StateActionNormalize` and `StateActionUnnormalize`.
4. Add `ActionModeTransform` for `abs`, `delta`, and `relative`.
5. Add `FeatureStatistics`, `DatasetStatistics`, and explicit cache helpers.
6. Add focused tests for all implemented public contracts and failure modes.
7. Add this plan and backlog task cards.

Implementation writes are serial under Data Owner. Architecture and Quality
review only after Data writes complete.

## Tranche B Execution Plan

Tranche B is optional and should not execute unless Tranche A passes, review
approves, and Owner judgment finds no ambiguity:

- Simple image transforms without heavy dependencies.
- Fake in-memory deterministic mixture sampling using tiny sample lists.

If image resize semantics, dtype behavior, RNG handling, or sampling semantics
are ambiguous, Tranche B remains backlog-only.

## Tranche C Plan-Only Scope

Tranche C remains plan-only in `GVLA-M2-PLANEXEC-002`:

- Real LeRobot adapter.
- Real Parquet adapter.
- Large fixtures.
- Dataset conversion.
- Streaming dataset.
- Dependency-heavy image backend.
- Legacy dataloader adapter implementation.

Any Tranche C implementation requires a new task card, fresh Owner routing, and
fixture/dependency/storage policy approval.

## TDD Matrix

| Area | Tests | Acceptance |
| --- | --- | --- |
| TransformProtocol | explicit structural annotation and simple call | no runtime `isinstance` on Protocol |
| ComposeTransform | order, empty identity, invalid step output, failure propagation | deterministic left-to-right behavior |
| StateActionNormalize | state/action normalization, missing fields, invalid std/shape | new arrays for changed values, no input mutation |
| StateActionUnnormalize | inverse roundtrip | values match original within tolerance |
| ActionModeTransform | abs, delta, relative, unknown mode, dimension failures | minimal documented semantics only |
| DatasetStatistics | schema validation and cache roundtrip via `tmp_path` | explicit paths, deterministic JSON, malformed payload rejection |

Focused validation must include `tests/dataloader` even if the existing project
wrapper has not yet been widened to include it.

## Owner Routing

- Architecture Owner `019eeea4-ddc6-7552-a673-728207c5a1e5`: read-only
  planning and post-execution contract review.
- Data Owner `019eeea5-4fbe-7332-b7d2-3c6fa65128c2`: primary serial writer
  for Tranche A implementation and execution report.
- Quality Owner `019eeea5-b5e8-71a1-b0a0-fe7ae4a9e147`: read-only planning,
  focused validation, wrapper review, artifact scans, and gate report.

No new Owner threads should be created or archived. Short-lived subagents, if
used inside an Owner thread, must be listed and retired by that Owner.

## Risk Matrix

| Risk | Mitigation |
| --- | --- |
| M1 contract drift | Treat M1 core sample/action/framework contracts as read-only. |
| Wrapper gap for `tests/dataloader` | Require focused dataloader pytest and Pyright evidence; widen gate only through approved scope. |
| Hidden cache/artifact writes | Cache helpers require explicit paths; tests use `tmp_path`; scans block `datasets/**`, `runs/**`, checkpoints, and large artifacts. |
| Action mode over-specification | Keep semantics numeric and minimal; defer robot-frame/gripper/pose interpretation. |
| DevSpace MCP dependency | Reports and evidence must state no internal DevSpace MCP use. |
| M1 publication confusion | Keep active M1 blocker recorded; do not mark M1 complete. |

## Stop Conditions

Stop with `BLOCKED_TEST` if focused tests or wrapper fail.
Stop with `BLOCKED_REVIEW` if Architecture or Quality rejects the implementation.
Stop with `FAIL` if DevSpace MCP is introduced as internal workflow dependency,
if protected paths are modified, or if M1/M2 completion state is falsified.
Stop with `PASS_LOCAL_READY_FOR_USER_REVIEW` if local commit exists but push
fails. Stop with `PASS_BRANCH_READY_FOR_USER_REVIEW` if commit and push both
succeed.

## M1 Publication Dependency Note

M2 work is isolated on `dev/m2-transform-data-contract-v2`, but M1 remains the
active unfinished milestone because `GVLA-M1-PUBLISH-001B` is still blocked on
PR tooling/auth. This task must not change the M1 publication gate, milestone
completion state, or preservation stash.

## Branch Isolation Note

This plan lives on `dev/m2-transform-data-contract-v2` in the current checkout.
It is not on the M1 publication branch and does not use the failed sibling
worktree path from `GVLA-M2-PLANEXEC-001`.
