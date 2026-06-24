# GVLA-M1-REVIEW-FIX-001 Owner Quality Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `dev/starvla-engineering-base`
- workspace_check: PASS

## Conclusion

Conclusion: PASS

Quality Owner applied the minimal requested policy/gate fixes after reading the
Architecture report and reference-asset evidence. The review-only `code-input`
assets remain trackable for PR review, while package discovery, Pyright, and the
project-local quality wrapper explicitly exclude `code-input`.

No commit, push, PR create/update, merge, force push, stash apply/drop/pop,
GVLA-M1-PUBLISH-001B continuation, M2 continuation, M1 completion marking,
`passes: true` update, `.agent-docs/feature_list.json` edit, global install,
conda base change, system Python change, shell config change, `/tmp` tool
environment, or `runs/tmp` cleanup was performed.

## Files Changed By Quality

- `pyproject.toml`
  - Added `code-input` and `code-input.*` to setuptools package discovery
    excludes.
- `pyrightconfig.genesisvla.json`
  - Added `code-input` to Pyright excludes.
- `scripts/quality/genesis_check_project_local.sh`
  - Added `code-input` and `../../../code-input` to the generated wrapper
    Pyright config excludes.
  - Kept product gates limited to `genesisvla tests/meta tests/core tests/config`.
- `tests/meta/test_repo_policy.py`
  - Added focused policy coverage:
    `test_should_keep_code_input_reference_assets_review_only`.
- `coordination/reports/GVLA-M1-REVIEW-FIX-001/owner-quality.md`
  - This report.

Reviewed but not newly modified by this Quality stage:

- `.gitignore`
  - Existing allowlist already satisfied the required approved code-input review
    asset tracking policy.
- `code-input/REFERENCE_ASSETS.md`
- `code-input/LICENSE_REVIEW.md`

No extracted third-party source file or zip under `code-input/**` was edited.

## License / Copyright / NOTICE Decision

Decision: PASS_REFERENCE_TRACKING_ALLOWED

Reviewed evidence:

- `coordination/reports/GVLA-M1-REVIEW-FIX-001/reference-assets.md`
- `code-input/REFERENCE_ASSETS.md`
- `code-input/LICENSE_REVIEW.md`

Summary:

- `code-input/dexbotic-main/LICENSE` is preserved and recorded as MIT license
  evidence.
- `code-input/FluxVLA-main/LICENSE` is preserved and recorded as Apache-2.0
  license evidence.
- No standalone `NOTICE`, `COPYING`, or `COPYRIGHT` file was reported by the
  reference-asset review.
- README and metadata files are preserved in the extracted trees.
- The assets are accepted only as review-only PR reference assets. Future copied
  or adapted code still requires source/destination/license/reuse-class
  attribution in the implementing task report.

No `BLOCKED_LICENSE` condition was found.

## Code-Input Tracking Policy Result

Result: PASS

`.gitignore` explicitly keeps `code-input/` ignored by default, then allowlists
only the approved review assets:

- `code-input/dexbotic-main.zip`
- `code-input/FluxVLA-main.zip`
- `code-input/dexbotic-main/**`
- `code-input/FluxVLA-main/**`
- `code-input/REFERENCE_ASSETS.md`
- `code-input/LICENSE_REVIEW.md`

Representative `git check-ignore -v` results showed allowlist hits for:

- zip: `code-input/dexbotic-main.zip`,
  `code-input/FluxVLA-main.zip`
- LICENSE: `code-input/dexbotic-main/LICENSE`,
  `code-input/FluxVLA-main/LICENSE`
- README: `code-input/dexbotic-main/README.md`,
  `code-input/FluxVLA-main/README.md`
- md docs: `code-input/dexbotic-main/docs/Data.md`
- pdf: `code-input/dexbotic-main/docs/Dexbotic_Tech_Report.pdf`
- png: `code-input/dexbotic-main/docs/rl_results.png`
- mp4: `code-input/dexbotic-main/hardware/so101/demo_press_button.mp4`
- npy: `code-input/FluxVLA-main/test/data/datasets/rlds_dataset/actions.npy`
- checkpoint placeholder: `code-input/FluxVLA-main/checkpoints/.gitkeep`

No `*.parquet` file was found under `code-input` for a representative parquet
check.

## Package / Pyright / Wrapper / Test Policy Result

Result: PASS

- Package discovery:
  - `pyproject.toml` now excludes `code-input` and `code-input.*`.
- Root Pyright:
  - `pyrightconfig.genesisvla.json` now excludes `code-input`.
- Wrapper-generated Pyright:
  - `scripts/quality/genesis_check_project_local.sh` now emits both
    `code-input` and `../../../code-input` in the generated Pyright config
    excludes.
  - After wrapper execution,
    `runs/tmp/m1-tool-filelists/pyrightconfig.wrapper.json` contained those
    exclusions.
- Product gate scope:
  - Wrapper Black file list is generated only from
    `genesisvla tests/meta tests/core tests/config`.
  - Wrapper pytest runs
    `tests/meta/test_repo_policy.py tests/core tests/config -v`.
  - Wrapper Ruff runs only
    `genesisvla tests/meta tests/core tests/config`.
  - Wrapper Pyright includes only GenesisVLA M1 source/tests plus project root
    extraPaths; `code-input` is explicitly excluded.
- Meta-policy test:
  - `test_should_keep_code_input_reference_assets_review_only` passes and checks
    tracking allowlist, package excludes, Pyright excludes, and wrapper gate
    scope/excludes.

## Validation Commands / Results

| Command | Result |
| --- | --- |
| `runs/tmp/m1-tool-venv/bin/python -m py_compile tests/meta/test_repo_policy.py` | PASS, exit 0. |
| `runs/tmp/m1-tool-venv/bin/python -m pytest tests/meta/test_repo_policy.py -v` | PASS, 14/14 tests passed. |
| `bash scripts/quality/genesis_check_project_local.sh` | PASS, exit 0. `py_compile` PASS; pytest 52/52 PASS; Black file-list PASS; Ruff PASS; Pyright PASS with 0 errors, 0 warnings, 0 informations. |
| `git diff --check` | PASS, no output. |
| `git check-ignore -v` representative approved code-input assets | PASS. Required representative assets were unignored/trackable through the approved allowlist; no parquet representative existed. |

## DevSpace MCP Compliance

Result: PASS

Quality Owner used only local shell/git/project-wrapper commands. No DevSpace
MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/
edit/bash, or DevSpace-derived evidence was used as project-internal workflow.
Any DevSpace references reviewed were prohibition/compliance text only.

## Subagent Retirement Ledger

No short-lived subagents were used. No active Quality subagent contexts remain.

## Parallelism Proposal

Parallelism proposal: `no_parallel_write`.

Actual execution used serial file edits only. Some read-only inspections were
run in parallel shell calls; no parallel writes were performed.

## Residual Scope Notes

- The working tree contains many untracked `code-input/**` review assets by
  explicit user/task decision. They remain reference-only and must be staged by
  Manager with explicit pathspecs if publication proceeds.
- `code-input/**` must not be imported by GenesisVLA runtime, package discovery,
  CI import path, Pyright include, or product lint/test gate.
- No broad optional scan over the full extracted reference trees was run beyond
  the required ignore/tracking and license-boundary evidence.
