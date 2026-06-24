# M0 REVIEW — GenesisVLA RFC 与质量闸门

## Your Role

You are the **Codex Manager**.
Milestone: **M0**.
Stage: **REVIEW**.

Claude Supervisor reviewed `.agent-docs/teamwork/reports/M0/VERIFY.md`. The VERIFY recommendation was `request_fixes` because of the V3 Black multi-path timeout.

**Claude has root-caused the issue and authorizes a 1-line Manager inline fix in this REVIEW stage** (see below). After the fix, VERIFY re-runs V3 to confirm green and Claude decides on M0 acceptance.

Your job in REVIEW:
1. Apply the **authorized Makefile inline patch** (Claude's specified fix).
2. Re-run V3 (`make genesis-check`) in this environment.
3. Re-run V2 (pytest) to confirm policy tests still pass (the Makefile change updates `test_should_have_make_genesis_check`'s expected target body).
4. Re-run V5 (path boundary) post-patch.
5. Update `roadmap_progress.md` and `workspace/task-board.md` to reflect M0 progress.
6. Write `.agent-docs/teamwork/reports/M0/REVIEW.md` with final synthesis.
7. Return `===HANDOFF===` with M0 acceptance recommendation.

NO worker dispatch in REVIEW. All work is Manager inline.

---

## Required Reading

1. `AGENTS.md`
2. `CLAUDE.md`
3. `.agent-docs/teamwork/reports/M0/PLAN.md`
4. `.agent-docs/teamwork/reports/M0/EXECUTE.md`
5. `.agent-docs/teamwork/reports/M0/VERIFY.md`
6. `Makefile` (current state)
7. `tests/meta/test_repo_policy.py` (to understand test expectations)

---

## Root Cause Analysis (from Claude)

`black 24.x` uses multiprocessing for multi-path/directory checks. In this sandboxed environment, the fork/spawn behavior hangs indefinitely (180s+, 600s+ all timeout). The code itself is Black-clean — single-file checks pass instantly.

**Verified fix** (Claude tested independently):
```bash
black --check --line-length 100 --workers 1 genesisvla tests/meta
```
Completes in <1s, exit 0, "5 files would be left unchanged".

This is a tooling/environment workaround, not a code change. It does not affect which files are checked, line length, exit codes on real failures, or any other check.

---

## Claude Supervisor Authorized REVIEW Edits

### Edit 1 — `Makefile`: add `--workers 1` to Black command

Locate the `genesis-check` target's black line:
```makefile
	black --check --line-length 100 genesisvla tests/meta
```

Change to:
```makefile
	black --check --line-length 100 --workers 1 genesisvla tests/meta
```

This is the ONLY change in the `Makefile`. Do NOT modify any other line. Do NOT modify the `check`, `autoformat`, `help`, `clean` targets.

### Edit 2 — `tests/meta/test_repo_policy.py`: update expected fragment

The current test asserts the Makefile contains:
```
black --check --line-length 100 genesisvla tests/meta
```

After Edit 1, this exact fragment no longer matches. Update the assertion to:
```
black --check --line-length 100 --workers 1 genesisvla tests/meta
```

Locate the relevant assertion in `test_should_have_make_genesis_check` and update only the Black fragment string. Do NOT modify the test function structure, names, or other assertions (ruff/pyright/pytest fragments stay unchanged).

These two edits keep the TDD test in sync with the corrected Makefile target.

---

## Verification Tasks

### V2 (post-fix) — Meta policy tests
```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/meta/test_repo_policy.py -v
```
Expected: 4 passed.

### V3 (post-fix) — `make genesis-check` runs clean
```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s make genesis-check
```
Expected: All 4 commands (black, ruff, pyright, pytest) run, exit code 0.
Capture the full output.

### V5 (post-fix) — Path boundary

```bash
git status --short
git diff --name-only HEAD
```

Expected post-REVIEW changed paths (in addition to whitelist from EXECUTE):
- `Makefile` (M0-modified, plus REVIEW edit 1 line)
- `tests/meta/test_repo_policy.py` (M0-created, plus REVIEW edit 2 line)
- `.gitignore` (already patched in VERIFY)

No other new changes from REVIEW.

### Additional check — Roadmap progress and task-board sync

Update `.agent-docs/teamwork/roadmap_progress.md` and `.agent-docs/teamwork/workspace/task-board.md` to reflect M0 stages (DISCUSS, PLAN, EXECUTE, VERIFY completed; REVIEW in progress/completed).

---

## Writable Paths For REVIEW

- `.agent-docs/teamwork/reports/M0/REVIEW.md` (write)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json`
- `.agent-docs/teamwork/roadmap_progress.md`
- `Makefile` (one authorized edit — see Edit 1)
- `tests/meta/test_repo_policy.py` (one authorized edit — see Edit 2)

Read-only: everything else.

---

## REVIEW Report Requirements

Write `.agent-docs/teamwork/reports/M0/REVIEW.md`:

1. Summary of M0 stages (DISCUSS → PLAN → EXECUTE → VERIFY → REVIEW).
2. The applied REVIEW edits with before/after diff snippets.
3. V2, V3, V5 post-fix results with exact command outputs.
4. Final M0 deliverables list (Features F0.1-F0.7 → file paths).
5. Residual risks after REVIEW.
6. Rollback notes.
7. Acceptance recommendation: `accept_m0` | `request_fixes` | `block_for_user`.

If V3 finally passes cleanly after the fix, recommend `accept_m0` and explicitly note that M0 is ready for Claude to mark complete in `roadmap_progress.md`.

---

## Stop Condition

STOP after writing REVIEW.md and HANDOFF.

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude final M0 acceptance and next-milestone selection.
Decisions:
- ...
Files Affected:
- .agent-docs/teamwork/reports/M0/REVIEW.md (written)
- Makefile (authorized REVIEW edit applied)
- tests/meta/test_repo_policy.py (authorized REVIEW edit applied)
- .agent-docs/teamwork/roadmap_progress.md (updated)
- .agent-docs/teamwork/workspace/task-board.md (updated)
- .agent-docs/teamwork/next-actor.json (set to Claude)
Next-Actor-Notes:
Returning control to Claude Supervisor. M0 awaiting final acceptance.
Next actor: Claude.
===END HANDOFF===
```
