# M1 EXECUTE-FIX-1 — pytest pythonpath gate fix

## Your Role

You are the **Codex Manager**. Milestone **M1**, stage **EXECUTE (scoped fix)**.

Claude Supervisor ran external validation of the prior M1 EXECUTE and found ONE real defect:
`make genesis-check` runs bare `pytest tests/...` (not `python -m pytest`). When the `genesisvla`
package is not installed editable, the test files fail with `ModuleNotFoundError: No module named
'genesisvla'`. CI installs `pip install -e ".[dev]"` so CI passes, but the M0 Definition of Done
requires `make genesis-check` to be green LOCALLY without requiring an editable install.

This is a scoped EXECUTE fix, NOT a new feature. Dispatch the approved worker to apply it.

---

## Approved Worker Plan (scoped fix)

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: apply ONE config fix so `make genesis-check`'s bare pytest can import genesisvla without editable install, then re-run the full gate and capture evidence.
```

## The Fix (exact)

Add a pytest config section to `pyproject.toml` so the repo root is on `sys.path` for bare `pytest`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

Placement: add as a new top-level table in `pyproject.toml`. Do NOT modify `[tool.black]`,
`[tool.ruff]`, `[project]`, `[project.optional-dependencies]`, or `[project.dependencies]`.

If `pyproject.toml` already has a `[tool.pytest.ini_options]` table, add `pythonpath = ["."]` to it
without removing existing keys.

Rationale: `python -m pytest` implicitly adds cwd to sys.path (which is why earlier runs passed),
but the Makefile uses bare `pytest`. `pythonpath = ["."]` makes both work and keeps the gate
independent of editable installs. This matches the existing `configfile: pyproject.toml` that pytest
already reports.

## Writable paths (worker)

- `pyproject.toml` (only the additive `[tool.pytest.ini_options]` table)

Everything else read-only. No source/test/doc changes. Do NOT touch `[tool.black]`/`[tool.ruff]`/`[project]`.

---

## Validation (Manager runs after worker; do NOT rely on Codex sandbox for Black)

Use the `/tmp/vla-flywheel-m0-tools/bin` venv (has numpy+omegaconf) or any env with deps:

```bash
cd /home/cz-jzb/workspace/vla-flywheel
export PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH
# Bare pytest (the failing case) must now pass:
pytest tests/core tests/config -v
pytest tests/meta/test_repo_policy.py tests/core tests/config -v
# Full gate (if Codex sandbox Black times out, run steps individually and record per-step exit codes;
# Claude will run `make genesis-check` externally as final evidence):
make genesis-check
```

Expected: bare `pytest tests/core tests/config -v` → 14 passed (previously 14 failed with
ModuleNotFoundError). Combined → 18 passed.

Record the before/after: prior failure was `ModuleNotFoundError: No module named 'genesisvla'` under
bare pytest; after fix, bare pytest passes.

---

## Writable paths (Manager)

- `.agent-docs/teamwork/reports/M1/EXECUTE_FIX_1.md` (write)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude)
- worker writable: `pyproject.toml`

## Report

Write `.agent-docs/teamwork/reports/M1/EXECUTE_FIX_1.md`:
1. The exact pyproject.toml diff
2. Before: bare pytest ModuleNotFoundError evidence
3. After: bare pytest 14/18 passed evidence
4. `make genesis-check` result (or per-step exit codes)
5. Path-boundary git status (only pyproject.toml changed by this fix)
6. Recommended next stage: VERIFY

## Stop Condition

STOP after the report + HANDOFF. Do not start VERIFY.

End with `===HANDOFF===` ... `Next actor: Claude.` `===END HANDOFF===`.
