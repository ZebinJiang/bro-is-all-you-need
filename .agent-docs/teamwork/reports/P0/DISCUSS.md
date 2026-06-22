# P0 DISCUSS — GenesisVLA Supervision Bootstrap

Date: 2026-06-18
Stage: DISCUSS
Manager: Codex
Report path: `.agent-docs/teamwork/reports/P0/DISCUSS.md`

## 1. Summary Of Investigation

Required governance files were read:

- `AGENTS.md`
- `boundaries.txt`
- `CLAUDE.md`
- `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- `.agent-docs/teamwork/claude_supervisor_usage.md`
- `.agent-docs/teamwork/roadmap_progress.md`
- `.agent-docs/teamwork/workspace/task-board.md`

Read-only investigation commands were run as requested.

Findings:

- `scripts/` exists and currently contains `data/`, `maintenance/`, `sandbox/`, `slurm/`, `init.sh`, and `smoke_test.sh`.
- `scripts/teamwork/` does not exist.
- Existing Python scripts under `scripts/` are:
  - `scripts/slurm/discover_slurm_environment.py`
  - `scripts/maintenance/generate_cleanup_proposal.py`
  - `scripts/maintenance/delete_from_cleanup_manifest.py`
- `.agent-docs/teamwork/` already exists with local Teamwork state:
  - `claude-inbox.md`
  - `claude_supervisor_usage.md`
  - `codex-manager-session.json`
  - `messages.jsonl`
  - `next-actor.json`
  - `prompts/P0/DISCUSS.prompt.md`
  - `roadmap_progress.md`
  - `teamwork_supervisor_protocol.md`
  - `workspace/task-board.md`
- Global teammate scripts exist at `~/.claude/skills/teammate/scripts/`, including:
  - `consult_claude.py`
  - `query_board.py`
  - `sync_task_board.py`
  - `state_machine.py`
  - `preflight.py`
  - `arena.py`
  - tests for those scripts
- `codex exec resume --help` confirms resume accepts a session id or thread name, and supports `--last` to select the newest recorded session when no id is provided.
- `codex exec --help` confirms `--json` is available for JSONL event output and `-o/--output-last-message` writes the final agent message.
- `.planning/` does not exist. `gsd-tools query init.phase-op P0` returned `phase_found: false`, `roadmap_exists: false`, and `planning_exists: false`.

GSD DISCUSS handling:

- `$gsd-discuss-phase` was invoked for process structure, and its workflow was read.
- The stock GSD workflow expects `.planning/ROADMAP.md` and normally writes `.planning/phases/...` artifacts.
- This supervised DISCUSS stage allows writes only to Teamwork paths. Therefore no `.planning/` artifacts were created.
- This report is the formal GSD-style discussion artifact for P0, using the required sections: scope, decisions, open questions, risks, and handoff.

## 2. Topic A — Local Teamwork Wrapper Design

The wrapper should be implemented during P0 EXECUTE at:

```text
scripts/teamwork/dispatch_codex_manager.py
```

Recommended form:

- Python CLI first.
- Keep logic importable as module functions inside the same file or nearby package only if later tests require it.
- Avoid a shell script as the primary implementation because the wrapper needs path validation, JSON metadata updates, prompt generation, and reliable subprocess handling.

Wrapper responsibilities:

- Accept a Claude-selected milestone id and stage.
- Generate or select the prompt file under `.agent-docs/teamwork/prompts/<milestone>/<stage>.prompt.md`.
- Ensure the report path is under `.agent-docs/teamwork/reports/<milestone>/<stage>.md` or an approved `.last.md` capture path.
- Force all project-specific Teamwork paths into `.agent-docs/teamwork/`.
- Choose `codex exec` for first bootstrap and `codex exec resume <session-id>` for normal continuation.
- Allow `codex exec resume --last` only under the policy described in Topic B.
- Run Codex with `-C /home/cz-jzb/workspace/vla-flywheel`.
- Use sandbox mode from Claude input, defaulting to `workspace-write` only when the stage explicitly allows writes; DISCUSS/PLAN should be constrained by prompt/write-scope rules.
- Capture Codex final output with `-o`.
- Prefer `--json` during real bootstrap/dispatch so the wrapper can test whether the CLI emits a stable session/thread id event.
- Update `.agent-docs/teamwork/codex-manager-session.json`.
- Append dispatch metadata to `.agent-docs/teamwork/messages.jsonl`.
- Record enough command preview/dry-run output for Claude to review during P0.

Teamwork files the wrapper must route locally:

- `.agent-docs/teamwork/workspace/task-board.md`
- `.agent-docs/teamwork/claude-inbox.md`
- `.agent-docs/teamwork/messages.jsonl`
- `.agent-docs/teamwork/next-actor.json`
- `.agent-docs/teamwork/codex-manager-session.json`
- `.agent-docs/teamwork/prompts/<milestone>/<stage>.prompt.md`
- `.agent-docs/teamwork/reports/<milestone>/<stage>.md`
- `.agent-docs/teamwork/reports/<milestone>/<stage>.last.md`

Minimum Claude inputs:

- `--milestone P0`
- `--stage DISCUSS|PLAN|EXECUTE|VERIFY|REVIEW`
- `--report-path .agent-docs/teamwork/reports/P0/<stage>.md` or equivalent controlled path
- `--prompt-path` optional override, otherwise generated from milestone/stage
- `--repo-root /home/cz-jzb/workspace/vla-flywheel`
- `--mode bootstrap|resume|auto`
- `--session-id` optional for resume
- `--use-last` explicit boolean fallback
- `--dry-run` for command preview and local-path verification
- `--sandbox` optional, with safe defaults by stage

The wrapper must not:

- choose the milestone;
- approve gates;
- advance stages;
- mark features or milestones complete;
- set `passes: true`;
- run Slurm jobs;
- run tests unless explicitly part of a later approved validation command;
- commit, push, open PRs, or publish branches;
- mutate source code, datasets, checkpoints, or StarVLA baseline files;
- write project-specific Teamwork state to global `~/.claude/skills/teammate/workspace/`;
- bypass Claude review by calling another high-level supervisor loop.

Existing Teamwork scripts to reuse or reference:

- `consult_claude.py`: useful for Codex-to-Claude consultation. It accepts `--board`, and when the board is under `.../workspace/task-board.md`, it projects sibling writes to `messages.jsonl`, `next-actor.json`, and `claude-inbox.md`.
- `query_board.py`: useful for bounded board history reads with `--board`.
- `sync_task_board.py`: useful as the task board reader/writer implementation and for understanding sibling path projection.
- `state_machine.py`: useful for existing protocol state and write ownership checks.
- `preflight.py`: useful as a reference for later wrapper diagnostics if it can be routed to local paths.

## 3. Topic B — Codex Manager Session Bootstrap/Resume

Current CLI facts:

- `codex exec resume [SESSION_ID] [PROMPT]` resumes by UUID or thread name.
- If no session id is supplied, `--last` selects the most recent recorded session.
- `codex exec` supports `--json`, which should be tested in P0 EXECUTE for a stable session/thread id event.
- `codex exec` supports `-o/--output-last-message`, which should write the final Codex response to the report capture path.

Session id extraction recommendation:

- Primary: run bootstrap with `codex exec --json` and parse JSONL events for the stable session/thread id if this Codex version emits one.
- Secondary: parse clearly labeled stdout/stderr text only if the label is stable enough to test.
- Fallback: leave `session_id` null and record that the wrapper could not extract a stable id.
- Do not infer a session id from unrelated global files unless P0 explicitly approves and tests that behavior.

When `codex exec resume --last` is safe:

- Only after a bootstrap session is known to be the most recent Codex session for this repository.
- Only when no other Codex session has been created in this repository since the active Codex Manager bootstrap.
- The wrapper/report must record why `--last` cannot be confused with another session.
- If there is ambiguity, the wrapper should block and ask Claude for a fresh bootstrap or explicit session id.

`.agent-docs/teamwork/codex-manager-session.json` should record:

- `session_id`, nullable;
- `use_last_fallback`, boolean;
- `repo_root`;
- `active_milestone`;
- `current_stage`;
- `last_prompt_path`;
- `last_report_path`;
- `bootstrap_mode`, boolean;
- `dispatch_mode`, such as `bootstrap`, `resume-by-id`, or `resume-last`;
- `sandbox`;
- `codex_command_preview`;
- `updated_at`;
- `last_exit_code`;
- `last_dispatch_event_id` if messages are appended;
- notes explaining fallback or blockers.

Recommended bootstrap command shape for P0 EXECUTE:

```bash
codex exec \
  --json \
  -C /home/cz-jzb/workspace/vla-flywheel \
  -s workspace-write \
  -o .agent-docs/teamwork/reports/P0/EXECUTE.last.md \
  - < .agent-docs/teamwork/prompts/P0/EXECUTE.prompt.md
```

Recommended resume command shape after a stable id is known:

```bash
codex exec resume <codex-session-id> \
  -o .agent-docs/teamwork/reports/P0/<stage>.last.md \
  - < .agent-docs/teamwork/prompts/P0/<stage>.prompt.md
```

Recommended fallback shape when safe:

```bash
codex exec resume --last \
  -o .agent-docs/teamwork/reports/P0/<stage>.last.md \
  - < .agent-docs/teamwork/prompts/P0/<stage>.prompt.md
```

## 4. Topic C — GSD DISCUSS Smoke Criteria

Minimum evidence that GSD DISCUSS ran in this project context:

- Codex Manager reads the local Teamwork task board and required governance files.
- Codex Manager identifies the active milestone as `P0` and stage as `DISCUSS`.
- Codex Manager reads the `$gsd-discuss-phase` skill and active workflow rules.
- Codex Manager records that stock GSD `.planning` output is auxiliary and not authoritative for GenesisVLA progress.
- If `.planning/` is absent, the report records the limitation and avoids creating unauthorized `.planning` files during this read-only DISCUSS.
- The report answers P0 wrapper, session, smoke-loop, and layout questions.
- The final response includes a structured `===HANDOFF===` block returning control to Claude.

`DISCUSS.md` must contain:

- investigation summary;
- answers to Topics A, B, C, and D;
- decisions made during DISCUSS;
- open questions for Claude;
- risk list;
- recommended next stage action;
- list of files affected;
- clear note that PLAN/EXECUTE did not start.

Valid P0 handoff shape:

```text
===HANDOFF===
Completed:
- Read required governance and Teamwork files.
- Ran requested read-only investigation commands.
- Structured P0 DISCUSS findings with gsd-discuss-phase rules.
- Wrote .agent-docs/teamwork/reports/P0/DISCUSS.md.

Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- PLAN must define the wrapper implementation and validation plan.

Decisions:
- Wrapper belongs at scripts/teamwork/dispatch_codex_manager.py.
- .agent-docs/teamwork/ remains authoritative supervisor state.
- .planning artifacts are auxiliary only and were not created in DISCUSS.

Files Affected:
- .agent-docs/teamwork/reports/P0/DISCUSS.md (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
```

## 5. Topic D — Repository Layout Inspection

`scripts/teamwork/` does not exist.

Cleanest creation path for P0 EXECUTE:

```text
scripts/teamwork/
  dispatch_codex_manager.py
```

Rationale:

- `scripts/` is already the project-local script root.
- Existing `scripts/slurm/` and `scripts/maintenance/` show task-specific script subdirectories are accepted in this checkout.
- A Teamwork wrapper is operational project tooling, not StarVLA model source, so it naturally belongs under `scripts/teamwork/`.

Existing Teamwork plumbing in this repository:

- Local Teamwork state exists under `.agent-docs/teamwork/`.
- `codex-manager-session.json` already records bootstrap metadata with `session_id: null`.
- `prompts/P0/DISCUSS.prompt.md` exists and matches the current assignment.
- `workspace/task-board.md` marks P0 DISCUSS as active and assigned to Codex.
- `next-actor.json` currently marks Codex as next actor for this dispatch.

Conflicts between governance overlay and StarVLA structure:

- No direct source-layout conflict was found during DISCUSS.
- The governance overlay uses `.agent-docs/`, `.agents/`, `.codex/`, `datasets/`, `runs/`, and related local-only directories. These are intended local governance/runtime roots, not StarVLA baseline source paths.
- The main operational gap is that the approved wrapper path is governance-defined but not implemented yet.
- A smaller permission mismatch exists: P0 acceptance expects `next-actor.json` to end with Claude after Codex handoff, but this DISCUSS assignment only explicitly allowed writes to `DISCUSS.md`, `messages.jsonl`, `claude-inbox.md`, and `workspace/task-board.md`. PLAN should clarify whether P0 EXECUTE/VERIFY may update `next-actor.json` directly or only through the wrapper/global teammate scripts.

## 6. Decisions Made During DISCUSS

- P0 remains the active prerequisite before M0.
- DISCUSS remains read-only for source code and does not implement the wrapper.
- The wrapper should be a Python CLI at `scripts/teamwork/dispatch_codex_manager.py`.
- The wrapper must route all project-specific Teamwork state under `.agent-docs/teamwork/`.
- The wrapper should support dry-run/command preview as first-class behavior for Claude testing.
- The wrapper must use `codex exec` only for bootstrap and `codex exec resume` for normal continuation.
- `codex exec resume --last` is acceptable only when repository-local session ambiguity is ruled out and recorded.
- Session id extraction should be tested through `codex exec --json` before relying on text parsing or fallback.
- Stock GSD `.planning/` artifacts are not authoritative for GenesisVLA progress and were not created in this DISCUSS stage.

## 7. Open Questions For Claude

- Should P0 PLAN authorize direct writes to `.agent-docs/teamwork/next-actor.json`, or require all `next-actor` updates to flow through the wrapper/Teamwork scripts?
- Should the wrapper create prompt files, require Claude to pre-create them, or support both with an explicit `--prompt-path` override?
- Should P0 EXECUTE include unit tests for the wrapper path validation and dry-run command rendering, or is a dry-run plus local smoke sufficient for P0?
- Should the wrapper treat `DISCUSS` and `PLAN` as prompt-constrained read-only stages while still invoking `codex exec -s workspace-write`, or should it use `-s read-only` and rely on Claude to collect reports another way?
- Should the wrapper write `.last.md` only, then require Codex to write the canonical stage report, or should the wrapper copy/promote `.last.md` to the canonical report path after successful completion?

## 8. Risks

- Session id extraction may not be stable across Codex CLI versions unless `--json` exposes a durable id event.
- `resume --last` can attach to the wrong session if another Codex session is created in the same repository.
- The global teammate scripts are usable, but the wrapper must prove they route all project-specific writes to `.agent-docs/teamwork/`.
- The current stock GSD setup has no `.planning/ROADMAP.md`; running the full GSD discuss workflow without adaptation would create auxiliary files outside this DISCUSS write scope.
- P0 acceptance mentions `next-actor.json`, but the current DISCUSS write scope did not explicitly include that file.
- A wrapper that does too much could bypass Claude gates; P0 PLAN must keep it as dispatch/routing infrastructure only.

## 9. Recommended Next Stage Action

Recommend `start_plan`.

The PLAN stage should produce a narrow implementation and validation plan for:

- creating `scripts/teamwork/dispatch_codex_manager.py`;
- validating path routing under `.agent-docs/teamwork/`;
- testing bootstrap metadata updates in `.agent-docs/teamwork/codex-manager-session.json`;
- testing `codex exec --json` session id extraction or documenting fallback;
- proving the wrapper does not choose milestones, approve gates, run Slurm, commit, push, or open PRs;
- defining the exact evidence required for P0 EXECUTE, VERIFY, and REVIEW.

Do not advance to EXECUTE until Claude reviews and approves the PLAN.

## 10. Files Affected

- `.agent-docs/teamwork/reports/P0/DISCUSS.md` (written)

No source code, scripts, tests, configs, datasets, checkpoints, Slurm files, or StarVLA baseline paths were modified.

===HANDOFF===
Completed:
- Read required governance and Teamwork files.
- Ran requested read-only repository, Teamwork-script, and Codex CLI investigation commands.
- Read and applied `$gsd-discuss-phase` workflow rules for the formal DISCUSS structure.
- Confirmed `scripts/teamwork/dispatch_codex_manager.py` does not exist yet.
- Defined wrapper, session bootstrap/resume, GSD smoke-loop, and repository-layout acceptance criteria.
- Wrote `.agent-docs/teamwork/reports/P0/DISCUSS.md`.

Pending:
- Claude gate decision: continue_discuss | start_plan | block_for_user | pause.
- PLAN must define wrapper implementation scope, tests, path permissions, and validation evidence.
- PLAN must resolve whether `next-actor.json` updates are directly authorized or only wrapper-mediated.

Decisions:
- P0 remains prerequisite and M0 must not start yet.
- Wrapper should be a Python CLI at `scripts/teamwork/dispatch_codex_manager.py`.
- `.agent-docs/teamwork/` remains authoritative supervisor state.
- `.planning/` artifacts are auxiliary only and were not created during DISCUSS.
- `codex exec` is for bootstrap; `codex exec resume` is for normal continuation; `resume --last` requires recorded no-ambiguity conditions.

Files Affected:
- `.agent-docs/teamwork/reports/P0/DISCUSS.md` (written)

Next-Actor-Notes:
Returning control to Claude Supervisor. Awaiting gate decision: continue_discuss | start_plan | block_for_user | pause.
Next actor: Claude.
===END HANDOFF===
