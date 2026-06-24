# Claude Supervisor Usage Guide

## Purpose

This guide tells Claude Code how to operate GenesisVLA supervision through Codex Manager and local Teamwork.

`CLAUDE.md` is the rule entrypoint. This file is the runbook: what Claude should read, decide, dispatch, review, and record during a milestone.

## Operating Model

Use this chain for all supervised GenesisVLA work:

```text
Claude Supervisor
  -> selects one GenesisVLA milestone node
  -> selects one stage: DISCUSS, PLAN, EXECUTE, VERIFY, or REVIEW
  -> dispatches or resumes one long-lived Codex Manager through Teamwork
      -> Codex Manager keeps repository and stage context
      -> Codex Manager runs GSD commands when assigned
      -> Codex Manager launches only Claude-approved Codex workers
      -> Codex Manager writes report and handoff
  -> Claude reviews report and decides the next gate
```

Do not dispatch unmanaged leaf workers directly from Claude. The Codex Manager layer is required so repository context, worker outputs, validation evidence, and risk notes stay in one place.

## Minimum Worker Coverage

Starting with `M1`, every milestone that changes source, scripts, configs, tests, quality gates, dataset/run/Slurm/model paths, or user-facing governance must carry a worker coverage ledger.

The ledger must be created during `PLAN` and updated through `EXECUTE`, `VERIFY`, and `REVIEW`:

- `DISCUSS` / `PLAN`: record read-only exploration workers, or record why exploration was unnecessary.
- `EXECUTE`: assign at least one write-capable worker for implementation changes.
- `VERIFY`: assign an independent read-only worker, or record Claude-run external validation evidence.
- `REVIEW`: record independent review evidence and close the ledger.

If a required worker cannot run, do not let Codex Manager silently continue as the implementer. Revise the worker plan, split the scope, or pause.

`VERIFY` and `REVIEW` must not become fix stages. Defects found there return to `PLAN` or scoped `EXECUTE` with an approved worker plan.

## First Milestone

Start with `P0: GenesisVLA supervision bootstrap prerequisite`.

`P0` is complete only after Claude has reviewed evidence that:

- project-specific Teamwork files are created and read under `.agent-docs/teamwork/`;
- Claude has tested the project-local Teamwork wrapper path as part of `P0`, not as a pre-`P0` discussion requirement;
- Codex Manager can be bootstrapped once and then resumed through recorded session metadata;
- Codex Manager can run an interactive GSD `DISCUSS` loop, write `.agent-docs/teamwork/reports/P0/DISCUSS.md`, and return a structured handoff.

Do not start `M0` until `P0` has completed `REVIEW` and Claude accepts the prerequisite evidence.

## Codex Manager Session

Use one long-lived Codex Manager session for the GenesisVLA supervised project.

Start a new Codex Manager session only when:

- bootstrapping the local supervisor loop for the first time;
- explicitly retiring the previous Codex Manager session after a handoff summary;
- recovering from an unavailable, corrupted, or intentionally reset Codex session.

After bootstrap, Claude should continue the same Codex Manager with:

```bash
codex exec resume \
  -m gpt-5.5 \
  -c 'model_reasoning_effort="xhigh"' \
  <codex-session-id> \
  -o .agent-docs/teamwork/reports/<milestone-id>/<stage>.last.md \
  - < .agent-docs/teamwork/prompts/<milestone-id>/<stage>.prompt.md
```

Bootstrap uses `codex exec` once:

```bash
codex exec \
  -C /home/cz-jzb/workspace/vla-flywheel \
  -s workspace-write \
  -m gpt-5.5 \
  -c 'model_reasoning_effort="xhigh"' \
  -o .agent-docs/teamwork/reports/<milestone-id>/<stage>.last.md \
  - < .agent-docs/teamwork/prompts/<milestone-id>/<stage>.prompt.md
```

Store active session routing metadata in:

```text
.agent-docs/teamwork/codex-manager-session.json
```

The session file should record:

- session id, if the wrapper can extract it;
- repository root;
- active milestone;
- current stage;
- Codex Manager model;
- Codex Manager reasoning effort;
- last prompt path;
- last report path;
- updated timestamp;
- whether `--last` fallback is being used.

If no stable session id has been extracted yet, `codex exec resume --last` is allowed only when no other Codex session has been created in this repository since the active Codex Manager session.

Use this project-local wrapper path when it exists:

```text
scripts/teamwork/dispatch_codex_manager.py
```

The wrapper should:

- create prompt and report paths under `.agent-docs/teamwork/`;
- force Teamwork board, inbox, message log, next-actor, and reports into project-local paths;
- choose `codex exec` for bootstrap and `codex exec resume` for continuation;
- pass `-m gpt-5.5` and `-c 'model_reasoning_effort="xhigh"'` unless Claude explicitly records a different Manager model profile for the stage;
- update `.agent-docs/teamwork/codex-manager-session.json`;
- append dispatch metadata to `.agent-docs/teamwork/messages.jsonl`.

The wrapper must not:

- choose the milestone;
- approve the next stage;
- execute Slurm jobs;
- commit, push, or open PRs;
- bypass Claude gates.

## GSD Artifact Mapping

Use `.agent-docs/teamwork/` as the authoritative supervisor state.

GSD may create native artifacts such as:

```text
.planning/
PLAN.md
STATE.md
CONTINUE.md
.continue-here.md
```

These files are allowed as temporary or auxiliary GSD outputs. They do not directly update GenesisVLA progress.

Codex Manager must convert stage-relevant content into:

```text
.agent-docs/teamwork/reports/<milestone-id>/<stage>.md
```

The report must list any GSD-native artifacts created or updated.

Claude should review `.agent-docs/teamwork/roadmap_progress.md`, `messages.jsonl`, `next-actor.json`, and the stage report before looking at `.planning/` artifacts.

Only Claude may decide whether information from `.planning/` becomes accepted GenesisVLA direction.

## Pause, Resume, And Thread Authority

Use GSD pause/resume/thread commands only as context continuity tools:

```text
$gsd-pause-work
$gsd-resume-work
$gsd-thread
```

These commands may preserve or restore working context, but they do not directly update GenesisVLA progress. They must not advance stages, approve plans, approve execution, accept verification, set `passes: true`, or modify `.agent-docs/teamwork/roadmap_progress.md`.

Codex Manager must summarize any relevant pause/resume/thread output into the current stage report. Claude reviews that summary and decides whether it affects roadmap progress.

## Before Dispatch

Before dispatching Codex Manager, Claude must read:

1. `CLAUDE.md`
2. `AGENTS.md`
3. `boundaries.txt`
4. `.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
5. `.agent-docs/teamwork/teamwork_supervisor_protocol.md`
6. `.agent-docs/teamwork/roadmap_progress.md`

If the milestone touches datasets, Slurm, cleanup, external paths, code-input, related-assets, model integration, or execution behavior, also read the matching `.agent-docs/` policy file listed in `AGENTS.md`.

## Selecting Work

Pick exactly one GenesisVLA milestone node or smaller sub-node.

The selected work must include:

- milestone id and title;
- current stage;
- objective;
- in-scope paths;
- out-of-scope paths;
- required policies;
- expected report path;
- stop condition;
- next actor after handoff.

If the node is too large, split it before dispatch. One local Teamwork task should map to one small GenesisVLA milestone or sub-node.

## Stage Usage

### DISCUSS

Use `DISCUSS` when scope, architecture, acceptance criteria, risk, or StarVLA/GenesisVLA boundary decisions are unclear.

Recommended GSD command:

```text
$gsd-discuss-phase
```

Optional precursor:

```text
$gsd-spec-phase
```

Use `$gsd-spec-phase` first when the deliverable itself is ambiguous.

Claude should review the DISCUSS report and decide:

```text
continue_discuss
start_plan
block_for_user
pause
```

### PLAN

Use `PLAN` after discussion has enough decisions.

Recommended GSD command:

```text
$gsd-plan-phase
```

For important architecture or model-path work, add:

```text
$gsd-plan-review-convergence
```

Starting with `M1`, the plan must include a worker coverage ledger and worker plan:

- worker count;
- worker types;
- serial or parallel shape;
- writable/read-only paths;
- validation responsibility;
- independent review responsibility;
- skip reasons and compensating evidence for any omitted worker category;
- stop condition for each worker.

Claude must approve the plan and worker plan before execution.

### EXECUTE

Use `EXECUTE` only after Claude approves the plan and worker plan.

Recommended GSD command:

```text
$gsd-execute-phase
```

Codex Manager must not add workers, change worker type, widen write scope, or parallelize serial work without Claude approval.

Starting with `M1`, implementation `EXECUTE` must use the approved write-capable worker. Codex Manager may coordinate, review, and validate, but must not patch implementation, test, config, quality-gate, Slurm, dataset, or model-path changes inline.

### VERIFY

Use `VERIFY` after execution or when evidence is needed before a gate decision.

Recommended GSD command:

```text
$gsd-verify-work
```

For code or config changes, also consider:

```text
$gsd-code-review
$gsd-add-tests
```

For Slurm-dependent work, verification is incomplete without job id, logs, outputs, and Manager review.

Starting with `M1`, implementation milestones require an independent read-only verification worker such as `code_reviewer` or `slurm_validation_engineer`, unless Claude records external validation evidence that replaces that worker. Any fix needed after verification must return to `EXECUTE`.

### REVIEW

Use `REVIEW` to close a stage or milestone.

Recommended GSD commands:

```text
$gsd-audit-milestone
$gsd-milestone-summary
$gsd-extract-learnings
```

Claude decides whether the milestone is accepted, needs more work, should pause, or should return to discussion.

Starting with `M1`, `REVIEW` must include independent review evidence and the final worker coverage ledger. Review must not make unplanned implementation edits; defects return to `PLAN` or scoped `EXECUTE`.

Local `REVIEW` acceptance is not final milestone completion. The user requires every completed milestone to be pushed and to provide a PR link. After accepting `REVIEW`, run the Milestone Publication Gate before marking the milestone complete or starting the next milestone.

### MILESTONE_PUBLICATION

Use this gate after local `REVIEW` acceptance.

Required outcome:

- required scans from `.agent-docs/git_workflow.md` recorded;
- milestone deliverables committed on a `dev/*` branch;
- branch pushed to the configured remote;
- PR opened or updated;
- PR URL recorded in the `REVIEW` report, `.agent-docs/teamwork/roadmap_progress.md`, and `workspace/task-board.md`;
- PR URL provided to Claude and the user.

If push or PR creation fails, mark the milestone `ready_to_publish_blocked` and record the exact blocker. Do not start the next milestone until the PR URL exists or the user explicitly changes the completion rule.

## GSD Command Selection

Use these commands as Claude-dispatched Codex Manager work, not as unmanaged side channels.

Primary chain:

```text
$gsd-spec-phase
$gsd-discuss-phase
$gsd-plan-phase
$gsd-plan-review-convergence
$gsd-execute-phase
$gsd-code-review
$gsd-verify-work
$gsd-audit-milestone
$gsd-milestone-summary
$gsd-ship
```

Context and mapping:

```text
$gsd-map-codebase
$gsd-graphify
$gsd-ns-context
```

AI/model design:

```text
$gsd-ai-integration-phase
$gsd-eval-review
$gsd-secure-phase
$gsd-validate-phase
```

Debug and recovery:

```text
$gsd-debug
$gsd-forensics
$gsd-audit-fix
```

Documentation and handoff:

```text
$gsd-docs-update
$gsd-extract-learnings
$gsd-pause-work
$gsd-resume-work
$gsd-thread
```

Treat `$gsd-pause-work`, `$gsd-resume-work`, and `$gsd-thread` as auxiliary context tools. They require Claude review before their content can affect `roadmap_progress.md`.

Avoid by default:

```text
$gsd-autonomous
$gsd-fast
$gsd-quick
$gsd-pr-branch
$gsd-new-project
```

Use `$gsd-ship` or a direct git/PR workflow for the milestone publication gate after local `REVIEW` acceptance. Outside milestone-completion publication, do not use `$gsd-ship` or `$gsd-pr-branch` unless the user explicitly asks for PR or remote publication.

Do not reintroduce parameter-space exploration workflows unless the user explicitly restores that governance area.

## Worker Plan Selection

Claude chooses Codex worker types. Codex Manager may propose a worker plan, but Claude must approve it before execution.

Read-only workers:

- `explorer`
- `code_reviewer`
- `cleanup_proposal_agent`
- `daily_task_planner`
- `research_planner`
- `slurm_validation_engineer`

Write-capable workers:

- `coding_integration_engineer`
- `coding_heavy_engineer`
- `slurm_environment_discovery_agent`
- `external_transfer_agent`

Use the smallest worker set that can safely complete the stage.

Prefer serial execution when work touches shared files, shared config contracts, baseline paths, dataset execution chains, model execution paths, or Slurm wrappers.

Parallel workers are allowed only when scopes are independent and write paths do not overlap.

## Teamwork Files

Project-local Teamwork state belongs under:

```text
.agent-docs/teamwork/
  roadmap_progress.md
  codex-manager-session.json
  messages.jsonl
  claude-inbox.md
  next-actor.json
  workspace/task-board.md
  reports/<milestone-id>/<stage>.md
```

Claude should update `.agent-docs/teamwork/roadmap_progress.md` after each gate decision.

Codex Manager should write reports under `.agent-docs/teamwork/reports/<milestone-id>/`.

Do not use global `~/.claude/skills/teammate/workspace/` as the GenesisVLA project state source when local state is configured.

## Dispatch Template

Use this shape when dispatching Codex Manager:

```text
Milestone: <id> - <title>
Stage: <DISCUSS|PLAN|EXECUTE|VERIFY|REVIEW>
Session: <bootstrap|resume>
Objective: <one concise objective>

Read first:
- AGENTS.md
- boundaries.txt
- CLAUDE.md
- .agent-docs/teamwork/teamwork_supervisor_protocol.md
- <stage-specific policy docs>

Allowed paths:
- <paths>

Disallowed paths:
- code-input/ unless explicitly authorized
- related-assets/ unless explicitly authorized
- datasets/readonly/
- assets/input/
- external paths
- secrets or credentials

GSD command:
- <one command or none>

Worker plan:
- Worker coverage ledger (M1+):
  - DISCUSS/PLAN exploration worker or skip reason
  - EXECUTE write-capable worker for implementation changes
  - VERIFY read-only worker or Claude external validation evidence
  - REVIEW independent review evidence
- <worker type, scope, paths, serial/parallel shape>

Expected report:
- .agent-docs/teamwork/reports/<milestone-id>/<stage>.md

Milestone publication requirement:
- If this dispatch follows accepted REVIEW, commit the milestone deliverables on dev/*, push the branch, open/update a PR, and report the PR URL.
- If PR publication is blocked, report ready_to_publish_blocked with exact blocker.

Stop condition:
- Stop after report and ===HANDOFF===.
- Next actor must be Claude unless user escalation is required.
```

## Review Checklist

Before allowing the next stage, Claude must check:

- Did Codex stay within the assigned stage?
- Did Codex use only approved GSD commands?
- Did Codex preserve the Manager-worker chain?
- Did Codex launch only approved workers?
- For M1+, did the report include the worker coverage ledger?
- For M1+, did EXECUTE implementation use an approved write-capable worker?
- For M1+, did VERIFY/REVIEW include independent evidence or an explicit Claude-approved replacement?
- Did Codex avoid Manager inline fixes during VERIFY/REVIEW?
- Did all writes stay within approved paths?
- Were datasets, runs, Slurm, external paths, and secrets handled under policy?
- Are validation results concrete, with skipped checks and residual risk stated?
- Does the report end with a clear handoff and next actor?
- If this is milestone completion, did Codex provide the pushed branch, commit SHA, and PR URL?
- If PR publication is blocked, is the status `ready_to_publish_blocked` with an actionable blocker?

If any answer is unclear, return to `DISCUSS`, revise the plan, or block for user input.
