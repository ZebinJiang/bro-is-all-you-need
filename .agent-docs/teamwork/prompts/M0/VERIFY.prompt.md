# M0 VERIFY — GenesisVLA RFC 与质量闸门

## Your Role

You are the **Codex Manager**.
Milestone: **M0**.
Stage: **VERIFY**.

Claude Supervisor reviewed `.agent-docs/teamwork/reports/M0/EXECUTE.md` and approved entry into VERIFY with two scoped instructions (see below).

Your job in VERIFY:
1. Re-run V1, V2, V4 independently.
2. Re-run V3 with documented mitigations for the Black multi-path timeout.
3. **Apply one Manager inline governance edit to `.gitignore`** (authorized below).
4. Re-run V5 and V6 to confirm the final state.
5. Write `.agent-docs/teamwork/reports/M0/VERIFY.md`.
6. Return `===HANDOFF===` to Claude.

NO worker dispatch in VERIFY. All work is Manager inline (validation + the one authorized governance edit).

---

## Required Reading

1. `AGENTS.md`
2. `CLAUDE.md`
3. `.agent-docs/teamwork/reports/M0/PLAN.md`
4. `.agent-docs/teamwork/reports/M0/EXECUTE.md`
5. `.gitignore` (read first, then edit per authorization below)
6. `scripts/teamwork/dispatch_codex_manager.py`

---

## Claude Supervisor Decisions for VERIFY

### Decision V1 — V3 Black timeout assessment

The Worker T5 capture shows a clean green `make genesis-check`:
```
black --check --line-length 100 genesisvla tests/meta
All done! ✨ 🍰 ✨
1 file would be left unchanged.
...
ruff check --config 'line-length=100' genesisvla tests/meta
All checks passed!
pyright -p pyrightconfig.genesisvla.json
0 errors, 0 warnings, 0 informations
pytest tests/meta/test_repo_policy.py -v
4 passed in 0.01s
```

Manager re-run timed out because of Black multi-path startup overhead in the validation environment — not a code defect. Single-file Black checks passed.

**Claude accepts the worker T5 evidence as authoritative for M0 functional correctness.**

VERIFY must:
- Re-attempt V3 with a longer timeout (e.g., `timeout 600s`) using the same `/tmp/vla-flywheel-m0-tools/bin` PATH that worker used.
- If Black still hangs, run each Black/Ruff/Pyright/pytest step **individually** as a fallback and record each step's exit code separately.
- Record V3 as `PASS` if all individual steps succeed; `PASS_WITH_TOOLING_NOTE` if `make genesis-check` itself times out but individual steps pass; `FAIL` only if any individual step fails.

### Decision V2 — `.gitignore` governance patch (authorized inline Manager edit)

The current `.gitignore:237` rule `*/**/*.md` makes all `docs/genesisvla/*.md` files invisible to git. This violates the M0 intent (F0.1-F0.3 docs must be reviewable in PRs).

**Claude authorizes one Manager inline edit to `.gitignore`** to add this exception. This is a documentation-only governance change with no code-behavior impact.

Required edit:
- Locate the `*/**/*.md` line in `.gitignore`.
- Add a **negation** rule immediately after it:
  ```
  !docs/genesisvla/**/*.md
  ```
- The `!` prefix is the gitignore negation syntax — files matching this pattern will be tracked.

After the edit:
- Confirm `git check-ignore -v docs/genesisvla/rfc_000_architecture.md` returns nothing (file is no longer ignored).
- Confirm `git status` shows `docs/genesisvla/` files as untracked.

Do NOT make any other changes to `.gitignore`. Do NOT touch other ignored paths.

### Decision V3 — VERIFY may also update `.agent-docs/teamwork/workspace/task-board.md` and `next-actor.json` to reflect M0 progress.

---

## Verification Tasks

### V1 — File existence (re-run)

Use the V1 Python script from PLAN section 8. All 15 paths must exist. Expected: `V1 PASS`.

### V2 — Meta policy tests (re-run)

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/meta/test_repo_policy.py -v
```
Expected: 4 passed.

### V3 — `make genesis-check` with mitigations

Attempt 1:
```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 600s make genesis-check
```

If timeout:
```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 120s black --check --line-length 100 genesisvla
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 120s black --check --line-length 100 tests/meta
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s ruff check --config 'line-length=100' genesisvla tests/meta
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pyright -p pyrightconfig.genesisvla.json
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pytest tests/meta/test_repo_policy.py -v
```

Record each step's exit code.

### V4 — Pyright strict (re-run)

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pyright -p pyrightconfig.genesisvla.json
```
Expected: 0 errors.

### V5 — Path boundary (post-gitignore patch)

```bash
git status --short
git diff --name-only HEAD
git check-ignore -v docs/genesisvla/rfc_000_architecture.md
git check-ignore -v docs/genesisvla/coding_standard.md
git check-ignore -v docs/genesisvla/testing_standard.md
```

After the `.gitignore` patch:
- `git check-ignore` must return nothing (exit 1) for all three GenesisVLA doc paths.
- `git status` must now show `docs/genesisvla/` as untracked.

### V6 — Manager inline review (re-run, final state)

Confirm V6 PLAN-section-8 checks plus:
- `.gitignore` change is only the additive negation rule.
- No other `.gitignore` lines were modified.
- No source code was changed.

---

## Manager-only Edit Authorized: `.gitignore`

Use Edit (not a worker) to apply the `.gitignore` patch defined in Decision V2.
This is the only file outside `.agent-docs/teamwork/` that VERIFY may modify.

---

## Writable Paths For VERIFY

- `.agent-docs/teamwork/reports/M0/VERIFY.md` (write)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md` (update)
- `.agent-docs/teamwork/next-actor.json` (set to Claude after handoff)
- `.gitignore` (one authorized governance edit only)

Read-only: everything else.

---

## VERIFY Report Requirements

Write `.agent-docs/teamwork/reports/M0/VERIFY.md`:

1. V1-V6 re-validation results with exact command outputs.
2. `.gitignore` change diff (before/after the patched lines).
3. `git check-ignore` output confirming docs are no longer ignored.
4. Final residual risks.
5. Acceptance recommendation: `accept_m0` | `request_fixes` | `block_for_user`.

---

## Stop Condition

STOP after writing VERIFY.md and HANDOFF.
Do NOT start REVIEW without new Claude dispatch.

End with:
```
===HANDOFF===
Completed:
- ...
Pending:
- Claude REVIEW gate decision.
Decisions:
- ...
Files Affected:
- .agent-docs/teamwork/reports/M0/VERIFY.md (written)
- .gitignore (authorized governance patch applied)
- .agent-docs/teamwork/next-actor.json (set to Claude)
Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting REVIEW gate.
Next actor: Claude.
===END HANDOFF===
```
