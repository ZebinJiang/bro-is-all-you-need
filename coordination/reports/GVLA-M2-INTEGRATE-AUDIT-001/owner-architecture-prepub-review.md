# GVLA-M2-INTEGRATE-AUDIT-001 Architecture Pre-Publication Review

## Conclusion

`APPROVE`

Architecture approves proceeding to Wave 4 publication from the Architecture
perspective. The core public-contract fix is coherent, direct strict Pyright is
clean, and the Quality gate-alignment report records green local gates after the
meta-policy update. Wave 4 should still remain Quality-owned with explicit
pathspec staging, required publication scans, no force push, and no milestone
completion before the later roadmap audit.

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required_HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- workspace_check: `PASS`
- status_short_before_report:
  - `M Makefile`
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M genesisvla/core/types/action.py`
  - `M pyproject.toml`
  - `M scripts/quality/bootstrap_project_local_tools.sh`
  - `M scripts/quality/genesis_check_project_local.sh`
  - `M tests/core/test_action.py`
  - `M tests/meta/test_repo_policy.py`
  - untracked M2 coordination/report/task/toolchain support paths

The dirty state matches the expected pre-publication M2 integration state.
Architecture did not stage, unstage, commit, push, PR, merge, stash, reset,
restore, clean, remove files, or modify source/tests/tooling/coordination state
during this review.

## Files Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
- `coordination/tasks/active/GVLA-M2-CORE-STATIC-002.yaml`
- `coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml`
- `coordination/reports/GVLA-M2-CORE-STATIC-002/owner-architecture.md`
- `coordination/reports/GVLA-M2-INTEGRATION-PUBLISH-002/owner-quality-gate-alignment.md`
- `runs/tmp/GVLA-M2-INTEGRATE-AUDIT-001/architecture/core-static-plan.md`
- `runs/tmp/GVLA-M2-INTEGRATE-AUDIT-001/data/data-static-plan.md`
- `runs/tmp/GVLA-M2-INTEGRATE-AUDIT-001/quality/integration-publication-plan.md`
- diff for:
  - `genesisvla/core/types/action.py`
  - `genesisvla/core/types/sample.py`
  - `tests/core/test_action.py`
  - `tests/meta/test_repo_policy.py`
- `git diff --name-status`

## Validation / Evidence Checked

- `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`:
  `PASS`, `0 errors, 0 warnings, 0 informations`
- `git diff --check`: `PASS`
- Suppression/static-hiding scan over `genesisvla/core/types/action.py`,
  `genesisvla/core/types/sample.py`, `tests/core/test_action.py`, and
  `tests/meta/test_repo_policy.py`: no matches for `type: ignore`,
  `pyright: ignore`, `cast(Any, ...)`, or Pyright strictness downgrade patterns.
- Quality gate-alignment report records:
  - `tests/meta/test_repo_policy.py -q`: `PASS`, `20 passed`
  - `make governance-check`: `PASS`
  - `make genesis-check`: `PASS`
  - product Pyright: `PASS`, `0 errors, 0 warnings, 0 informations`
  - `git diff --check`: `PASS`

I did not rerun broad gates because the Quality gate-alignment report already
records fresh green `make genesis-check` and `make governance-check` evidence,
and this review only needed lightweight Architecture confirmation.

## Public Contract Review

`ImageLike: TypeAlias = NumericArray` is acceptable for the current M1/M2 public
contract. It makes the image alias statically numeric, which matches accepted
M1/M2 image payloads (`uint8`, `float32`, and normalized numeric arrays), keeps
`RawSample.images` compatible with the existing readonly copy helper, and avoids
forcing dataloader tests to cast around a too-broad image type.

`ActionMask` remains bool-only as `NDArray[np.bool_]`. The invalid runtime test
uses a local helper:

```python
def _invalid_action_mask_for_runtime_probe() -> ActionMask:
    """构造静态契约外的掩码,仅用于验证运行时拒绝逻辑。"""
    invalid_mask: NDArray[np.float32] = np.ones((2, 7), dtype=np.float32)
    return cast(ActionMask, invalid_mask)
```

This helper is narrow, test-local, and documents that it probes runtime rejection
outside the valid static constructor domain. It does not widen the public
`ActionChunk.mask` contract and does not use `Any` or ignore comments.

## M1 Behavior / Dataloader Scope

No M1 runtime behavior break was found:

- action values remain numeric, finite, copied, and read-only;
- bool mask validation remains enforced;
- non-bool masks are still rejected at runtime;
- `RawSample` image/action/state immutability behavior remains unchanged;
- direct strict Pyright and reported full product tests are green.

No dataloader scope creep was found. `genesisvla/dataloader/**` and
`tests/dataloader/**` were not changed for this fix. The prior dataloader image
test diagnostics disappeared through the core alias correction.

## Gate Semantics Review

The Quality meta-policy fix does not weaken public gate semantics. It replaces a
stale literal whitelist for `blocking_gate` with a stricter state-consistency
rule:

- `M1-T` remains allowed for legacy/startup control-plane validation;
- non-`M1-T` gates must match between `PROGRAM_STATE.yaml` and
  `TASK_INDEX.yaml`;
- non-`M1-T` gates must be present in `TASK_INDEX.yaml` active, blocked, or
  completed task lists.

This is more appropriate for an active M2 gate sequence than hard-coding only
`GVLA-M2-TOOLENV-RECOVERY-001`, and it does not suppress product validation or
weaken Black/Ruff/Pyright/pytest gates.

## Blockers

None from Architecture.

Remaining publication responsibilities belong to Wave 4 Quality publication:
explicit staging, staged scans, local commit(s), non-force push, Draft PR
creation/update, and recording the PR URL/remote SHA. M2 milestone completion
must still wait for the later audit and publication evidence.

## Wave 4 Publication Readiness

`YES_FROM_ARCHITECTURE`

Wave 4 may proceed from the Architecture perspective after the other required
Wave 3 pre-publication reviews are also collected. Architecture does not require
a Data D-W1 for the four resolved static diagnostics.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, new worktree, new Python environment, stage, unstage,
commit, push, PR, merge, stash, reset, restore, clean, rm, feature-list pass
update, or completion-state update was used.

## Subagent Ledger

No short-lived Architecture subagents were used for this Wave 3 read-only
review. No subagent retirement was required.

## Parallelism Note

Read-only Architecture review only; no parallel write.
