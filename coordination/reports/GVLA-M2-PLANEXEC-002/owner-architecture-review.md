target_branch: dev/m2-transform-data-contract-v2
pwd: /home/cz-jzb/workspace/vla-flywheel
git_root: /home/cz-jzb/workspace/vla-flywheel
branch: dev/m2-transform-data-contract-v2
workspace_check: PASS

# GVLA-M2-PLANEXEC-002 Architecture Review

## Architecture Decision

APPROVE

Architecture approves the Tranche A contract boundary as implemented. The new
public protocol is limited to `TransformProtocol` in `genesisvla/core/protocols`,
while concrete transforms and statistics/cache behavior live under
`genesisvla/dataloader`. No M1 public contract break was found.

This approval is Architecture-only. Quality still owns the final test/gate
decision, including the Data report's incomplete Black evidence and any wrapper
coverage gap for `tests/dataloader`.

## Files Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-PLANEXEC-002.yaml`
- `docs/coordination/plans/GVLA-M2-PLAN.md`
- `coordination/reports/GVLA-M2-PLANEXEC-002/owner-architecture-plan.md`
- `coordination/reports/GVLA-M2-PLANEXEC-002/owner-data-plan.md`
- `coordination/reports/GVLA-M2-PLANEXEC-002/owner-quality-plan.md`
- `coordination/reports/GVLA-M2-PLANEXEC-002/owner-data-execute.md`
- `docs/genesisvla/rfc_000_architecture.md`
- `docs/genesisvla/coding_standard.md`
- `docs/genesisvla/testing_standard.md`
- `genesisvla/core/protocols/transform.py`
- `genesisvla/core/protocols/__init__.py`
- `genesisvla/dataloader/__init__.py`
- `genesisvla/dataloader/transforms/__init__.py`
- `genesisvla/dataloader/transforms/compose.py`
- `genesisvla/dataloader/transforms/action_mode.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/dataloader/statistics/__init__.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/statistics/cache.py`
- `tests/dataloader/__init__.py`
- `tests/dataloader/test_transform_protocol.py`
- `tests/dataloader/test_compose_transform.py`
- `tests/dataloader/test_action_mode_transform.py`
- `tests/dataloader/test_state_action_normalize.py`
- `tests/dataloader/test_dataset_statistics.py`
- `docs/genesisvla/m2_transform_data_contract.md`

## Findings Ordered By Severity

No blocking Architecture findings.

Non-blocking residuals for Manager/Quality:

- The Data execute report records Black check as interrupted and not claimed as
  passing. This is a Quality gate item, not an Architecture contract blocker.
- The Data execute report records direct Pyright with zero errors and unresolved
  import warnings due to non-wrapper invocation. Quality should decide whether
  focused Pyright evidence is sufficient.
- `docs/genesisvla/m2_transform_data_contract.md` appears ignored by git status.
  If Manager expects this doc to be publication evidence, it must be explicitly
  handled before commit/publication.
- The task card still needs Manager reconciliation after execution/review; this
  Architecture review did not modify task state or completion state.

## Contract Boundary Assessment

PASS.

`TransformProtocol` is implemented as a plain structural `typing.Protocol` in
`genesisvla/core/protocols/transform.py`:

```python
def __call__(self, sample: RawSample) -> RawSample:
    ...
```

It is exported from `genesisvla/core/protocols/__init__.py`. Existing
`FrameworkProtocol`, `RunnerProtocol`, and `PolicyProtocol` implementations were
not changed. Tests use explicit protocol annotation and do not add
`runtime_checkable` or protocol `isinstance` semantics.

Concrete behavior is correctly placed in the Data layer:

- `ComposeTransform` in `genesisvla/dataloader/transforms/compose.py`
- `ActionModeTransform` in `genesisvla/dataloader/transforms/action_mode.py`
- `StateActionNormalize` and `StateActionUnnormalize` in
  `genesisvla/dataloader/transforms/state_action.py`
- `FeatureStatistics`, `DatasetStatistics`, `save_statistics`, and
  `load_statistics` in `genesisvla/dataloader/statistics/`

This matches the Manager M2 plan and the Architecture planning report.

## M1 Contract Break Assessment

PASS.

No behavioral changes were found in M1 public contract files:

- `genesisvla/core/types/**`
- `genesisvla/core/protocols/framework.py`
- `genesisvla/core/protocols/runner.py`
- `genesisvla/core/protocols/policy.py`
- `tests/core/**`
- `.agent-docs/feature_list.json`
- root `Makefile`, `pyrightconfig.genesisvla.json`, and `pyproject.toml`

The only change in existing Core protocol export surface is adding
`TransformProtocol` to `genesisvla/core/protocols/__init__.py`, which is the
intended M2 additive public contract and does not alter existing M1 semantics.

## Scope Creep Assessment

PASS.

No Tranche B/C implementation creep was found in the implemented source/test
files. The review found no real LeRobot adapter, Parquet adapter, large fixture,
dataset conversion, streaming dataset, dependency-heavy image backend, training
implementation, model implementation, deployment implementation, Slurm behavior,
robot endpoint behavior, or dataset write behavior.

The references to LeRobot, Parquet, streaming, `/tmp`, and DevSpace MCP are in
plans/reports/docs as out-of-scope or compliance notes, not implementation
dependencies.

## ComposeTransform Assessment

PASS.

`ComposeTransform` has a clear minimal public contract:

- stores transforms as a tuple;
- applies transforms left-to-right;
- treats empty composition as identity;
- rejects non-`RawSample` input;
- rejects non-`RawSample` step output with step context;
- propagates transform-specific exceptions without hiding the original failure.

This is sufficient for M2 Tranche A and does not require M1 contract changes.

## State/Action Statistics Assessment

PASS.

`StateActionNormalize` and `StateActionUnnormalize` use the planned formulas:

```text
normalized = (value - mean) / std
unnormalized = value * std + mean
```

The implementation validates state/action dimensionality against
`FeatureStatistics`, rejects missing required fields, allocates changed arrays,
and reuses untouched fields such as images and metadata. The tests cover
normalization, inverse roundtrip, missing field errors, zero std, shape
mismatch, and input non-mutation.

`DatasetStatistics` is suitable as the Tranche A schema/cache foundation. It is
versioned, requires positive `sample_count`, requires at least one of state or
action statistics, validates finite 1-D mean/std arrays, and rejects std values
below the epsilon threshold.

Recommendation: if future tranches make `metadata` a persisted public contract,
add explicit JSON-safe metadata validation. For Tranche A, cache serialization
failure on non-JSON metadata is a non-blocking residual risk.

## ActionModeTransform Assessment

PASS.

The implementation matches the agreed minimal semantics:

- `abs`: requires actions and returns the sample unchanged;
- `delta`: preserves the first row and computes adjacent row differences;
- `relative`: requires 1-D state, checks state length against `action_dim`, and
  subtracts `state[:action_dim]` from every action row.

It rejects unknown modes, missing actions, missing state for relative mode,
non-1-D state, and too-short state. It does not introduce robot-frame, gripper,
pose, control-rate, model, or policy semantics.

## DatasetStatistics Cache Assessment

PASS for Tranche A.

Cache helpers use JSON and require caller-provided paths. They do not infer
repository-root caches, global user caches, dataset roots, run roots, or system
`/tmp` defaults. Tests cover explicit `tmp_path` roundtrip, deterministic key
ordering, unsupported schema versions, invalid payloads, and non-finite stats.

Recommendation: future production cache callers should pass approved
project-local paths such as `datasets/cache/**` or run-local evidence paths, and
Quality should scan that no generated cache artifacts are staged.

## Public Contract Risks And Recommendations

- Keep `TransformProtocol` per-`RawSample` for Tranche A. Batch/model-input
  transforms should remain a future Architecture-reviewed extension.
- Keep action mode semantics numeric and minimal. Robot-frame and pose-specific
  interpretation should require a separate task.
- Keep statistics cache path ownership at the caller boundary. The helper is
  acceptable because it has no implicit cache path, but callers must not route
  persistent project evidence to system `/tmp`.
- Before acceptance/publication, Manager or Quality should reconcile ignored
  docs/report paths and make sure intended evidence is included intentionally.
- Before acceptance/publication, Quality should resolve the Black/Pyright/wrapper
  evidence gaps recorded by Data.

## DevSpace MCP Compliance

PASS. This Architecture review used local shell reads and this single allowed
report write only. It did not use DevSpace MCP, `vla-flywheel-devspace`, MCP
connector tools, `open_workspace`, MCP read/write/edit, or MCP bash. No
Architecture conclusion depends on DevSpace MCP evidence.

## Subagent Retirement Ledger

None used. No short-lived Architecture subagents were created for this read-only
review.

## Parallelism Note

No parallel writes were used. This review was read-only except for the allowed
Architecture review report. Architecture sees no need for parallel write work;
any implementation follow-up should remain serial under the assigned Owner
because the touched files share transform/statistics public contracts.
