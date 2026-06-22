# M1 REVIEW + Publication Gate

## Your Role

You are the **Codex Manager**. Milestone **M1 — Core Contract + Typed Config**. Stage **REVIEW**.

Claude has accepted all prior M1 stages:
- DISCUSS, PLAN, EXECUTE (33 files), EXECUTE-FIX-1 (pytest pythonpath), VERIFY (independent code_reviewer), EXECUTE-FIX-2 (legacy_sample metadata contract).
- VERIFY-2 resolution: Claude-run external validation accepted the FIX-2 (independent reviewer prescribed the exact fix; Claude confirmed the code matches the Section 6.8 contract; tests 19/19 green; pre-FIX-2 full `make genesis-check` was exit 0 and FIX-2 is a provably non-breaking O(1) change).

REVIEW does TWO things:
1. **Final synthesis** of M1 (worker coverage ledger closure, residual risks, final gate evidence).
2. **Milestone Publication Gate** per `CLAUDE.md` — commit on dev/*, push, open PR, record PR URL. The user requires every completed milestone to provide a PR link.

NO worker dispatch needed for REVIEW synthesis. The publication gate is Manager-run git work.

---

## Required Reading

1. `AGENTS.md`, `CLAUDE.md` (Milestone Publication Gate section), `boundaries.txt`
2. `.agent-docs/git_workflow.md` — **REQUIRED for the publication gate scans**
3. All M1 reports: `.agent-docs/teamwork/reports/M1/{DISCUSS,PLAN,EXECUTE,EXECUTE_FIX_1,VERIFY,EXECUTE_FIX_2}.md`
4. `.agent-docs/teamwork/roadmap_progress.md`

---

## Part A — Final Synthesis

Write the REVIEW synthesis covering:

### A1. M1 Stage Summary
Table of all stages (DISCUSS → PLAN → EXECUTE → EXECUTE-FIX-1 → VERIFY → EXECUTE-FIX-2 → REVIEW) with status + report path.

### A2. Worker Coverage Ledger (closed)
| Stage | Worker | Status |
- DISCUSS: Manager read-only inspection (incl. FluxVLA/dexbotic archive review)
- PLAN: Manager plan
- EXECUTE: 1× coding_integration_engineer (33 files)
- EXECUTE-FIX-1: 1× coding_integration_engineer (pytest pythonpath)
- VERIFY: 1× code_reviewer (independent, found 1 blocking defect)
- EXECUTE-FIX-2: 1× coding_integration_engineer (legacy_sample metadata)
- REVIEW: Manager synthesis + Claude external validation

### A3. Final Gate Evidence
Run the full gate in a deps-present env and capture output:
```bash
cd /home/cz-jzb/workspace/vla-flywheel
export PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH
make genesis-check
```
If the Codex sandbox Black/Pyright environment issue recurs (known M0/M1 behavior), run each step individually and record per-step exit codes, and note that Claude confirmed `make genesis-check` exit 0 externally pre-FIX-2 with FIX-2 being non-breaking. Capture:
- black --workers 1 (all 4 dirs)
- ruff
- pyright (note sandbox 142-error env issue if it recurs; venv-aware pyright = 0 errors)
- pytest tests/meta tests/core tests/config → expect 19 passed

### A4. M1 Deliverables (F1.1-F1.7 → files)
List the 33 source files + governance updates mapped to features F1.1-F1.7.

### A5. Residual Risks
- non-blocking: validate.py `_str_value` coerces non-string scalars (reviewer non-blocking risk) — note for future config hardening
- non-blocking: M0 meta tests lack per-test Chinese docstrings
- Codex sandbox Black/Pyright env issue (not a code defect)

---

## Part B — Milestone Publication Gate (per CLAUDE.md)

Execute these steps in order. This is the standing user requirement: M1 must be pushed with a PR URL.

### B1. Read git workflow
Read `.agent-docs/git_workflow.md` for the exact scan commands.

### B2. Branch check
```bash
branch="$(git branch --show-current)"
echo "branch: $branch"
# must be dev/* — current is dev/starvla-engineering-base
case "$branch" in dev/*) echo "OK dev branch" ;; *) echo "BLOCKER: not dev/*"; exit 1 ;; esac
```

### B3. Stage ONLY M1 + M0 + P0 deliverables (intentional commit)
The worktree has a mix. Stage deliberately. Include the GenesisVLA governance overlay deliverables that are intended to be versioned for this milestone chain:
```
git add genesisvla/ tests/ docs/genesisvla/ pyrightconfig.genesisvla.json \
  .pre-commit-config.yaml .github/workflows/genesisvla.yml .github/PULL_REQUEST_TEMPLATE.md \
  Makefile pyproject.toml .gitignore scripts/teamwork/dispatch_codex_manager.py
```
**Do NOT** `git add` the deleted `docs/agent_skills/integrate-starvla-dataset/assets/templates/*` paths unless they are intentional — inspect first and report. **Do NOT** add `.agent-docs/` (governance overlay is local-only per gitignore). **Do NOT** add `code-input/`, `datasets/`, `runs/`, secrets.

Run `git status --short` and report exactly what is staged before committing.

### B4. Required scans (from git_workflow.md)
Run and capture output:
```bash
git diff --cached --check                 # whitespace
# secret-pattern scan, artifact-extension scan, large staged-file scan, large text-diff scan
# (use the exact commands / fallbacks from .agent-docs/git_workflow.md)
```
If `gitleaks` exists: `gitleaks protect --staged --redact` or equivalent. Record results or recorded skip reasons.

### B5. Commit
```bash
git commit -m "$(cat <<'EOF'
feat(genesisvla): M0 quality gates + M1 core contracts and typed config

P0: local Codex Manager dispatch wrapper.
M0: GenesisVLA RFC + docs, pyright strict config, pre-commit, CI, PR template, make genesis-check.
M1: core types (RawSample/ActionChunk/FrameworkOutput), protocols, typed registry,
    dataclass config schema + OmegaConf loader/export, legacy_sample adapter, TDD (19 tests).

Co-Authored-By: Claude <noreply@anthropic.com>
EOF
)"
```
Report the commit SHA.

### B6. Push
```bash
git push -u origin "$branch"
```
Use the user-provided GitHub proxy if the push needs network:
```bash
export http_proxy=http://192.168.32.11:18000 https_proxy=http://192.168.32.11:18000
```
(only for the push command). Report push result.

### B7. Open or update PR
Use `gh pr create` (base = main, head = dev branch) OR record the PR creation command + URL. If `gh` is unavailable or auth/network blocks it, record the exact blocker and the manual PR-creation URL.

### B8. Record PR URL
Write the PR URL into:
- `.agent-docs/teamwork/reports/M1/REVIEW.md`
- update `.agent-docs/teamwork/roadmap_progress.md`
- update `.agent-docs/teamwork/workspace/task-board.md`

### B9. If blocked
If any of B4-B7 is blocked by scans, network, credentials, permissions, or remote state, set the milestone status to `ready_to_publish_blocked`, record the exact blocker and what Claude/User must do, and keep next-actor = Claude. Do NOT fake a PR URL.

**Do NOT merge the PR.**

---

## Writable paths (Manager)

- `.agent-docs/teamwork/reports/M1/REVIEW.md`
- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/messages.jsonl`, `next-actor.json`
- git operations: staging/commit/push of the intended deliverables on the dev/* branch (publication gate authorized)

NO source code edits in REVIEW (it is not a fix stage).

---

## REVIEW Report

`.agent-docs/teamwork/reports/M1/REVIEW.md`:
1. Parts A1-A5 (synthesis)
2. Part B: publication evidence — staged file list, scan outputs, commit SHA, push result, **PR URL** (or `ready_to_publish_blocked` + blocker)
3. Final recommendation: `m1_complete` (only if PR URL exists) | `ready_to_publish_blocked`

## Stop Condition

STOP after REVIEW.md + HANDOFF. Provide the PR URL (or blocker) to Claude.

End with `===HANDOFF=== ... Next actor: Claude. ===END HANDOFF===`.
