# P0 PLAN — GenesisVLA Supervision Bootstrap

## Your Role

You are the **Codex Manager** for the GenesisVLA engineering repository.
Milestone: **P0 — Supervision Bootstrap Prerequisite**.
Stage: **PLAN**.

You are **read-only** for source code during this stage. You may write to:
- `.agent-docs/teamwork/reports/P0/PLAN.md`
- `.agent-docs/teamwork/messages.jsonl` (append only)
- `.agent-docs/teamwork/claude-inbox.md` (if you need to consult Claude)
- `.agent-docs/teamwork/workspace/task-board.md`

Do NOT write any source code, scripts, or tests during PLAN. Produce only the plan document.

---

## Required Reading (do this first)

1. `AGENTS.md`
2. `boundaries.txt`
3. `CLAUDE.md`
4. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
5. `.agent-docs/teamwork/claude_supervisor_usage.md`
6. `.agent-docs/teamwork/roadmap_progress.md`  ← Claude's answers to DISCUSS open questions are here
7. `.agent-docs/teamwork/reports/P0/DISCUSS.md`  ← full DISCUSS findings
8. `scripts/slurm/discover_slurm_environment.py`  ← reference for existing Python CLI patterns
9. `scripts/maintenance/generate_cleanup_proposal.py`  ← reference for existing Python CLI patterns
10. `~/.claude/skills/teammate/scripts/sync_task_board.py`  ← reference for task board path routing

---

## Stage Objective

Draft a **complete, reviewable implementation plan** for P0 EXECUTE so that Claude Supervisor can make an `approve_execute` decision.

The plan must cover the wrapper, session routing, validation, rollback, and the single approved worker.

---

## Claude Supervisor Decisions (from DISCUSS review)

These are confirmed decisions. Include them verbatim in the PLAN:

1. **`next-actor.json` write authority**: Direct writes to `.agent-docs/teamwork/next-actor.json` are authorized for Codex Manager **during P0 only** (wrapper not yet built). After P0, all `next-actor.json` updates must flow through the wrapper. The PLAN must document this transition and ensure the wrapper sets `next-actor.json` in future milestones.

2. **Wrapper prompt creation policy**: The wrapper must accept `--prompt-path` for Claude-provided prompts (the standard pattern). It may also auto-detect an existing prompt at the standard path `<teamwork-root>/prompts/<milestone>/<stage>.prompt.md`. Claude always provides or pre-approves the prompt; the wrapper never generates prompt content.

3. **Unit test scope for P0**: P0 acceptance requires:
   - `dispatch_codex_manager.py --dry-run` output shows all local Teamwork paths under `.agent-docs/teamwork/`.
   - One wrapper smoke invocation that verifies `.agent-docs/teamwork/codex-manager-session.json` is updated with session_id, dispatch_mode, last_prompt_path, last_report_path, updated_at, and last_exit_code.
   - Full pytest unit test suite is M0 scope, not P0.

4. **Sandbox for all stages**: Always use `-s workspace-write`. Stage write restrictions come from prompt instructions, not sandbox mode.

5. **`.last.md` promotion policy**: Wrapper only ever writes to `.last.md`. Claude promotes manually (or via prompt) after accepting the report. No automatic promotion.

6. **Codex model and reasoning**: All dispatch commands must explicitly set `model=gpt-5.5` and pass `-c model_reasoning_effort=xhigh`.

---

## Plan Scope

The EXECUTE stage will deliver exactly one artifact:

```
scripts/teamwork/
  dispatch_codex_manager.py
```

No other source files are in scope for P0 EXECUTE.

---

## Plan Requirements

### 1. Wrapper Interface Design

Define the complete Python CLI interface:

```
dispatch_codex_manager.py [OPTIONS]

Required:
  --milestone MILESTONE_ID     e.g. P0
  --stage STAGE                DISCUSS|PLAN|EXECUTE|VERIFY|REVIEW

Optional:
  --repo-root PATH             default: auto-detect git root
  --teamwork-root PATH         default: <repo-root>/.agent-docs/teamwork
  --prompt-path PATH           explicit prompt file; default: <teamwork-root>/prompts/<milestone>/<stage>.prompt.md
  --report-path PATH           canonical report path; default: <teamwork-root>/reports/<milestone>/<stage>.md
  --mode {bootstrap,resume,auto}  default: auto (uses session file to decide)
  --session-id SESSION_ID      explicit codex session id for resume
  --use-last                   boolean flag: use --last fallback (requires explicit opt-in and ambiguity check)
  --dry-run                    print command only, do not execute
  --sandbox {read-only,workspace-write,danger-full-access}  default: workspace-write
  --model MODEL                default: gpt-5.5
  --reasoning-effort EFFORT    default: xhigh

Forbidden behaviors (enforce in code):
  - Do not accept --approve-gate, --mark-complete, --set-passes, --push, --pr
  - Do not accept any Slurm submission flags
  - Do not write to paths outside <teamwork-root> or <repo-root>
  - Do not read prompts from global ~/.claude paths
```

### 2. Wrapper Behavior Sequence

Define the exact execution steps the wrapper must perform:

```
Step 1: Validate --repo-root (must be a git repository root or raise error)
Step 2: Validate --teamwork-root exists under --repo-root
Step 3: Resolve prompt path:
  a. If --prompt-path given and file exists: use it
  b. If --prompt-path given and file missing: raise error
  c. If no --prompt-path: use <teamwork-root>/prompts/<milestone>/<stage>.prompt.md; raise if missing
Step 4: Resolve report capture path: <teamwork-root>/reports/<milestone>/<stage>.last.md
  - Create parent directory if needed
Step 5: Determine dispatch mode:
  a. If --mode bootstrap: use `codex exec`
  b. If --mode resume and --session-id: use `codex exec resume <session-id>`
  c. If --mode resume and --use-last: check ambiguity (see below), then use `codex exec resume --last`
  d. If --mode auto: read <teamwork-root>/codex-manager-session.json; use session_id if not null, else bootstrap
Step 6: Build codex command:
  codex exec [resume [<session-id>|--last]] \
    -C <repo-root> \
    -s <sandbox> \
    -m <model> \
    -c model_reasoning_effort=<reasoning-effort> \
    -o <report-capture-path> \
    - < <prompt-path>
Step 7: If --dry-run: print command preview with all resolved paths, print teamwork file routing table, exit 0
Step 8: Execute command, capture exit code
Step 9: Update <teamwork-root>/codex-manager-session.json with:
  - session_id (null until extraction is solved)
  - dispatch_mode (bootstrap|resume-by-id|resume-last)
  - repo_root, active_milestone, current_stage
  - last_prompt_path, last_report_path
  - sandbox, model, reasoning_effort
  - codex_command_preview (the exact command string)
  - updated_at (ISO timestamp)
  - last_exit_code
Step 10: Append dispatch event to <teamwork-root>/messages.jsonl
Step 11: Exit with codex exit code
```

### 3. --use-last Ambiguity Check

When `--use-last` is requested, the wrapper must:

1. Read `<teamwork-root>/codex-manager-session.json`.
2. Confirm `session_id` is null (otherwise use `--session-id` instead).
3. Run `codex exec resume --help` or equivalent to confirm `--last` is supported.
4. Check that no other `.codex` session metadata under `<repo-root>` was created after the last bootstrap timestamp.
5. If any ambiguity check fails: print error and exit non-zero.
6. Record the ambiguity-check result in `codex-manager-session.json` under `use_last_fallback_reason`.

### 4. Session ID Extraction (best-effort)

In the EXECUTE phase, the worker should attempt `codex exec --json` and parse for a stable session or thread id event.
The wrapper code should have a `try_extract_session_id(jsonl_events)` function that returns null if no stable id is found.
Do not crash if extraction fails; record `session_id: null` and `session_id_extraction_method: "not_found"`.

### 5. Worker Plan

Claude approves exactly **one write-capable worker** for P0 EXECUTE:

```
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create scripts/teamwork/dispatch_codex_manager.py only
Writable paths:
  - scripts/teamwork/dispatch_codex_manager.py (create)
  - .agent-docs/teamwork/codex-manager-session.json (update for smoke test)
Read-only paths (all others including source, baseline, datasets, slurm configs)
Stop condition: wrapper file exists, dry-run passes, smoke invocation passes
Worker must not: modify any other file, run sbatch, push, create PRs
```

No parallel workers. No additional workers.

### 6. Validation Plan (for VERIFY stage)

Define the checks that VERIFY must pass before P0 EXECUTE is accepted:

```
V1. File existence: scripts/teamwork/dispatch_codex_manager.py exists
V2. Dry-run output: python scripts/teamwork/dispatch_codex_manager.py \
      --milestone P0 --stage PLAN --dry-run
    Output must show:
      - prompt path under .agent-docs/teamwork/prompts/P0/
      - report path under .agent-docs/teamwork/reports/P0/
      - codex command with -C, -s workspace-write, -m gpt-5.5, -c model_reasoning_effort=xhigh
      - no global ~/.claude/skills/teammate paths in any routing field
V3. Smoke invocation: python scripts/teamwork/dispatch_codex_manager.py \
      --milestone P0 --stage PLAN \
      --prompt-path .agent-docs/teamwork/prompts/P0/PLAN.prompt.md \
      --mode auto
    After completion:
      - .agent-docs/teamwork/codex-manager-session.json updated with dispatch_mode, last_prompt_path, last_report_path, updated_at, last_exit_code
      - .agent-docs/teamwork/messages.jsonl has a new dispatch event
      - .agent-docs/teamwork/reports/P0/PLAN.last.md has output (may already exist from Claude's direct dispatch)
V4. Path boundary: wrapper must not have written to any path outside .agent-docs/teamwork/ or scripts/teamwork/
V5. Script review: code_reviewer worker reads the wrapper source and confirms:
      - no Slurm job submission
      - no git push/PR calls
      - no milestone/gate selection logic
      - no .claude/ global path writes
      - Chinese docstrings and comments
```

### 7. Rollback Plan

```
Rollback: delete scripts/teamwork/dispatch_codex_manager.py
Recovery: the existing manual codex exec dispatch pattern remains operative
Risk: none — the wrapper is additive; removing it restores the pre-P0 state
```

### 8. Risk List

Include risks identified in DISCUSS plus any new ones from the PLAN design:

- Session id extraction may fail across CLI versions → record `session_id: null`, use `--last` only under explicit opt-in.
- `--use-last` ambiguity if another session is created in the repo → enforced by ambiguity check in Step 5 of wrapper behavior.
- Wrapper scope creep (accepting gate-approval or Slurm flags) → CLI argparse must reject forbidden args.
- Chinese docstrings may conflict with line length limits → use Google-style with 100 char limit per AGENTS.md.

---

## Output Requirements

Write your complete plan document to:
```
.agent-docs/teamwork/reports/P0/PLAN.md
```

The plan must contain all sections in this prompt:
1. Wrapper Interface Design
2. Wrapper Behavior Sequence
3. --use-last Ambiguity Check
4. Session ID Extraction
5. Worker Plan (including all fields Claude requires)
6. Validation Plan (V1–V5)
7. Rollback Plan
8. Risk List
9. In-scope vs out-of-scope clarification
10. Recommended next stage: EXECUTE (pending Claude approval)

End your **final response** with:

```
===HANDOFF===
Completed:
- ...

Pending:
- ...

Decisions:
- ...

Files Affected:
- .agent-docs/teamwork/reports/P0/PLAN.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: approve_execute | revise_plan | continue_discuss | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
```

---

## Stop Condition

**STOP after writing PLAN.md and returning the HANDOFF.**
Do NOT implement the wrapper.
Do NOT modify source code, scripts, tests, baseline paths, or datasets.
EXECUTE requires Claude's explicit `approve_execute` gate decision.
