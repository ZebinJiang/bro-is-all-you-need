target_branch: dev/m2-transform-data-contract-v2
pwd: /home/cz-jzb/workspace/vla-flywheel
git_root: /home/cz-jzb/workspace/vla-flywheel
branch: dev/m2-transform-data-contract-v2
workspace_check: PASS

# GVLA-M2-PLANEXEC-002 Architecture Owner Plan

## Decision / Recommendation

Architecture recommends proceeding with M2 Tranche A on branch
`dev/m2-transform-data-contract-v2`, with Data Owner as the serial writer for
implementation and Architecture/Quality as read-only reviewers after execution.

The recommended public boundary is:

- Add `TransformProtocol` under `genesisvla/core/protocols/transform.py` and
  export it from `genesisvla/core/protocols/__init__.py`.
- Keep `ComposeTransform` and concrete transforms under
  `genesisvla/dataloader/transforms/`.
- Keep `DatasetStatistics` schema/cache under
  `genesisvla/dataloader/statistics/`.
- Do not modify M1 public contracts by default.

This planning report does not mark M1 or M2 complete. M1 publication remains
`BLOCKED_PR_TOOL_OR_AUTH` until the required publication/PR evidence exists.

## Files Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `coordination/tasks/active/GVLA-M2-PLANEXEC-002.yaml`
- `docs/genesisvla/rfc_000_architecture.md`
- `docs/genesisvla/coding_standard.md`
- `docs/genesisvla/testing_standard.md`
- `.agent-docs/feature_list.json`
- `genesisvla/core/types/__init__.py`
- `genesisvla/core/types/action.py`
- `genesisvla/core/types/framework.py`
- `genesisvla/core/types/sample.py`
- `genesisvla/core/protocols/__init__.py`
- `genesisvla/core/protocols/framework.py`
- `genesisvla/core/protocols/policy.py`
- `genesisvla/core/protocols/runner.py`
- `tests/core/test_action.py`
- `tests/core/test_framework_contract.py`
- `tests/core/test_protocol_contracts.py`
- `tests/core/test_raw_sample.py`
- `tests/core/test_registry.py`

## Proposed Package Layout

Recommended Tranche A layout:

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
```

Recommended tests:

```text
tests/
  core/
    test_transform_protocol.py
  dataloader/
    test_compose_transform.py
    test_state_action_normalize.py
    test_action_mode_transform.py
    test_dataset_statistics.py
```

Optional Tranche B additions, only after Tranche A review:

```text
genesisvla/
  dataloader/
    transforms/
      image.py
    datasets/
      __init__.py
      in_memory.py
```

Do not create a duplicate source tree, do not use a template-owned `src/`
layout, and do not touch the sibling worktree
`/home/cz-jzb/workspace/vla-flywheel-m2-planexec`.

## Public Contract Notes

`TransformProtocol` belongs in Core because it is the shared public interface
that Data, Model, and Runner layers may depend on. It should remain a plain
`typing.Protocol`, matching the existing `FrameworkProtocol`, `RunnerProtocol`,
and `PolicyProtocol` style. Do not add `runtime_checkable`, and do not rely on
runtime `isinstance` checks in tests.

Recommended minimal Tranche A protocol:

```python
class TransformProtocol(Protocol):
    def __call__(self, sample: RawSample) -> RawSample:
        ...
```

This keeps Tranche A per-sample and avoids premature batch/model-input
transform contracts. Batch-level transforms can be proposed later through a
separate Architecture-reviewed task if M2 evidence shows they are needed.

`ComposeTransform` should be a Data-layer implementation, not a Core contract.
It should compose `TransformProtocol` instances deterministically from left to
right. Architecture preference is that an empty composition is a documented
identity transform, because it supports config-driven pipelines without changing
M1 behavior.

Concrete transforms should preserve untouched fields on `RawSample`, return a
new `RawSample` when values change, and avoid hidden in-place mutation. Reusing
unchanged numpy arrays is acceptable to avoid unnecessary data movement, but
changed arrays must be newly produced and shape-validated.

`DatasetStatistics` belongs in `genesisvla/dataloader/statistics/`, not Core,
because statistics and cache lifecycle are Data-layer concerns. The schema
should be a versioned dataclass with explicit fields for action/state means and
standard deviations, sample count, and small metadata where needed. Cache IO
must require an explicit caller-provided project-local path and must not write
at import time.

## Tranche A Boundaries

Tranche A should include:

- `TransformProtocol` and export wiring.
- `ComposeTransform`.
- `StateActionNormalize`.
- `StateActionUnnormalize`.
- `ActionModeTransform` for `abs`, `delta`, and `relative`.
- `DatasetStatistics` schema.
- Explicit-path statistics cache load/save helpers.
- Focused unit and failure-mode tests under `tests/core` and `tests/dataloader`.
- M2 planning/task records allowed by the task card.

Tranche A must not include:

- Changes to M1 contracts: `RawSample`, `BatchSample`, `ModelInput`,
  `FrameworkOutput`, `ActionChunk`, `ActionMask`, `ActionSpace`,
  `FrameworkProtocol`, `RunnerProtocol`, or `PolicyProtocol`.
- Real LeRobot or Parquet adapters.
- Dataset downloads, dataset conversion, large fixtures, or committed runtime
  artifacts.
- Runtime caches in repo root, system `/tmp`, global user cache, or hidden tool
  directories.
- Heavy image dependencies.
- Slurm/runtime execution changes.
- M1 publication branch or publication gate changes.
- `.agent-docs/feature_list.json` pass-state changes.

## Tranche B Boundaries

Tranche B may proceed only after Tranche A is implemented, validated, and
reviewed. It may include:

- Simple image transforms without new heavy dependencies.
- A deterministic fake in-memory dataset or mixture sampler for contract tests.
- Additional tests proving transform composition across image/sample fields.

Tranche B should still avoid real dataset ingestion, external data movement,
large fixtures, streaming behavior, and completion-state changes.

## Tranche C Boundaries

Tranche C is plan-only in this task. It should capture follow-up scope for:

- Real LeRobot adapter.
- Real Parquet adapter.
- Large fixtures.
- Dataset conversion.
- Streaming dataset behavior.
- Dependency-heavy image backends.
- Wider dataset cache lifecycle and invalidation policy.

Any Tranche C execution requires a new task card and fresh Data, Architecture,
and Quality routing.

## Breaking-Change Risk

Breaking-change risk is manageable if Tranche A adds new M2 contracts without
modifying M1 contracts. Primary risks:

- Adapting `RawSample` or `BatchSample` to transform code instead of adapting
  transform code to the accepted M1 contracts.
- Introducing runtime Protocol semantics through `runtime_checkable` or
  `isinstance`.
- Leaving `ActionModeTransform` semantics implicit or policy-specific.
- Adding implicit cache paths that read/write root cache, `/tmp`, global user
  cache, or environment-derived paths.
- Mixing Tranche A public-contract work with Tranche B/C dataset or dependency
  scope.

Required mitigation:

- Treat M1 public contracts as read-only unless a separate breaking-change task
  is opened and Architecture-approved.
- Define action modes explicitly and cover them with tiny numeric fixtures:
  - `abs`: return actions unchanged.
  - `delta`: return consecutive row differences, preserving the first row as
    the initial command unless a later Architecture task approves a different
    convention.
  - `relative`: subtract the current state prefix matching `action_dim` from
    each action row; reject missing or too-short state.
- Raise clear `ValueError` for missing actions/state, shape mismatch, zero or
  invalid standard deviation, unsupported mode, and incompatible statistics.

## Required Architecture Review Criteria After Execution

Architecture follow-up review should verify:

- Workspace remains `/home/cz-jzb/workspace/vla-flywheel` on branch
  `dev/m2-transform-data-contract-v2`.
- No file in `/home/cz-jzb/workspace/vla-flywheel-m2-planexec` was touched.
- The M1 preservation stash was not applied, dropped, or popped.
- No M1 public contract files were behaviorally changed.
- `TransformProtocol` is a plain structural Protocol under Core.
- Concrete transforms are in `genesisvla/dataloader/transforms/`.
- Statistics schema/cache helpers are in `genesisvla/dataloader/statistics/`.
- Cache helpers use explicit project-local paths and avoid root cache, `/tmp`,
  global user cache, and global environment mutation.
- Compose order, identity behavior, normalization inverse behavior, action mode
  semantics, and failure cases are tested.
- Tests use explicit Protocol annotations, not runtime Protocol checks.
- No datasets, runs, checkpoints, generated caches, model weights, or runtime
  artifacts are staged. Existing `__pycache__` artifacts observed in core/test
  paths should not become publication or acceptance evidence.
- `Makefile`, root `pyrightconfig.genesisvla.json`, `pyproject.toml`,
  `.agent-docs/feature_list.json`, and M1 publication state are unchanged unless
  a separate authorized task allows them.
- Project-local quality wrapper and focused tests pass before review closure.

## DevSpace MCP Compliance

PASS. This Architecture planning review used local repository shell reads and
one allowed report write only. It did not use DevSpace MCP,
`vla-flywheel-devspace`, MCP connector tools, `open_workspace`, MCP read/write
/edit, or MCP bash. DevSpace MCP must not be cited as internal workflow evidence
for M2 execution, review, acceptance, or publication.

## Subagent Retirement Ledger

None used. No short-lived subagents were created for this read-only Architecture
planning review.

## Parallelism Proposal

Read-only planning and post-execution review may run in parallel across
Architecture and Quality because their write paths are separate reports.
Implementation writes for Tranche A should remain serial under Data Owner,
because the tranche touches shared transform/statistics contracts and tests. No
parallel writes are proposed.
