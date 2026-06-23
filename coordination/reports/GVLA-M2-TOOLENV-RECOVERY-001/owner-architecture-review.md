# GVLA-M2-TOOLENV-RECOVERY-001 Owner Architecture Review

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- required_HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- workspace_check: `PASS`
- status_short:
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `?? coordination/reports/GVLA-M2-DATA-TYPING-001/`
  - `?? coordination/reports/GVLA-M2-RESTACK-001/`
  - `?? coordination/reports/GVLA-M2-UNBLOCK-001/`
  - `?? coordination/tasks/active/GVLA-M2-CORE-TYPING-001.yaml`
  - `?? coordination/tasks/active/GVLA-M2-DATA-TYPING-001.yaml`
  - `?? coordination/tasks/active/GVLA-M2-TOOLCHAIN-001.yaml`
  - `?? coordination/tasks/active/GVLA-M2-TOOLENV-RECOVERY-001.yaml`
  - `?? coordination/tasks/active/GVLA-M2-UNBLOCK-REVIEW-001.yaml`

The existing coordination state was treated as Manager-owned context outside
this review boundary. This review did not modify canonical source, tests,
tooling, feature-list passes, completion state, or candidate patches.

## Conclusion

`APPROVE`

Architecture approves proceeding to Wave 3 canonical integration, provided the
integration remains sequential and applies/validates the V2 toolchain recovery
before using the canonical worktree for final strict Pyright, pytest, build, and
source-provenance evidence. The pre-existing canonical venv is not acceptable
evidence and must be recovered by the V2 flow.

## Files And Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `coordination/tasks/active/GVLA-M2-TOOLENV-RECOVERY-001.yaml`
- Quality V2 report:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch/coordination/reports/GVLA-M2-TOOLENV-RECOVERY-001/owner-quality.md`
- Quality V2 patch:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch/runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/quality/toolchain-v2.patch`
- Quality V2 supersedes note:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch/runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/quality/toolchain-v2-supersedes.md`
- Architecture core typing report:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-core-typing-scratch/coordination/reports/GVLA-M2-CORE-TYPING-001/owner-architecture.md`
- Architecture core typing patch:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-core-typing-scratch/runs/tmp/GVLA-M2-UNBLOCK-001/architecture/core-typing.patch`
- Quality source-provenance evidence:
  - `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/stamps/m1-tool-venv.ready.json`
  - `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/source-provenance/runtime-import.json`
  - `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/source-provenance/build-source.json`
  - `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/source-provenance/pyright-root.json`
  - wheelhouse manifest under fingerprint `0d1243cd602f498fdbb61bc8`

## Validation Commands Run

- `sha256sum -c` for Quality V2 patch: `PASS`
- `sha256sum -c` for Architecture core typing patch: `PASS`
- `git apply --check <core-typing.patch>` in canonical worktree: `PASS`
- `git apply --check <toolchain-v2.patch>` in canonical worktree: `PASS`
- Quality scratch tool check:
  - project-local Python executable path: under
    `gvla-m2-toolchain-scratch/runs/tmp/m1-tool-venv/bin/python`
  - `sys.prefix`: `gvla-m2-toolchain-scratch/runs/tmp/m1-tool-venv`
  - `pyright --version`: `pyright 1.1.410`
  - `pytest --version`: `pytest 9.1.1`
- `git diff --check` in Quality scratch: `PASS`
- suppression/static-hiding scan over V2 and core patches:
  no matches for `# type: ignore`, `type: ignore`, `pyright: ignore`,
  `cast(Any`, basic type-checking downgrade, or dataloader exclusion.
- symlink scan:
  - Quality scratch venv contains normal Python/lib symlinks; no symlink to
    another worktree was found.
  - canonical pre-existing venv has stale interpreter symlinks and was not used
    as validation evidence.

Full canonical Pyright/pytest/build validation was skipped because applying
patches is forbidden in this review and the current canonical venv is not a
valid recovered environment. Quality scratch already records full V2 validation;
Wave 3 must reproduce that evidence after sequential canonical integration.

## Per-Worktree Isolation Review

`PASS`

The V2 design recovers a venv under each worktree's own
`runs/tmp/m1-tool-venv`, records a readiness stamp with `target_root`, and
rejects readiness stamps that point at another checkout. Source-provenance
artifacts in Quality scratch show:

- readiness target root:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch`;
- runtime clean-wheel import from
  `runs/tmp/GVLA-M2-TOOLENV-RECOVERY-001/clean-install-venv/.../site-packages`;
- build source root:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch`;
- Pyright wrapper target root:
  `/home/cz-jzb/workspace/vla-flywheel/.worktrees/gvla-m2-toolchain-scratch`.

This is sufficient to show the Quality scratch validation did not borrow the
canonical worktree or another source tree.

## Venv Move / Copy / Symlink Review

`PASS_WITH_CANONICAL_NOTE`

Quality's recovery report records incomplete venv quarantine and fresh
per-worktree venv recreation. The venv symlinks observed in Quality scratch are
normal Python virtualenv links, not copied/moved/symlinked venv reuse from a
different worktree.

The canonical worktree currently has a stale pre-recovery venv whose interpreter
symlink resolves outside the worktree. Architecture did not use it for
validation. Wave 3 should let V2 quarantine/rebuild it before accepting
canonical evidence.

## Pyright Interpreter And Source Tree Review

`PASS`

V2 keeps strict Pyright semantics and adds provenance for the generated wrapper
config. It does not remove `tests/dataloader` or `genesisvla/dataloader` from
coverage. The Quality report records:

- `make genesis-check`: `PASS`, product Pyright `0 errors`;
- direct `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`:
  `PASS`, `0 errors, 0 warnings, 0 informations`;
- source-provenance JSON showing Pyright target root and include set.

## M1 Contract / Static Semantics Review

`PASS`

V2 toolchain changes are confined to quality environment and validation
plumbing:

- `Makefile`
- `pyproject.toml`
- `requirements/quality/**`
- `scripts/quality/bootstrap_project_local_tools.sh`
- `scripts/quality/genesis_check_project_local.sh`
- `scripts/quality/genesis_build_verify_project_local.sh`
- `tests/meta/test_repo_policy.py`

They do not modify public M1 source contracts, config schema semantics, M2 data
contracts, model/training/deployment runtime, feature-list passes, or completion
state. The patch adds stricter reproducibility and provenance checks rather than
weakening static analysis.

## Architecture Core Typing Candidate Review

`PASS`

The existing Architecture patch remains a valid candidate:

- expected SHA256:
  `cbdf436c5877973d493de9a1e9d9a79a183c642461e00109896dcfdf39c47fba`
- SHA check: `PASS`
- `git apply --check` against canonical HEAD: `PASS`
- scope: `genesisvla/core/types/action.py` only

The patch narrows public array aliases and removes the known `np.all`/Pyright
unknown-overload path without changing runtime action behavior.

## Static Diagnostic Hiding Review

`PASS`

No evidence of diagnostic hiding was found:

- no `# type: ignore`;
- no `type: ignore`;
- no `pyright: ignore`;
- no `cast(Any, ...)`;
- no Pyright strictness downgrade;
- no dataloader/test exclusion added;
- no wrapper suppression of Pyright diagnostics.

V2 makes diagnostics more trustworthy by requiring source provenance and a
verified per-worktree tool environment.

## Proceed To Wave 3

`APPROVE_TO_PROCEED`

Architecture approves proceeding to Wave 3 canonical integration with these
conditions:

- apply V2 toolchain recovery before relying on canonical validation;
- rebuild/quarantine the existing canonical venv through V2 rather than using it;
- then apply and validate the Architecture core typing patch sequentially;
- rerun full canonical `make genesis-check`, `make governance-check`, strict
  Pyright, focused tests, build/wheel checks, source provenance, suppression
  scans, and protected-path scans before acceptance.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, source/test/tooling edit, patch application, stage,
unstage, commit, push, PR, merge, force, stash, reset, restore, clean, rm,
feature-list pass update, or completion-state update was used.

## Subagent Retirement Ledger

| Subagent | Role | Output collected | Risks summarized | Retired |
| --- | --- | --- | --- | --- |
| A-RO1 | Architecture Wave 2 read-only validation/review | yes: this report | yes | yes |

No additional short-lived Architecture subagents were created.

## Parallelism Note

No parallel writes. This Architecture review was read-only except for this
report. Speed/latency was requested by governance context but no speed field was
exposed in the available tool interface; recorded as requested/not exposed.
