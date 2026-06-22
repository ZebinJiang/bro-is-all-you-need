# M0 EXECUTE — GenesisVLA RFC 与质量闸门

## Your Role

You are the **Codex Manager**.
Milestone: **M0 — GenesisVLA RFC 与质量闸门**.
Stage: **EXECUTE**.

Claude Supervisor has reviewed `.agent-docs/teamwork/reports/M0/PLAN.md` and approved `approve_execute`.

Your job in EXECUTE:
1. Dispatch the **approved `coding_integration_engineer` worker** to implement the M0 plan, including TDD red-green sequence.
2. Review the worker's output.
3. Run V1-V5 Manager validation; perform V6 inline.
4. Write `.agent-docs/teamwork/reports/M0/EXECUTE.md`.
5. Return `===HANDOFF===` to Claude.

---

## Required Reading

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/teamwork/reports/M0/DISCUSS.md`
5. `.agent-docs/teamwork/reports/M0/PLAN.md`  ← full implementation spec
6. `.agent-docs/teamwork/roadmap_progress.md`
7. `.codex/agents/coding-integration-engineer.toml`

The PLAN is the source of truth for what to build, in what order, and what to verify.

---

## Approved Worker Plan (verbatim from PLAN Section 7)

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M0 artifacts, run TDD red-green and make genesis-check, capture validation output.
Stop condition: all in-scope artifacts exist, pytest tests/meta/test_repo_policy.py green, make genesis-check green, worker returns evidence.
Worker must not: launch additional workers, modify out-of-scope files, push, PR, sbatch, set passes=true.
```

Writable paths whitelist (worker may write ONLY these):
```
docs/genesisvla/rfc_000_architecture.md
docs/genesisvla/coding_standard.md
docs/genesisvla/testing_standard.md
pyrightconfig.genesisvla.json
.pre-commit-config.yaml
.github/workflows/genesisvla.yml
.github/PULL_REQUEST_TEMPLATE.md
Makefile
pyproject.toml
tests/meta/__init__.py
tests/meta/test_repo_policy.py
genesisvla/__init__.py
genesisvla/core/__init__.py
genesisvla/config/__init__.py
genesisvla/py.typed
```

Read-only paths: everything else, including `starVLA/`, `datasets/`, `runs/`, `pyrightconfig.json` (legacy), `code-input/`, `related-assets/`, all secrets, all baseline configs.

---

## Critical Worker Instructions

Pass these to the worker explicitly:

1. **TDD order is mandatory**:
   - Step T1: write `tests/meta/__init__.py` and `tests/meta/test_repo_policy.py` first.
   - Step T2: run `pytest tests/meta/test_repo_policy.py -v` and capture RED output (must be `4 failed`).
   - Step T3: create the rest of M0 artifacts (Tasks 2-9 in PLAN section 4).
   - Step T4: run `pytest tests/meta/test_repo_policy.py -v` and capture GREEN output (must be `4 passed`).
   - Step T5: run `make genesis-check` and capture green output.

2. **Test names must use pytest's `test_` prefix**:
   ```python
   def test_should_have_genesisvla_docs(): ...
   def test_should_have_make_genesis_check(): ...
   def test_should_have_pyright_strict_config(): ...
   def test_should_have_pr_template_with_test_plan(): ...
   ```

3. **`pyproject.toml` change is additive only**: add `pytest` and `pyright` strings to `[project.optional-dependencies].dev` array. Do NOT modify `[tool.black]`, `[tool.ruff]`, or any other section. Do NOT change line-length values.

4. **`Makefile` change is additive only**: add the `genesis-check` target at the end. Do NOT modify the existing `check`, `help`, `clean`, or `autoformat` targets.

5. **PR template is updated, not duplicated**: edit `.github/PULL_REQUEST_TEMPLATE.md` to insert the GenesisVLA Test Plan section after the existing `## Testing` heading. Do NOT create `.github/pull_request_template.md`.

6. **Python file requirements**:
   - All new Python files (`tests/meta/*.py`, `genesisvla/**/*.py`) must have Chinese module docstrings.
   - `genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py` contain ONLY the docstring — no imports, no code.
   - `genesisvla/py.typed` is an empty marker file.

7. **Tool availability**: if `pytest` and `pyright` are not installed in the current Python environment, the worker should install them via `pip install pytest pyright` (these are now in dev deps anyway). Use `pip install --user` if there is no project venv. Record install commands in the report.

8. **Chinese docstrings for doc files**: doc files (`docs/genesisvla/*.md`) are in English (governance language). Only Python files require Chinese docstrings.

---

## Validation Checks (after worker)

Run V1-V5 yourself; V6 is your inline manager review.

### V1 — File existence
Run the V1 Python script from PLAN section 8.

### V2 — Meta policy tests pass
```bash
pytest tests/meta/test_repo_policy.py -v
```
Expected: 4 passed, exit code 0.

### V3 — make genesis-check green
```bash
make genesis-check
```
Expected: black + ruff + pyright + pytest all run cleanly, exit code 0.

### V4 — Pyright strict
```bash
pyright -p pyrightconfig.genesisvla.json
```
Expected: 0 errors, exit code 0.

### V5 — Path boundary
```bash
git status --short
git diff --name-only HEAD
```
Expected: only whitelist files appear in new/changed paths. Pre-existing dirty files (`.gitignore`, `docs/agent_skills/...` deletions) are noted but not reverted.

### V6 — Manager inline review
Confirm per PLAN section 8 V6:
- Python files have Chinese docstrings
- No `starVLA/` edits
- No Slurm, push, PR creation, secrets
- `pyrightconfig.json` (legacy) unchanged
- `make check` target unchanged
- `[tool.black]` / `[tool.ruff]` global sections unchanged
- `.pre-commit-config.yaml` path-scoped (does not match `starVLA/`)
- CI workflow runs `make genesis-check`, not `make check`

---

## Writable Paths For Manager (EXECUTE stage)

- `.agent-docs/teamwork/reports/M0/EXECUTE.md` (write)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude after handoff)

Plus the worker's writable whitelist above (worker writes via Manager).

---

## EXECUTE Report Requirements

Write `.agent-docs/teamwork/reports/M0/EXECUTE.md` containing:

1. Worker dispatch summary
2. Changed files list with SHA256 (or file sizes) for each created file
3. **Full RED pytest output** (after T2)
4. **Full GREEN pytest output** (after T4)
5. **Full `make genesis-check` output** (after T5)
6. V1-V6 validation results
7. Performance/complexity notes
8. Residual risks
9. Rollback notes
10. Recommended next stage: VERIFY

---

## Stop Condition

STOP after writing EXECUTE.md and HANDOFF.
Do NOT start VERIFY without new Claude dispatch.

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude gate decision for VERIFY.
Decisions:
- ...
Files Affected:
- [whitelist files created/modified]
- .agent-docs/teamwork/reports/M0/EXECUTE.md (written)
Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting VERIFY gate.
Next actor: Claude.
===END HANDOFF===
```
