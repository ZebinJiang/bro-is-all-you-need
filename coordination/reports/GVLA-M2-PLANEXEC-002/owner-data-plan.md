target_branch: dev/m2-transform-data-contract-v2
pwd: /home/cz-jzb/workspace/vla-flywheel
git_root: /home/cz-jzb/workspace/vla-flywheel
branch: dev/m2-transform-data-contract-v2
workspace_check: PASS

# GVLA-M2-PLANEXEC-002 Data Owner Plan

Owner: 30-OWNER · Data
Result: read-only planning report written. No source, test, feature-list, task-state, M1 publication gate, dataset, checkpoint, run-output, stash, sibling worktree, Owner-thread, or archive changes were made by this Owner stage.

## Scope Confirmation

- Task: `GVLA-M2-PLANEXEC-002 · Plan and execute M2 tranche A on a new branch`
- Worktree: `/home/cz-jzb/workspace/vla-flywheel`
- Branch: `dev/m2-transform-data-contract-v2`
- Active governance: `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- Task card state read: `status: blocked`, `conclusion: BLOCKED_OWNER_DISPATCH`
- Current delegation: read-only Data Owner planning report only
- M1 publication remains `BLOCKED_PR_TOOL_OR_AUTH`.
- M1 milestone is not marked complete.
- M2 milestone is not marked complete.

## Implementation Recommendation

Proceed with Tranche A only after Manager reopens or supersedes the blocked task card and dispatches a single write-capable Data Implementer for the approved source/test scope. This report is suitable as Data Owner planning input, but it is not implementation evidence and should not be treated as M2 acceptance.

Recommended Tranche A boundary:

1. Add a minimal per-sample `TransformProtocol` under `genesisvla/core/protocols/`.
2. Add concrete Data-layer transforms under `genesisvla/dataloader/transforms/`.
3. Add `DatasetStatistics` schema and explicit cache helpers under `genesisvla/dataloader/statistics/`.
4. Add focused unit tests under `tests/core` and `tests/dataloader`.
5. Keep M1 public contracts stable. Do not modify `RawSample`, `BatchSample`, `ModelInput`, `FrameworkOutput`, `ActionChunk`, `ActionMask`, `ActionSpace`, `FrameworkProtocol`, `RunnerProtocol`, or `PolicyProtocol` unless a separate Architecture-approved breaking-change task exists.

RawSample consumption chain:

```text
legacy dict or tiny fixture payload
  -> RawSample
  -> TransformProtocol implementation
  -> ComposeTransform
  -> transformed RawSample
  -> BatchSample
  -> ModelInput
```

Transforms should remain sample-to-sample. They should not emit batches, `ModelInput`, `ActionChunk`, framework outputs, tensors, datasets, or model-ready dicts in Tranche A.

## Tranche A Source/Test File Plan

Core protocol:

- Add `genesisvla/core/protocols/transform.py`
  - `TransformProtocol(Protocol)`
  - `__call__(self, sample: RawSample) -> RawSample`
- Update `genesisvla/core/protocols/__init__.py`
  - export `TransformProtocol`
  - keep the existing explicit protocol export style

Data package:

- Add `genesisvla/dataloader/__init__.py`
- Add `genesisvla/dataloader/transforms/__init__.py`
- Add `genesisvla/dataloader/transforms/compose.py`
  - `ComposeTransform`
- Add `genesisvla/dataloader/transforms/state_action.py`
  - `StateActionNormalize`
  - `StateActionUnnormalize`
- Add `genesisvla/dataloader/transforms/action_mode.py`
  - `ActionModeTransform`
  - accepted modes: `abs`, `delta`, `relative`
- Add `genesisvla/dataloader/statistics/__init__.py`
- Add `genesisvla/dataloader/statistics/schema.py`
  - `FeatureStatistics`
  - `DatasetStatistics`
- Add `genesisvla/dataloader/statistics/cache.py`
  - explicit-path save/load helpers

Focused tests:

- Add `tests/core/test_transform_protocol.py`
  - explicit structural annotation for `TransformProtocol`
  - no `runtime_checkable`
  - no runtime protocol `isinstance` check
- Add `tests/dataloader/__init__.py`
- Add `tests/dataloader/test_compose_transform.py`
  - left-to-right execution order
  - empty composition identity
  - clear failure when a step returns a non-`RawSample`
  - original sample remains unmutated
- Add `tests/dataloader/test_state_action_normalize.py`
  - state normalization
  - action normalization
  - unnormalize inverse within tolerance
  - missing arrays and invalid stats failures
- Add `tests/dataloader/test_action_mode_transform.py`
  - `abs` identity
  - `delta` first-row-preserved row difference
  - `relative` current-state-prefix subtraction
  - missing actions/state and dimension failures
- Add `tests/dataloader/test_dataset_statistics.py`
  - schema validation
  - explicit cache path roundtrip
  - zero, negative, non-finite, and shape-mismatched std rejections

Quality gate gap:

- Current `Makefile`, `pyrightconfig.genesisvla.json`, and `scripts/quality/genesis_check_project_local.sh` do not include `tests/dataloader`.
- This report does not authorize modifying those files.
- Manager/Quality should decide before acceptance whether to expand the gate in a separate Quality-scoped change or require focused commands such as:

```text
python -m pytest tests/core/test_transform_protocol.py tests/dataloader -v
python -m pyright genesisvla tests/dataloader
```

## Data Contract Notes And Edge Cases

Contract impact:

- `RawSample` remains the Data-layer transform input and output.
- Existing M1 validation stays authoritative: images must be non-empty, language and robot tag must be non-empty, actions are 2-D when present, and state is at least 1-D when present.
- `RawSample.actions` should be required only by action transforms and normalization paths that operate on actions.
- `RawSample.state` should be required only by state normalization and `relative` action mode.
- M2 should not add masks to `RawSample` in Tranche A. Existing `ActionMask` belongs to `ActionChunk`; raw action masks need a later contract decision.

Transform impact:

- `ComposeTransform` should store transforms as an immutable tuple.
- It should execute left-to-right with deterministic step order.
- Empty composition should be identity.
- Each step should receive the previous step's returned `RawSample`.
- A step returning a non-`RawSample` should raise a clear error with step index and transform identity.
- Transform-specific `ValueError` failures should retain their original cause; avoid broad catch-and-replace behavior that hides the underlying failure.

Fixture impact:

- Tranche A tests should use in-memory tiny fixtures only.
- Use the existing M1 shape idiom: a small `front` image, actions shaped `(2, 7)`, state shaped `(7,)`, robot tag such as `debug-arm`, and shallow metadata.
- No files under `datasets/**` should be read or written.
- No real LeRobot, Parquet, conversion, streaming, or large fixture behavior belongs in Tranche A.

Determinism notes:

- Transform behavior must not use global random state.
- Statistics cache serialization should use deterministic key ordering.
- Optional fake mixture sampling must use an explicit seed or deterministic schedule if Tranche B is approved.

Copy risk:

- Do not deep-copy `images` or `metadata` by default; M1 documents mappings as owned inputs and does not promise deep-copy isolation.
- Do not mutate input arrays in place.
- Reuse unchanged arrays for efficiency.
- Allocate new arrays for changed `state` and `actions`.
- Do not copy full datasets into runs or cache directories.

Rollback notes:

- Tranche A should be reversible by deleting the new `genesisvla/dataloader/**` package, `genesisvla/core/protocols/transform.py`, the `TransformProtocol` export, and focused tests.
- No dataset, checkpoint, run-output, Slurm, external-path, or stash cleanup should be required if implementation follows this plan.
- Do not touch or depend on `/home/cz-jzb/workspace/vla-flywheel-m2-planexec`.

## ComposeTransform Minimal Contract

Recommended contract:

```text
ComposeTransform(transforms: Iterable[TransformProtocol] = ())
__call__(sample: RawSample) -> RawSample
```

Required behavior:

- Accept zero or more transforms.
- Convert transforms to a tuple at construction.
- Execute in tuple order.
- Return the input sample unchanged for an empty tuple.
- Validate that the initial input is a `RawSample`.
- Validate every step output is a `RawSample`.
- Preserve field identity for untouched values when possible.
- Never write files, mutate environment variables, allocate devices, or infer dataset roots.

Failure behavior:

- `TypeError` or `ValueError` is acceptable for non-`RawSample` input/output as long as the message names the failing step.
- Unsupported transform objects should fail when invoked or during construction with a clear error.
- Do not catch `KeyboardInterrupt` or system-exit style exceptions.
- Do not turn every transform failure into a generic pipeline error that hides missing action/state/statistics details.

## Minimal Semantics For abs/delta/relative

`ActionModeTransform("abs")`:

- Requires `RawSample.actions` to be present.
- Leaves action values unchanged.
- May return the original sample unchanged to avoid copies.
- Does not normalize, clip, scale, or change `ActionSpace.normalized`.

`ActionModeTransform("delta")`:

- Requires `RawSample.actions` to be present and 2-D.
- Converts each row to a delta from the previous row.
- Recommended convention:

```text
out[0] = actions[0]
out[t] = actions[t] - actions[t - 1] for t > 0
```

- This preserves the first command as the initial absolute command and keeps tiny-fixture expectations readable.
- It should not infer control rate, robot frame, gripper semantics, pose representation, or policy-specific layout.

`ActionModeTransform("relative")`:

- Requires `RawSample.actions` and `RawSample.state`.
- Uses `action_dim = actions.shape[1]`.
- Minimal safe convention:

```text
base = state[:action_dim]
out = actions - base
```

- Reject missing state.
- Reject state shorter than `action_dim`.
- Reject ambiguous non-1-D state in Tranche A unless Architecture approves a convention for sequence state.
- It should not interpret quaternion, Euler, velocity, gripper, or coordinate-frame semantics.

Unsupported mode:

- Reject with `ValueError` that lists accepted modes: `abs`, `delta`, `relative`.
- Never silently pass through unknown modes.

## DatasetStatistics Schema/Cache Plan

Recommended schema:

```text
FeatureStatistics
  mean: 1-D numeric array
  std: 1-D numeric array
  names: tuple[str, ...] = ()

DatasetStatistics
  schema_version: "1.0"
  sample_count: positive int
  state: FeatureStatistics | None
  action: FeatureStatistics | None
  metadata: Mapping[str, JSON-safe scalar/list/dict] = {}
```

Validation:

- `sample_count > 0`
- at least one of `state` or `action` is present
- `mean` and `std` are 1-D arrays
- `mean.shape == std.shape`
- all mean/std values are finite
- every std value is greater than an explicit epsilon such as `1e-8`
- `names` length must not exceed the feature dimension

State/action normalization:

```text
normalized = (value - mean) / std
unnormalized = value * std + mean
```

Shape rules:

- 1-D state must match state statistic dimension.
- 2-D actions must match action statistic dimension on axis 1.
- Broadcasting should be explicit and tested.
- Missing stats for a requested field should fail clearly rather than silently no-op.

Cache rules:

- Cache helpers require an explicit caller-provided path.
- No import-time IO.
- No implicit repository-root cache.
- No global user cache.
- No system `/tmp` default.
- Prefer JSON for Tranche A because stats are small, inspectable, deterministic, and easy to scan.
- Serialize arrays to lists and restore numpy arrays on load.
- Include `schema_version` and reject unsupported versions.
- Use deterministic key ordering.
- If atomic write is implemented, create the temporary file in the same explicit parent directory and replace the target.

Allowed future cache destinations:

- `datasets/cache/**` for reusable derived statistics.
- `runs/local/<run_id>/**` or `runs/slurm/<run_id>/**` for run-local evidence.

Disallowed destinations:

- `datasets/readonly/**`
- repository root
- global home cache
- system `/tmp` by default
- sibling worktree paths

## Optional Tranche B Go/No-Go Criteria

Go only if all conditions hold:

- Tranche A implementation exists.
- Focused Tranche A tests pass.
- Architecture approves `TransformProtocol`, action-mode semantics, and statistics schema/cache boundary.
- Quality approves the focused test/gate coverage.
- No M1 public contracts were modified.
- No source/test work touched the M1 publication branch or stash.
- No dataset, checkpoint, run-output, Slurm, external-path, or sibling-worktree artifact was introduced.

Allowed Tranche B:

- Simple image transforms implemented with numpy only.
- Fake in-memory deterministic fixtures.
- Fake in-memory mixture sampling for contract tests.

No-go if any condition holds:

- Action mode semantics remain disputed.
- Statistics cache path policy remains unclear.
- The quality gate does not cover `tests/dataloader` or a focused substitute.
- Image transforms require PIL, OpenCV, TorchVision, torch, or another new dependency.
- Mixture sampling requires real datasets, generated dataset artifacts, external files, streaming IO, or large fixtures.

Fake fixture and mixture boundary:

- Use `Sequence[RawSample]` or another in-memory collection.
- Use explicit local seed or deterministic weighted round-robin.
- Never use global RNG.
- Preserve stable ordering for equal weights.
- Do not implement real LeRobot, Parquet, sharding, distributed sampling, streaming, or conversion in this task.

## DevSpace MCP Compliance

PASS. This Data Owner planning stage used local repository reads and this single allowed report write only. It did not use DevSpace MCP, `vla-flywheel-devspace`, MCP connector tools, `open_workspace`, MCP read/write/edit, or MCP bash. DevSpace MCP must not be cited as internal planning, execution, verification, review, acceptance, publication, or completion evidence for M2.

## Worker Coverage

- Explorer: skipped; Data Owner performed direct read-only planning from the task card and repository files.
- Implementer: skipped; this stage forbids source, test, feature-list, M1 publication gate, stash, and sibling-worktree changes.
- Reviewer: skipped in this Owner report; Architecture and Quality should review after execution or gate-scope decision.
- Tester: skipped; no implementation was produced, and no validation command is acceptance evidence for this plan-only stage.

## Subagent Retirement Ledger

No short-lived direct subagents were created.

| Role | Assigned scope | Output collected | Risks summarized | Retired |
| --- | --- | --- | --- | --- |
| Explorer | none | not applicable | not applicable | not applicable |
| Implementer | none | not applicable | not applicable | not applicable |
| Reviewer | none | not applicable | not applicable | not applicable |
| Tester | none | not applicable | not applicable | not applicable |

## Parallelism Proposal

Requested: no parallel writes.

Planning/review:

- Architecture and Quality may perform read-only planning or review in parallel because their report paths are disjoint and they do not modify source or shared contracts.

Implementation:

- Tranche A writes should remain serial under Data Owner.
- Exactly one write-capable Implementer should own all approved Tranche A source/test writes.
- Do not split `TransformProtocol`, `ComposeTransform`, normalization, action-mode transforms, statistics cache, and tests across multiple write workers in this task because the shared contract surface is small and conflict-prone.

Potential later split:

- If Manager wants parallel work after Tranche A, create separate task cards for disjoint scopes such as simple image transforms versus fake in-memory mixture tests.
- Each resulting task should keep one writer, have explicit writable paths, and receive Architecture/Quality review as needed.

## Required Follow-Up Approvals

- Architecture: approve protocol boundary, action-mode semantics, and statistics schema/cache.
- Quality: approve focused tests and decide how `tests/dataloader` enters the M2 quality evidence.
- Manager: unblock or supersede `GVLA-M2-PLANEXEC-002` before execution, because the current task card records `BLOCKED_OWNER_DISPATCH`.

## User Decision Required

None for this read-only Data Owner planning report.
