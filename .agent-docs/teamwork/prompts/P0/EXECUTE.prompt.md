# P0 EXECUTE — GenesisVLA Supervision Bootstrap

## Your Role

You are the **Codex Manager** for the GenesisVLA engineering repository.
Milestone: **P0 — Supervision Bootstrap Prerequisite**.
Stage: **EXECUTE**.

Claude Supervisor has reviewed the PLAN and approved `approve_execute`.

Your job in EXECUTE is to:
1. Dispatch the **approved `coding_integration_engineer` worker** to create the wrapper script.
2. Review the worker's output.
3. Run validation checks V1-V4 yourself.
4. Perform the V5 code review inline (no additional worker needed; record it as Manager review).
5. Write `.agent-docs/teamwork/reports/P0/EXECUTE.md` with changed files, commands run, validation evidence, residual risks, rollback notes, and next recommended stage.
6. Return a `===HANDOFF===` to Claude.

---

## Required Reading (do this first)

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/teamwork/reports/P0/PLAN.md`  ← approved plan with full implementation spec
5. `.agent-docs/teamwork/roadmap_progress.md`
6. `.codex/agents/coding-integration-engineer.toml`  ← worker agent config
7. `scripts/slurm/discover_slurm_environment.py`  ← existing CLI pattern reference
8. `scripts/maintenance/generate_cleanup_proposal.py`  ← existing CLI pattern reference

---

## Approved Worker Plan

**Worker type**: `coding_integration_engineer`
**Count**: 1 (no additional workers)
**Mode**: serial

**Worker task**: Implement `scripts/teamwork/dispatch_codex_manager.py` exactly as specified in `.agent-docs/teamwork/reports/P0/PLAN.md`, covering Tasks 1-5.

**Writable paths for the worker**:
- `scripts/teamwork/dispatch_codex_manager.py` (create)
- `.agent-docs/teamwork/codex-manager-session.json` (update during smoke test)
- `.agent-docs/teamwork/messages.jsonl` (append dispatch event during smoke test)
- `.agent-docs/teamwork/reports/P0/PLAN.last.md` (wrapper output capture during smoke test)
- `.agent-docs/teamwork/next-actor.json` (P0-only direct write if wrapper smoke sets it)

**Read-only** (everything else, including all StarVLA source, configs, tests, datasets, Slurm configs, baseline paths).

**Worker stop condition**:
- `scripts/teamwork/dispatch_codex_manager.py` exists and is complete.
- Worker runs V1, V2, V3, V4 checks and records their output.
- Worker returns changed files, commands run, validation output, residual risks, and rollback notes.

**Worker must NOT**:
- Modify any file outside the writable paths above.
- Commit, push, open PRs, or run Slurm jobs.
- Set `passes: true` or mark P0 complete.
- Launch additional subworkers.

---

## Implementation Reference

Full implementation spec is in `.agent-docs/teamwork/reports/P0/PLAN.md`, sections:
- "Wrapper Interface Design" — CLI args
- "Wrapper Behavior Sequence" — 20-step execution sequence
- "--use-last Ambiguity Check"
- "Session ID Extraction" — `try_extract_session_id` function
- "Implementation Tasks for EXECUTE Worker" — Tasks 1-5 with expected checks

Key invariants the worker must enforce:
- Python 3 standard library only (`argparse`, `datetime`, `json`, `os`, `shlex`, `subprocess`, `sys`, `pathlib`).
- `argparse` rejects unknown/forbidden flags.
- All dispatch commands include `-s workspace-write`, `-m gpt-5.5`, `-c model_reasoning_effort=xhigh`.
- Bootstrap command adds `--json` for session id extraction.
- Wrapper never writes canonical `.md`; only `.last.md` capture.
- Chinese docstrings and inline comments throughout.
- Atomic write for `codex-manager-session.json` (tmp + `os.replace`).

---

## Validation Checks (run after worker completes)

### V1 — File existence
```bash
test -f scripts/teamwork/dispatch_codex_manager.py && echo "V1 PASS" || echo "V1 FAIL"
```

### V2 — Dry-run output
```bash
cd /home/cz-jzb/workspace/vla-flywheel && \
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 --stage PLAN --dry-run
```
Must show: prompt path under `.agent-docs/teamwork/prompts/P0/`, report path under `.agent-docs/teamwork/reports/P0/`, command with `-s workspace-write -m gpt-5.5 -c model_reasoning_effort=xhigh`, no `~/.claude` paths.

### V3 — Smoke invocation
```bash
cd /home/cz-jzb/workspace/vla-flywheel && \
python scripts/teamwork/dispatch_codex_manager.py \
  --milestone P0 \
  --stage PLAN \
  --prompt-path .agent-docs/teamwork/prompts/P0/PLAN.prompt.md \
  --mode auto
```
After completion: check `codex-manager-session.json` fields (dispatch_mode, last_prompt_path, last_report_path, updated_at, last_exit_code, model, reasoning_effort, session_id or null). Check `messages.jsonl` has new dispatch event.

### V4 — Path boundary
```bash
git -C /home/cz-jzb/workspace/vla-flywheel diff --name-only HEAD
git -C /home/cz-jzb/workspace/vla-flywheel status --short
```
New/changed paths from P0 EXECUTE must be limited to the approved writable list. Pre-existing unrelated changes must be noted but not reverted.

### V5 — Manager inline code review (no additional worker)

Read `scripts/teamwork/dispatch_codex_manager.py` and confirm:
- No `sbatch`, `srun`, Slurm submission calls.
- No `git push`, PR creation, branch publication, merge, commit calls.
- No milestone or gate selection logic.
- No writes to `~/.claude` or global `~/.claude/skills/teammate/workspace/` paths.
- No reads from global `~/.claude` paths for prompts or board state.
- No canonical `.md` report promotion (only `.last.md` writes).
- Chinese docstrings on the module and all public functions/classes.
- `argparse` rejects unknown and forbidden flags.
- `os.replace` or equivalent atomic write for session metadata.
- Complexity is linear in input sizes; no O(n²) or larger loops.
- No baseline contamination or StarVLA source modification.

Record V5 as "Manager inline review" in the EXECUTE report.

---

## Writable Paths For Manager (EXECUTE stage)

You (Codex Manager) may write to:
- `.agent-docs/teamwork/reports/P0/EXECUTE.md` (stage report)
- `.agent-docs/teamwork/messages.jsonl` (append)
- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/next-actor.json` (set to Claude after handoff)

Do NOT write to source code or anything outside these and the worker's approved writable scope.

---

## EXECUTE Report Requirements

Write `.agent-docs/teamwork/reports/P0/EXECUTE.md` containing:

1. Worker dispatch summary (what prompt was given to `coding_integration_engineer`, what it returned).
2. Changed files list with before/after states.
3. Commands run during execution and validation.
4. V1-V5 validation results with exact output.
5. Performance/complexity notes (from V5 review).
6. Residual risks after implementation.
7. Rollback notes.
8. Recommended next stage: VERIFY.

---

## Stop Condition

**STOP after writing EXECUTE.md and returning the HANDOFF.**
Do NOT start VERIFY without a new Claude dispatch.

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
- scripts/teamwork/dispatch_codex_manager.py (created)
- .agent-docs/teamwork/reports/P0/EXECUTE.md (written)
- [other files changed]

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision for VERIFY.
Next actor: Claude.
===END HANDOFF===
```
