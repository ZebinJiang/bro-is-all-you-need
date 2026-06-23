# GVLA-M1-PR-FIX-001 Architecture Owner Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel`
- git_root: `/home/cz-jzb/workspace/vla-flywheel`
- branch: `dev/starvla-engineering-base`
- workspace_check: PASS

## Result

Architecture fix implementation completed locally. No commit, push, force-push,
PR merge, stash apply/drop/pop, M1 completion, or M1 `passes: true` update was
performed.

## Changed Files

Architecture-owned fixes:

- `.github/workflows/genesisvla.yml`
- `.gitignore`
- `coordination/THREAD_REGISTRY.yaml`
- `coordination/tasks/active/GVLA-M1T-001.yaml`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `docs/genesisvla/m1_lite_contract.md`
- `genesisvla/config/loader/validate.py`
- `pyproject.toml`
- `tests/config/test_loader.py`
- `tests/meta/test_repo_policy.py`

Stable `.codex` governance files exposed by `.gitignore` for PR inclusion:

- `.codex/config.toml`
- `.codex/agents/thread_explorer.toml`
- `.codex/agents/thread_implementer.toml`
- `.codex/agents/thread_reviewer.toml`
- `.codex/agents/thread_tester.toml`

Runtime ledger files removed from source publication scope:

- `.agent-docs/teamwork/codex-manager-session.json`
- `.agent-docs/teamwork/messages.jsonl`
- `.agent-docs/teamwork/reports/M0/DISCUSS.last.md`
- `.agent-docs/teamwork/reports/M0/EXECUTE.last.md`
- `.agent-docs/teamwork/reports/M0/PLAN.last.md`
- `.agent-docs/teamwork/reports/M0/REVIEW.last.md`
- `.agent-docs/teamwork/reports/M0/VERIFY.last.md`
- `.agent-docs/teamwork/reports/M1/DISCUSS.last.md`
- `.agent-docs/teamwork/reports/M1/EXECUTE.last.md`
- `.agent-docs/teamwork/reports/M1/PLAN.last.md`
- `.agent-docs/teamwork/reports/M1/VERIFY.last.md`
- `.agent-docs/teamwork/reports/P0/DISCUSS.last.md`
- `.agent-docs/teamwork/reports/P0/EXECUTE.last.md`
- `.agent-docs/teamwork/reports/P0/PLAN.last.md`
- `.agent-docs/teamwork/reports/P0/VERIFY.last.md`

Pre-existing dirty/untracked workspace items observed and not reverted by this
Owner stage include Manager publication state files and reports under
`coordination/PROGRAM_STATE.yaml`, `coordination/TASK_INDEX.yaml`,
`coordination/reports/GVLA-M1-PUBLISH-*`, and related active task cards.

## Decisions Made

- Stable `.codex` governance configuration is a source contract for this PR.
  `.gitignore` now keeps `.codex` generally local while whitelisting only
  `.codex/config.toml` and the four `thread_*` Owner subagent configs.
- Legacy task card references to `.codex/agents/explorer.toml`,
  `implementer.toml`, `reviewer.toml`, and `tester.toml` were updated to
  `thread_explorer.toml`, `thread_implementer.toml`, `thread_reviewer.toml`,
  and `thread_tester.toml`.
- `genesisvla/py.typed` is now declared in `pyproject.toml` package data.
- CI path filters now include stable `.codex`, `coordination/**`,
  `docs/coordination/**`, and M1 governance state docs so governance/config
  changes trigger the GenesisVLA gate.

## Runtime Ledger Cleanup Decision

Runtime ledgers are not published as stable source contracts. The session JSON,
Teamwork messages JSONL, and `.last.md` capture files were removed from the
tracked publication scope and ignored going forward.

`coordination/THREAD_REGISTRY.yaml` was replaced with a sanitized example that
keeps the registry shape, prompt paths, charter paths, archived flags, and
startup-smoke fields without real thread ids, local absolute paths, Codex session
ids, or resume commands. Meta policy now checks the sanitized registry shape and
explicitly rejects committed `thread_id: 019...` style runtime ids.

## Config Validation Changes

`genesisvla/config/loader/validate.py` now rejects silent coercion:

- `name: 123` raises `ValueError`
- `schema_version: 1.0` raises `ValueError`
- `runner.batch_size: 1.5` raises `ValueError`
- `runner.batch_size: true` raises `ValueError`
- `runner.max_steps: 2.0` raises `ValueError`
- `required_modalities: [front, null]` raises `ValueError`
- empty required modality strings raise `ValueError`
- integer fields reject bool and float
- string fields reject non-string values

Focused coverage was added in `tests/config/test_loader.py`.

## M1-lite Docs Change

Added `docs/genesisvla/m1_lite_contract.md` to clarify that M1 is a
numpy-only, torch-free minimal contract layer. The doc states that
`FrameworkOutput.loss` remains `float | NumericArray` in M1 and that torch/Tensor
training contracts belong to M3/M4 runner/model framework work, not this PR.

## Validation

Passed:

- `PYTHONPYCACHEPREFIX=runs/tmp/m1-pr-fix-pycache runs/tmp/m1-tool-venv/bin/python -m py_compile genesisvla/config/loader/validate.py tests/config/test_loader.py tests/meta/test_repo_policy.py`
- `PYTHONDONTWRITEBYTECODE=1 PYTEST_ADDOPTS='-p no:cacheprovider' runs/tmp/m1-tool-venv/bin/python -m pytest tests/config tests/meta tests/core -v` -> `47 passed`
- `RUFF_CACHE_DIR=runs/tmp/m1-pr-fix-ruff-cache runs/tmp/m1-tool-venv/bin/python -m ruff check --config line-length=100 genesisvla/config/loader/validate.py tests/config/test_loader.py tests/meta/test_repo_policy.py`
- `bash scripts/quality/genesis_check_project_local.sh` -> py_compile PASS, pytest `47 passed`, Black PASS, Ruff PASS, Pyright `0 errors`
- `git diff --check`
- tracked working-tree secret-pattern scan with `git grep -nIE ... -- .` -> no findings
- changed/untracked file secret-pattern scan with `rg ...` over edited files and exposed `.codex` files -> no findings
- forbidden artifact/protected-path scan over `git status --porcelain --untracked-files=all` -> no findings

Not run:

- staged scans (`git diff --cached --check`, staged secret scan, staged artifact
  scan, large staged-file scan, large text-diff scan) were not run because this
  Owner stage did not stage files and the user prohibited commit/push work.

Notes:

- A runtime-id scan over the sanitized registry/docs/meta policy reported only
  the expected defensive test literal `assert "thread_id: 019" not in registry`.
- An initial direct Black invocation hung and was interrupted, but the project
  wrapper's per-file Black phase later completed successfully.

## DevSpace MCP Compliance

PASS. This Owner stage used local repository shell commands and `apply_patch`
only. It did not use DevSpace MCP, `vla-flywheel-devspace`, MCP connector tools,
`open_workspace`, MCP read/write/edit, or MCP bash as project workflow or
evidence.

## Subagent Retirement Ledger

No short-lived subagents were created or used. No Owner thread was created or
archived.

## Residual Risks / Next Routing

- Quality Owner should perform independent read-only review and decide whether
  the existing broader dirty/untracked Manager publication files are in or out of
  the final PR-fix publication scope.
- Manager should stage intentionally, run required staged scans, then handle any
  commit/push/PR action separately. This Architecture stage intentionally did not
  stage, commit, or push.
