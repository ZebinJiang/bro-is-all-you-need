# P0 VERIFY — GenesisVLA Supervision Bootstrap

## Your Role

You are the **Codex Manager** for the GenesisVLA engineering repository.
Milestone: **P0 — Supervision Bootstrap Prerequisite**.
Stage: **VERIFY**.

Claude Supervisor has reviewed the EXECUTE report and approved entry into VERIFY.

Your job in VERIFY is to:
1. Re-run V1, V2, and V5 checks independently against the current wrapper state.
2. **Do NOT re-run V3 smoke** — the EXECUTE report documents a "resumed-session prompt collision" risk; Claude has decided this is a known documented risk and not a P0 blocker. Re-running V3 here would repeat the collision.
3. Run the **P0 Evidence Checklist** from `CLAUDE.md` (all sections: Wrapper and local Teamwork routing, Codex Manager session routing, Interactive GSD handoff).
4. Write `.agent-docs/teamwork/reports/P0/VERIFY.md` with your findings.
5. Return a `===HANDOFF===` to Claude.

---

## Required Reading (do this first)

1. `CLAUDE.md`  ← contains the P0 Evidence Checklist
2. `.agent-docs/teamwork/reports/P0/EXECUTE.md`
3. `.agent-docs/teamwork/reports/P0/DISCUSS.md`
4. `.agent-docs/teamwork/reports/P0/PLAN.md`
5. `.agent-docs/teamwork/codex-manager-session.json`
6. `scripts/teamwork/dispatch_codex_manager.py`
7. `.agent-docs/teamwork/messages.jsonl`
8. `.agent-docs/teamwork/next-actor.json`
9. `.agent-docs/teamwork/workspace/task-board.md`

---

## Verification Tasks

### V1 — File existence (re-run)
```bash
test -f scripts/teamwork/dispatch_codex_manager.py && echo "V1 PASS" || echo "V1 FAIL"
wc -l scripts/teamwork/dispatch_codex_manager.py
```

### V2 — Dry-run (re-run)
```bash
cd /home/cz-jzb/workspace/vla-flywheel && \
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 --stage EXECUTE --dry-run
```
(Use --stage EXECUTE now to verify the routing works for the EXECUTE stage prompt)

Also:
```bash
python scripts/teamwork/dispatch_codex_manager.py --milestone P0 --stage VERIFY --dry-run
```

Both runs must show all paths under `.agent-docs/teamwork/`, no `~/.claude` paths.

### V5 — Code review (re-read and confirm)

Re-read `scripts/teamwork/dispatch_codex_manager.py` and verify independently. Confirm the V5 PASS from EXECUTE.md still holds.

### P0 Evidence Checklist (from CLAUDE.md)

Check each item in the P0 Evidence Checklist from `CLAUDE.md`:

**Wrapper and local Teamwork routing:**
- `scripts/teamwork/dispatch_codex_manager.py` exists → record yes/no
- wrapper dry-run shows all project-specific Teamwork paths under `.agent-docs/teamwork/` → check V2 output
- prompt path is under `.agent-docs/teamwork/prompts/P0/` → confirm from dry-run
- report path is under `.agent-docs/teamwork/reports/P0/` → confirm from dry-run
- `messages.jsonl`, `claude-inbox.md`, `next-actor.json`, and `workspace/task-board.md` are read from or written to the project-local Teamwork directory → verify by reading actual files

**Codex Manager session routing:**
- `.agent-docs/teamwork/codex-manager-session.json` records repository root, milestone id, stage, prompt path, report path, updated timestamp, and bootstrap/resume mode → read and confirm each field
- stable session id is recorded → confirm `session_id` field
- first dispatch used `codex exec`, normal continuation used `codex exec resume` → confirm from `messages.jsonl` and DISCUSS/PLAN dispatch history

**Interactive GSD handoff:**
- Codex Manager ran assigned DISCUSS stage and did not advance to PLAN → confirm from DISCUSS.md
- `.agent-docs/teamwork/reports/P0/DISCUSS.md` contains scope, questions, decisions, risks, GSD artifacts created or updated, and structured handoff → confirm from file
- `next-actor.json` ends with Claude as next actor after Codex handoff → confirm current state
- Claude records review outcome before any P0 feature is marked complete → note that Claude reviewed all stages

### V3 concern assessment

Read the EXECUTE.md V3 concern (PLAN.md modified by resumed session) and record:
- Is the wrapper itself free from the "promote canonical .md" behavior? (confirm from V5)
- Is the concern a wrapper defect or a session-use-pattern issue? Record your assessment.
- What is the recommended future policy to avoid this in M0 and beyond?

---

## Writable Paths For Manager (VERIFY stage)

- `.agent-docs/teamwork/reports/P0/VERIFY.md` (write)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude after handoff)

Do NOT run smoke invocations that resume the live PLAN session.
Do NOT modify source code or any file outside VERIFY-approved scope.

---

## VERIFY Report Requirements

Write `.agent-docs/teamwork/reports/P0/VERIFY.md` containing:

1. V1 re-check results
2. V2 re-check results (EXECUTE and VERIFY stage dry-runs)
3. V5 re-check results
4. P0 Evidence Checklist — each item with PASS/FAIL/PARTIALLY_MET
5. V3 concern assessment
6. Residual risks and recommended acceptance conditions
7. VERIFY recommendation: accept_p0 | request_fixes | block_for_user

---

## Stop Condition

**STOP after writing VERIFY.md and returning the HANDOFF.**
Do NOT start REVIEW without a new Claude dispatch.

End your final response with:

```
===HANDOFF===
Completed:
- ...

Pending:
- ...

Decisions:
- ...

Files Affected:
- .agent-docs/teamwork/reports/P0/VERIFY.md (written)
- .agent-docs/teamwork/next-actor.json (set to Claude)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting REVIEW gate decision.
Next actor: Claude.
===END HANDOFF===
```
