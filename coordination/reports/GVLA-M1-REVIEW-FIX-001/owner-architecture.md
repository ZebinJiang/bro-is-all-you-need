# GVLA-M1-REVIEW-FIX-001 Architecture Report

## Workspace Verification

- target_branch: `dev/starvla-engineering-base`
- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `dev/starvla-engineering-base`
- workspace_check: `PASS`

## Architecture Decision

`REQUEST_CHANGES`

The license evidence is sufficient for review-only tracking, but the publication contract is not yet fully encoded in repository policy/configuration. The current evidence shows `code-input/**` is intended to be tracked for review only, while package/type/gate policy still needs explicit exclusion checks and the `.gitignore` allowlist still needs to guarantee the approved zips and extracted reference trees can be tracked despite broad artifact ignore rules.

## Changed Files

- `coordination/reports/GVLA-M1-REVIEW-FIX-001/owner-architecture.md` only by this Architecture stage.

No source, test, wrapper, package, Pyright, feature-list, runtime, M2, dataset, checkpoint, or protected-path edits were made by this Architecture stage.

## License Decision

`PASS_REFERENCE_TRACKING_ALLOWED`

- `code-input/dexbotic-main/LICENSE` contains MIT License text with Dexmal copyright notice.
- `code-input/FluxVLA-main/LICENSE` contains Apache License 2.0 text.
- `code-input/REFERENCE_ASSETS.md`, `code-input/LICENSE_REVIEW.md`, and `coordination/reports/GVLA-M1-REVIEW-FIX-001/reference-assets.md` consistently classify both assets as review-only reference assets with original license files preserved.

No `BLOCKED_LICENSE` condition was found from the already established LICENSE evidence.

## Code-Input Boundary Decision

`REQUEST_CHANGES`

Required boundary remains:

- `code-input/dexbotic-main.zip`, `code-input/FluxVLA-main.zip`, and their extracted trees may be tracked for PR review.
- `code-input/**` must remain reference-only.
- `code-input/**` must not become a runtime dependency, package input, product test import target, Pyright source include, Black/Ruff product gate target, dataset/checkpoint input, or CI execution input.

Evidence reviewed:

- `code-input/REFERENCE_ASSETS.md` records the intended non-runtime policy.
- `code-input/LICENSE_REVIEW.md` records the same non-runtime policy.
- `scripts/quality/genesis_check_project_local.sh` currently builds product gates from `genesisvla tests/meta tests/core tests/config`, so it does not directly lint/type/test `code-input`.

Required change:

- Add explicit repository policy/config checks so this boundary is enforced, not only documented.

## Package / Pyright / Gate Decision

`REQUEST_CHANGES`

Required minimal fixes:

1. `.gitignore` must explicitly allow the approved `code-input` review assets to be tracked. Existing broad ignore rules such as artifact/media/checkpoint patterns can otherwise hide files inside the extracted reference trees.
2. `pyproject.toml` package discovery should explicitly exclude `code-input` and `code-input.*`.
3. `pyrightconfig.genesisvla.json` should explicitly exclude `code-input`.
4. `scripts/quality/genesis_check_project_local.sh` wrapper-generated Pyright config should explicitly exclude `code-input`, while keeping product gates limited to `genesisvla tests/meta tests/core tests/config`.
5. `tests/meta/test_repo_policy.py` should add a focused policy test for review-only `code-input` tracking and package/Pyright/wrapper exclusion.

These are publication contract fixes only; they must not make `code-input/**` executable product code.

## Runtime-ID / Source-Contract Decision

`PASS_WITH_SCOPE_NOTE`

The current task card and task index evidence for `GVLA-M1-REVIEW-FIX-001` use sanitized or stable identifiers for this task path. `coordination/tasks/active/GVLA-M1-REVIEW-FIX-001.yaml` records runtime Owner ids as `runtime-only`, and the report paths are repository-relative.

Broader historical coordination state may still contain prior runtime thread ids as evidence from earlier tasks. Per task instruction, this Architecture stage did not broad-scrub historical evidence reports or unrelated coordination history. No new real runtime thread id or local absolute path was added by this Architecture report as a stable source contract.

## M2 Dataloader Gate

No M2 implementation was reviewed or modified. No change to M2 dataloader behavior is approved by this Architecture stage. If future Quality gating needs dataloader coverage, it should be conditional and handled in the M2 task path, not by importing M2 scope into this M1 publication-fix task.

## Validation Commands / Results

Not run after the final Manager report-now instruction.

Required validation after the minimal fixes above:

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v`
- `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py`
- `git diff --check`

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, PR operation, staging operation, commit, push, stash apply/drop/pop, merge, force push, `/tmp` tool environment, global pip, or conda base workflow was used by this Architecture stage.

## Subagent Retirement Ledger

None used.

## Parallelism / No Parallel Write Note

No subagents and no parallel writes were used. Read-only local shell reads were used; the only write from this Architecture stage is this Owner report.

## Required Follow-Up

Blocking before Architecture approval:

- Apply the minimal `.gitignore`, `pyproject.toml`, `pyrightconfig.genesisvla.json`, wrapper-generated Pyright exclusion, and `tests/meta/test_repo_policy.py` policy-test updates listed above.
- Run the focused validation commands and record results.

This task should remain in `REQUEST_CHANGES` until those publication contract fixes are present and validation passes.
