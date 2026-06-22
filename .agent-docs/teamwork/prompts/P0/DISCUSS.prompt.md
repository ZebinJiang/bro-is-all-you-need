# P0 DISCUSS — GenesisVLA Supervision Bootstrap

## Your Role

You are the **Codex Manager** for the GenesisVLA engineering repository.
This is the first supervised GenesisVLA milestone: **P0 — Supervision Bootstrap Prerequisite**.
You are executing the **DISCUSS** stage.

You are **read-only** for source code during this stage. You may write to:
- `.agent-docs/teamwork/reports/P0/DISCUSS.md`
- `.agent-docs/teamwork/messages.jsonl` (append only)
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/workspace/task-board.md`

Do NOT modify any source code, scripts, tests, configs, or dataset files during DISCUSS.

---

## Required Reading (do this first)

Read these files before producing any output:

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
5. `.agent-docs/teamwork/claude_supervisor_usage.md`
6. `.agent-docs/teamwork/roadmap_progress.md`
7. `.agent-docs/teamwork/workspace/task-board.md`

---

## Stage Objective

Discuss and clarify the **P0 acceptance criteria** so that the Claude Supervisor can approve a PLAN in the next stage.

Specifically, address these discussion topics:

### Topic A: Local Teamwork Wrapper Design

The local wrapper `scripts/teamwork/dispatch_codex_manager.py` does **not exist yet**.
It must be designed and built during P0 EXECUTE.

For DISCUSS, answer:
- What should the wrapper do? (prompt generation, local path routing, codex exec vs resume, session metadata write)
- What Teamwork files should the wrapper route to `.agent-docs/teamwork/`?
- What inputs should it accept from Claude (milestone id, stage, report path)?
- What must the wrapper NOT do? (milestone selection, gate approval, Slurm execution, push/PR)
- Should the wrapper be a Python CLI, a shell script, or a Python module?
- What existing Teamwork scripts (in `~/.claude/skills/teammate/scripts/`) can be used or referenced?

### Topic B: Codex Manager Session Bootstrap/Resume

Based on the current `codex exec` CLI behavior:
- How can a session id be extracted after `codex exec`?
- If a stable session id is not available, when is `codex exec resume --last` safe?
- What should `.agent-docs/teamwork/codex-manager-session.json` record?
- What is the recommended bootstrap command shape for P0 EXECUTE?

### Topic C: GSD DISCUSS Smoke Criteria

For P0 to be complete, Codex Manager must demonstrate an interactive GSD DISCUSS loop.
Define the smoke criteria:
- What is the minimum evidence that GSD DISCUSS ran in this project context?
- What must the `.agent-docs/teamwork/reports/P0/DISCUSS.md` contain?
- What does a valid `===HANDOFF===` block look like for P0?

### Topic D: Repository Layout Inspection

Inspect the actual repository layout to determine:
- Does `scripts/teamwork/` directory exist? If not, what is the cleanest place to create it?
- Does any existing Teamwork plumbing already exist in the repository?
- Are there any conflicts between the governance overlay and existing StarVLA repo structure?

---

## Investigation Tasks

Run these commands (read-only) to gather facts:

```bash
# Repository layout
ls -la /home/cz-jzb/workspace/vla-flywheel/scripts/
find /home/cz-jzb/workspace/vla-flywheel/scripts -name "*.py" 2>/dev/null | head -20
find /home/cz-jzb/workspace/vla-flywheel/.agent-docs -type f | sort

# Existing Teamwork scripts
ls ~/.claude/skills/teammate/scripts/ 2>/dev/null

# Check codex exec resume behavior
codex exec resume --help 2>&1 | head -30
```

---

## GSD Command

After completing the investigation and discussion above, run:

```
$gsd-discuss-phase
```

Use the GSD discuss phase to structure your findings as a formal discussion artifact.
The discussion should capture scope, decisions, open questions, and risks for P0.

---

## Output Requirements

Write your complete stage report to:
```
.agent-docs/teamwork/reports/P0/DISCUSS.md
```

The report must contain:
1. Summary of findings from investigation
2. Answers to Topics A, B, C, D above
3. Decisions made during DISCUSS
4. Open questions that require Claude input
5. Risk list
6. Recommended next stage action

End your **final response** with a `===HANDOFF===` block in exactly this format:

```
===HANDOFF===
Completed:
- [list what was completed in DISCUSS]

Pending:
- [list items that remain for PLAN]

Decisions:
- [key decisions made]

Files Affected:
- .agent-docs/teamwork/reports/P0/DISCUSS.md (written)
- [any other files touched]

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

**STOP after completing the report and handoff.**
Do NOT advance to PLAN or EXECUTE.
Do NOT implement the wrapper script.
Do NOT modify source code, tests, or existing governance files.

The next stage (PLAN or further DISCUSS) requires explicit Claude Supervisor approval.
