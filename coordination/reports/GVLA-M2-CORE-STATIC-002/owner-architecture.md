# GVLA-M2-CORE-STATIC-002 Owner Architecture Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required_HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- workspace_check: `PASS`
- initial_status_short:
  - `M Makefile`
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M genesisvla/core/types/action.py`
  - `M pyproject.toml`
  - `M scripts/quality/bootstrap_project_local_tools.sh`
  - `M scripts/quality/genesis_check_project_local.sh`
  - `M tests/meta/test_repo_policy.py`
  - untracked M2 coordination/task/report/toolchain support paths

The pre-existing dirty state matched Wave 0/Wave 1 classification. A-W1 did not
stage, unstage, commit, push, merge, stash, reset, restore, clean, or remove
files.

## Conclusion

`BLOCKED_TEST`

A-W1 resolved the four current strict Pyright diagnostics: direct Pyright now
reports `0 errors, 0 warnings, 0 informations`, focused `tests/core` pass, and
the Data-visible `tests/dataloader/test_image_transforms.py` diagnostics
disappeared without editing dataloader files. However, the required
`make genesis-check` still exits non-zero because the out-of-scope governance
meta test rejects the current Manager-owned `blocking_gate:
GVLA-M2-CORE-STATIC-002` value in `coordination/PROGRAM_STATE.yaml`.

This remaining blocker is not in the A-W1 allowed write scope because this task
explicitly forbids modifying `coordination/PROGRAM_STATE.yaml`,
`coordination/TASK_INDEX.yaml`, and `tests/meta/test_repo_policy.py`.

## Files Changed

A-W1 changed:

- `genesisvla/core/types/action.py`
- `tests/core/test_action.py`
- `coordination/reports/GVLA-M2-CORE-STATIC-002/owner-architecture.md`

A-W1 did not modify:

- `genesisvla/core/types/sample.py`
- `docs/genesisvla/m2_transform_data_contract.md`
- `genesisvla/dataloader/**`
- `tests/dataloader/**`
- `Makefile`
- `pyproject.toml`
- `scripts/quality/**`
- `pyrightconfig.genesisvla.json`
- `tests/meta/**`
- `.agent-docs/feature_list.json`
- `coordination/PROGRAM_STATE.yaml`
- `coordination/TASK_INDEX.yaml`

## Exact Fix Summary By Diagnostic

### `genesisvla/core/types/sample.py:49:41`

Fixed by changing `ImageLike` from `NDArray[np.generic]` to the numeric image
domain:

```python
ImageLike: TypeAlias = NumericArray
```

This makes `RawSample.images` statically compatible with the existing
`_readonly_array(value: NumericArray) -> NumericArray` helper. Runtime RawSample
copy and read-only semantics are unchanged.

### `tests/core/test_action.py:81:18`

Fixed by keeping `ActionMask` bool-only and adding a narrow test-local helper:

```python
def _invalid_action_mask_for_runtime_probe() -> ActionMask:
    """构造静态契约外的掩码,仅用于验证运行时拒绝逻辑。"""
    invalid_mask: NDArray[np.float32] = np.ones((2, 7), dtype=np.float32)
    return cast(ActionMask, invalid_mask)
```

This preserves the public static contract while keeping the negative runtime
test for non-bool mask rejection. It uses no `Any`, no `cast(Any, ...)`, and no
ignore comments.

### `tests/dataloader/test_image_transforms.py:50:5`

Resolved by the core alias correction. No dataloader test or source edit was
needed.

### `tests/dataloader/test_image_transforms.py:51:9`

Resolved by the core alias correction. `ImageLike` is now numeric, so
`np.testing.assert_allclose` can accept `output.images["front"]` under strict
Pyright.

## Validation Commands And Results

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/core -q`: `PASS`
  - `35 passed in 0.25s`
- `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`:
  `PASS`
  - `0 errors, 0 warnings, 0 informations`
- `make genesis-check`: `FAIL`
  - product py_compile: `PASS`
  - product pytest: `PASS`, `131 passed`
  - product Black filelist: `PASS`
  - product Ruff: `PASS`
  - product Pyright: `PASS`, `0 errors, 0 warnings, 0 informations`
  - governance py_compile: `PASS`
  - governance pytest: `FAIL`, one failure in
    `tests/meta/test_repo_policy.py::test_should_have_codex_thread_team_control_plane`
  - failure cause: the test currently allows only `M1-T` or
    `GVLA-M2-TOOLENV-RECOVERY-001` for `blocking_gate`, but the Manager-owned
    current state has `blocking_gate: GVLA-M2-CORE-STATIC-002`.
  - governance Black: `PASS`
  - governance Ruff: `PASS`
- `git diff --check`: `PASS`
- `git status --short`: recorded after validation; shows A-W1 files plus
  pre-existing Quality/Manager dirty/untracked M2 state.

Suppression scan over `genesisvla/core/types/action.py` and
`tests/core/test_action.py` found no `type: ignore`, `pyright: ignore`,
`cast(Any, ...)`, or Pyright strictness downgrade.

## Direct Pyright Status

`PASS`

Direct strict Pyright is green with `0 errors, 0 warnings, 0 informations`.

## Whether Data D-W1 Is Still Needed

`NO`

Data D-W1 is not needed for the four diagnostics covered by this task. The two
Data-visible `tests/dataloader/test_image_transforms.py` diagnostics disappear
after the core `ImageLike` correction, and A-W1 did not edit
`genesisvla/dataloader/**` or `tests/dataloader/**`.

## Public Contract Compatibility / No M1 Behavior Break

Runtime behavior is preserved:

- `ActionChunk.values` remains numeric and read-only after copying.
- `ActionChunk.mask` remains bool-only for valid public static usage and still
  rejects non-bool masks at runtime.
- `RawSample` image/action/state copy and immutability behavior are unchanged.
- `ImageLike` is now a semantic numeric-image alias, matching current M1/M2
  image arrays (`uint8`, `float32`, normalized numeric arrays).

Static contract compatibility improves:

- `ImageLike`, `NumericArray`, and `RawSample` readonly conversion are coherent.
- `ActionMask` remains precise as `NDArray[np.bool_]`.
- Negative runtime testing is isolated to a local helper and does not widen the
  public constructor contract.

## Protected Path / No Scope Creep Check

`PASS`

A-W1 touched only the allowed core action type file, core action test, and this
report. It did not touch protected dataloader, model, training, deployment,
acceleration, datasets, code-input, feature-list passes, toolchain/config/meta
policy files, Manager state, or git index.

Current `git diff --name-status` also includes pre-existing modified files from
Quality/Manager state:

- `Makefile`
- `coordination/PROGRAM_STATE.yaml`
- `coordination/TASK_INDEX.yaml`
- `pyproject.toml`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `scripts/quality/genesis_check_project_local.sh`
- `tests/meta/test_repo_policy.py`

A-W1 did not modify those out-of-scope paths.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, new worktree, new Python environment, global pip, conda
base mutation, stage, unstage, commit, push, PR, merge, stash, reset, restore,
clean, rm, feature-list pass update, or completion-state update was used.

## Subagent Retirement Ledger

| Context | Role | Write scope | Output collected | Risks summarized | Retired |
| --- | --- | --- | --- | --- | --- |
| A-W1 | Architecture Owner direct canonical writer | `genesisvla/core/types/action.py`, `tests/core/test_action.py`, report/evidence paths | yes: diff, validation, this report | yes | yes |

No child subagent was used for A-W1. A-RO1 was not launched in this Owner thread;
Wave 1 diagnosis was performed directly and recorded at
`runs/tmp/GVLA-M2-INTEGRATE-AUDIT-001/architecture/core-static-plan.md`.

## Parallelism Note

Single canonical writer; no parallel write. Data and Quality did not write in
parallel with A-W1. Data should remain closed unless Manager opens a later step
for a different residual blocker; it is not needed for the four Pyright
diagnostics resolved here.
