# GVLA-M1-HARDEN-001 Owner Architecture Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `dev/starvla-engineering-base`
- head: `645850d92b9d2217c060ffe2205b266d04dae541`
- workspace_check: `PASS`
- initial_git_status_short:
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M coordination/reports/GVLA-M1-PUBLISH-001B/manager-summary.md`
  - `M coordination/tasks/active/GVLA-M1-PUBLISH-001A-FIX.yaml`
  - `M coordination/tasks/active/GVLA-M1-PUBLISH-001B.yaml`
  - `?? coordination/reports/GVLA-M1-PR-FIX-001/manager-summary.md`
  - `?? coordination/reports/GVLA-M1-PUBLISH-001A-FIX-WS/`
  - `?? coordination/reports/GVLA-M1-PUBLISH-001A-FIX/`
  - `?? coordination/reports/GVLA-M1-PUBLISH-001B/owner-quality-precommit.md`
  - `?? coordination/reports/GVLA-M1-REVIEW-FIX-001/manager-summary.md`
  - `?? coordination/reports/GVLA-M2-PLANEXEC-001/`
  - `?? coordination/tasks/active/GVLA-M1-HARDEN-001.yaml`
  - `?? coordination/tasks/active/GVLA-M1-PUBLISH-001A-FIX-WS.yaml`
  - `?? tests/meta/__init__.py`

## Architecture Decision

`BLOCKED_OWNER_EXECUTION`

The workspace and scope were verified, and the current PR blocker surfaces were identified. However, the required internal Implementer subagent did not return a completed handoff before Manager convergence. It was retired while still running. It left allowed-scope working-tree modifications, but because it did not return changed-file rationale, validation suggestions, or completion evidence, this Architecture stage cannot approve or claim the implementation as complete.

## Changed Files Observed After Retiring Implementer

These files were modified or created in the working tree by the non-completed Implementer before retirement and remain unreviewed/unvalidated by this Owner report:

- `Makefile`
- `genesisvla/config/loader/validate.py`
- `genesisvla/core/types/action.py`
- `scripts/maintenance/delete_from_cleanup_manifest.py`
- `scripts/quality/genesis_check_project_local.sh`
- `scripts/slurm/discover_slurm_environment.py`
- `tests/config/test_loader.py`
- `tests/core/test_action.py`
- `tests/maintenance/`
- `tests/slurm/`

This report file was then written by Architecture:

- `coordination/reports/GVLA-M1-HARDEN-001/owner-architecture.md`

No staging, commit, push, stash, PR, merge, feature-list pass update, M2 worktree edit, protected dataset/run/checkpoint edit, or DevSpace MCP workflow was performed.

## Cleanup Safety Changes

`BLOCKED_OWNER_EXECUTION`

Initial review verified the pre-hardening cleanup script had a real blocker:

- `scripts/maintenance/delete_from_cleanup_manifest.py` used string `startswith` for containment.
- It resolved the target path before a raw symlink check, so symlink refusal ordering was insufficient.
- It did not explicitly reject deleting the repository root.
- It was vulnerable to sibling-prefix containment mistakes such as a path under `/workspace/repo-backup`.
- It needed `Path.resolve()` plus `Path.relative_to()` and destructive calls only after all checks.

The Implementer modified this file, but the edit was not handed off or validated before forced retirement. It must be reviewed by the next Owner/Quality pass before acceptance.

## Slurm Safety Changes

`BLOCKED_OWNER_EXECUTION`

Initial review verified the pre-hardening Slurm discovery script had real blockers:

- `scripts/slurm/discover_slurm_environment.py` used string `startswith` for config containment.
- `subprocess.run` lacked explicit timeouts.
- `--write-config` did not hard-block unsafe discovery states such as `UNKNOWN_CLUSTER`, empty cluster/partition, `TO_FILL`, or missing partition.
- `run_id` was not constrained to `^[A-Za-z0-9._-]+$`.
- Config writes were direct `write_text`, not temp file plus `os.replace()` atomic replacement.
- Output/config path containment needed `resolve()` plus `relative_to()`.

The Implementer modified this file and likely added `tests/slurm/`, but the edit was not handed off or validated before forced retirement. It must be reviewed before acceptance.

## Unknown-Key Rejection Design

`BLOCKED_OWNER_EXECUTION`

Initial review verified strict type validation already existed for strings, ints, bool/float rejection, non-empty modalities, and export-time validation. The missing PR blocker was unknown-key rejection at all four config layers:

- experiment top level;
- `model`;
- `data`;
- `runner`.

Required coverage still must be confirmed for YAML and CLI dotlist typos such as:

- `runner.bach_size`;
- `model.unknown`;
- `data.unknown`;
- `top_level_unknown`.

The Implementer modified `genesisvla/config/loader/validate.py` and `tests/config/test_loader.py`, but those changes were not handed off or validated before forced retirement.

## Action Contract Changes Or Deferrals

`BLOCKED_OWNER_EXECUTION`

Initial review found `genesisvla/core/types/action.py` already enforced positive `horizon`/`action_dim`, 2-D shape, and mask shape. The remaining small M1-scope hardening targets were:

- mask dtype must be bool;
- action values must be finite numeric;
- optional action names must be non-empty, unique, and match `action_dim` when supplied;
- empty horizon remains rejected.

The Implementer modified `genesisvla/core/types/action.py` and `tests/core/test_action.py`, but those changes were not handed off or validated before forced retirement. No Architecture approval is given for the modified contract in this report.

## M1 API Scope Note

`PASS_EXISTING_DOC`

`docs/genesisvla/m1_lite_contract.md` already states M1 is a minimal, numpy-only, torch-free contract layer. It also states `FrameworkOutput.loss` is `float | NumericArray`, and torch/Tensor losses, gradient behavior, device semantics, distributed execution, runner lifecycle, and model framework contracts belong to later M3/M4 milestones. No documentation edit was required before the Manager convergence instruction.

## Reference Asset / Code-Input Boundary

`PASS_EXISTING_POLICY`

Existing policy already keeps `code-input/**` review-only:

- `pyproject.toml` excludes `code-input` and `code-input.*` from package discovery.
- `pyrightconfig.genesisvla.json` excludes `code-input`.
- `scripts/quality/genesis_check_project_local.sh` excludes `code-input` from source gates and generated Pyright config.
- `tests/meta/test_repo_policy.py` contains a focused code-input reference-only policy test.

No code-input extracted upstream source was modified by this Architecture stage.

## Validation

Not run after final Manager convergence. Required next validation after reviewing/finalizing the unreturned Implementer edits:

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/config tests/core tests/meta tests/maintenance tests/slurm -v`
- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`
- `bash scripts/quality/genesis_check_project_local.sh`
- `git diff --check`
- `git status --short`

No `git diff --cached --check` was run because this Architecture stage did not stage files.

## Risks

- The working tree now contains allowed-scope modifications from a retired Implementer that did not provide a completion handoff.
- The changes may be correct, partially correct, or incomplete; they require explicit review before any approval or Quality handoff.
- The local wrapper/Makefile may have been changed to include new tests, but that must be reviewed to ensure `code-input` and M2 scope are still excluded.
- Historical dirty/untracked files remain present and were intentionally not cleaned, reset, restored, or staged.

## Follow-Ups

Blocking:

- Review the unreturned Implementer diffs in the listed changed files.
- If acceptable, run the focused project-local validation commands.
- If not acceptable, route a new serial Implementer pass or revert only the incomplete Implementer changes with explicit Manager approval.

Non-blocking:

- Quality Owner should independently confirm no M2 scope, `code-input` runtime inclusion, protected-path edits, or feature-list pass updates occurred.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, PR operation, push, merge, force push, staging, stash apply/drop/pop, global dependency install, `/tmp` tool environment, or M2 worktree operation was used as project-internal workflow or evidence.

## Subagent Retirement Ledger

| Subagent | Role | Status | Result |
| --- | --- | --- | --- |
| `019ef30b-1b42-7b21-ae3f-9d7e69a90736` | Explorer | Retired | Timed out before returning useful read-only findings; no writes. |
| `019ef30d-849e-72e1-906d-2c36342347f5` | Implementer | Retired | Timed out before completion handoff; left allowed-scope working-tree modifications listed above. |

Reviewer and Tester subagents were not started because Manager convergence required stopping internal subagent work and writing this report immediately.

## Parallelism Proposal

No parallel writes. The attempted workflow used a read-only Explorer followed by a single Implementer. The Implementer was the only write-capable subagent. Further work should remain serial because cleanup safety, Slurm safety, config schema, and local gates are shared public contracts.
