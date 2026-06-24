# GenesisVLA Local Teamwork Supervisor Protocol

## Purpose

This protocol defines how Claude Code and Codex CLI collaborate on GenesisVLA milestones inside this repository.

The default operating model is:

```text
Claude Supervisor
  -> selects one GenesisVLA milestone node
  -> dispatches or resumes one long-lived Codex Manager through Teamwork
      -> Codex Manager runs one GSD stage
      -> Codex Manager launches Claude-approved Codex workers according to the minimum worker coverage policy
      -> Codex Manager consults Claude through local Teamwork when blocked
      -> Codex Manager returns a structured report and handoff
  -> Claude reviews the result
  -> Claude decides the next stage
```

The goal is to use Claude Code for long-context planning, worker-plan approval, supervision, and gate decisions, while Codex Manager preserves local repository context, coordinates worker subagents, performs bounded investigation, GSD discussion, implementation, verification, and reporting.

## Local-Only State

All project-specific Teamwork state must stay inside this repository under:

```text
.agent-docs/teamwork/
  roadmap_progress.md
  codex-manager-session.json
  claude_supervisor_usage.md
  teamwork_supervisor_protocol.md
  messages.jsonl
  claude-inbox.md
  next-actor.json
  workspace/task-board.md
  reports/<milestone-id>/<stage>.md
```

This directory is covered by `.agent-docs` in `.gitignore`. It is local-only by default and must not be committed, pushed, or published unless the user explicitly changes that policy.

The global `~/.claude/skills/teammate/` installation may be used as the implementation provider, but project-specific task boards, inboxes, reports, and progress records must be routed to `.agent-docs/teamwork/`.

## Codex Manager Session

GenesisVLA supervision uses one long-lived Codex Manager session by default.

Claude starts a new Codex Manager session only when bootstrapping the local supervisor loop, intentionally retiring the previous Manager after a handoff summary, or recovering from an unavailable or corrupted session.

All normal follow-up dialogue should use `codex exec resume <codex-session-id>` so Codex Manager keeps repository context, stage history, worker outputs, validation evidence, and risk notes connected across turns.

Codex Manager dispatch must explicitly set the Manager model and reasoning effort. The default GenesisVLA Manager profile is `model=gpt-5.5` and `model_reasoning_effort=xhigh`. If Claude chooses a different model or effort for a stage, the dispatch metadata and stage report must explain why.

The active session metadata belongs in:

```text
.agent-docs/teamwork/codex-manager-session.json
```

If a wrapper cannot extract a stable session id, `codex exec resume --last` may be used only when no other Codex session has been created in this repository since the active Manager session.

The approved project-local wrapper path is:

```text
scripts/teamwork/dispatch_codex_manager.py
```

The wrapper handles prompt generation, local Teamwork paths, Codex bootstrap/resume, explicit Manager model/effort flags, session metadata, and dispatch logs. It does not choose milestones, approve gates, execute Slurm jobs, commit, push, or bypass Claude review.

## GSD Artifact Mapping

`.agent-docs/teamwork/` is the authoritative GenesisVLA supervisor state.

GSD-native artifacts such as `.planning/`, `PLAN.md`, `STATE.md`, `CONTINUE.md`, or `.continue-here.md` may exist as temporary or auxiliary outputs. They are not accepted project direction until Codex Manager summarizes them into the stage report and Claude reviews the report.

Codex Manager must list created or modified GSD-native artifacts in the handoff and write the supervisor-facing summary under:

```text
.agent-docs/teamwork/reports/<milestone-id>/<stage>.md
```

Claude decides whether any GSD-native artifact changes should influence `roadmap_progress.md`.

## Pause, Resume, And Thread Authority

GSD pause, resume, and thread artifacts are auxiliary context, not project authority.

`$gsd-pause-work`, `$gsd-resume-work`, and `$gsd-thread` may preserve or restore discussion context across sessions, but they must not directly update `roadmap_progress.md`, advance a stage, approve a plan, approve execution, mark verification accepted, or set feature/milestone completion state.

Codex Manager must summarize relevant pause/resume/thread material into the current Teamwork stage report and handoff. Claude decides whether that recovered context changes project direction, stage status, or roadmap progress.

## Milestone Granularity

One GenesisVLA small milestone maps to one local Teamwork task.

The first local Teamwork task is `P0: GenesisVLA supervision bootstrap prerequisite`. `P0` must validate the project-local Teamwork wrapper, Codex Manager bootstrap/resume behavior, and interactive GSD handoff loop before Claude starts `M0`. Wrapper testing belongs inside `P0`; it is not a separate pre-`P0` task.

Each task may contain multiple supervised stages:

```text
DISCUSS -> PLAN -> EXECUTE -> VERIFY -> REVIEW
```

The stages are serial. Codex must not skip stages or advance itself across Claude gates.

## Minimum Worker Coverage

Starting with `M1`, every milestone that changes source, scripts, configs, tests, quality gates, dataset/run/Slurm/model paths, or user-facing governance must maintain a worker coverage ledger.

The ledger is created in `PLAN`, updated in `EXECUTE`, checked in `VERIFY`, and closed in `REVIEW`. It must include:

- `DISCUSS`/`PLAN` read-only exploration worker usage, or a concrete skip reason;
- `EXECUTE` write-capable worker ownership for implementation changes;
- `VERIFY` independent read-only worker ownership, or Claude-run external validation evidence;
- `REVIEW` independent review evidence;
- any skipped worker category, why it was skipped, and what compensating evidence exists.

`EXECUTE` implementation changes must not be Manager-only. If the approved worker cannot run, Codex Manager must stop and hand back to Claude for plan revision.

`VERIFY` and `REVIEW` are evidence stages, not fix stages. Defects found there must return to `PLAN` or a scoped `EXECUTE` fix with a Claude-approved worker plan.

## Role Boundaries

### Claude Supervisor

Claude owns:

- reading the full GenesisVLA roadmap and local progress context;
- selecting the current milestone node;
- defining the current GSD stage and allowed scope;
- dispatching Codex Manager through Teamwork;
- approving the Codex worker plan for worker count, worker type, serial/parallel shape, writable/read-only paths, and stop condition;
- answering Codex consultations;
- approving, revising, or rejecting plans;
- deciding whether execution may start;
- deciding whether verification evidence is sufficient;
- updating project-level progress decisions.

Claude must not treat Codex output as accepted until the report and handoff are reviewed.

### Codex Manager

Codex owns:

- running exactly one assigned GSD stage at a time;
- inspecting the repository and relevant governance files;
- preserving the Manager context for repository state, worker outputs, validation evidence, and risk notes;
- launching only Claude-approved Codex workers when subagents are needed;
- reviewing worker outputs and retiring worker contexts before reporting back to Claude;
- asking Claude through Teamwork when scope, architecture, or acceptance is unclear;
- producing a stage report under `.agent-docs/teamwork/reports/<milestone-id>/`;
- ending each stage with a structured Teamwork handoff;
- obeying repository governance, including Manager-worker delegation rules for structural implementation.

Codex must not:

- ask the final user directly during a supervised Teamwork task unless Claude explicitly routes that question to the user;
- silently assume unresolved planning or acceptance decisions;
- advance from `DISCUSS` to `PLAN`, from `PLAN` to `EXECUTE`, or from `EXECUTE` to `VERIFY` without Claude approval;
- add extra workers, change worker types, widen write scopes, or run serial work in parallel without Claude approval;
- bypass the Manager-worker chain by delegating unmanaged implementation directly to leaf workers;
- write project-specific Teamwork records to the global home directory when a local board is configured.

## Stage Gates

### DISCUSS Gate

`DISCUSS` is interactive, not a single-shot report.

Codex should use local Teamwork consultation when it needs:

- architecture direction;
- milestone scope clarification;
- acceptance criteria;
- conflict resolution between roadmap and repository governance;
- decision about whether to involve the user.

The `DISCUSS` stage ends only when Codex produces:

- discussion summary;
- decisions already made;
- open questions;
- risk list;
- recommended next stage;
- structured handoff.

Claude reviews the discussion report and decides whether to continue discussion, start planning, or block for user input.

### PLAN Gate

Codex may draft a plan, but the plan is not executable until Claude approves it.

The `PLAN` stage report must include:

- milestone objective;
- in-scope and out-of-scope work;
- affected paths;
- implementation sequence;
- required worker coverage ledger, worker plan, and Manager-worker policy;
- validation plan;
- rollback notes;
- risks and assumptions.

Claude must review the plan and choose one of:

```text
approve_execute
revise_plan
continue_discuss
block_for_user
pause
```

### EXECUTE Gate

Execution starts only after Claude approves the plan.

Codex Manager must execute only the approved scope. Structural implementation, code modification, config-contract changes, dataset execution changes, Slurm wrapper changes, debugging fixes, and model-path implementation must follow the Claude-approved worker plan and repository Manager-worker rules.

Starting with `M1`, implementation `EXECUTE` stages must include at least one approved write-capable worker unless the report proves that no implementation change was made. Codex Manager may not patch implementation, test, config, quality-gate, Slurm, dataset, or model-path defects inline.

The `EXECUTE` stage report must include:

- changed files;
- commands run;
- worker coverage ledger update;
- validation evidence;
- unresolved issues;
- performance and complexity notes;
- rollback notes;
- next recommended stage.

### VERIFY Gate

Verification starts after execution or when Claude explicitly asks for validation.

Starting with `M1`, `VERIFY` for an implementation milestone must use an independent read-only worker such as `code_reviewer` or `slurm_validation_engineer`, or record Claude-run external validation evidence that replaces that worker.

The `VERIFY` stage report must include:

- checks run;
- pass/fail status;
- evidence paths;
- skipped checks and reasons;
- worker coverage ledger update;
- Slurm evidence when relevant;
- acceptance recommendation.

Claude decides whether to accept, request fixes, reopen planning, or pause.

### REVIEW Gate

`REVIEW` closes a stage or milestone after evidence has been collected.

Starting with `M1`, `REVIEW` must include independent review evidence and the final worker coverage summary. `REVIEW` must not make unplanned implementation edits. If review finds defects, Claude must reopen `PLAN` or dispatch a scoped `EXECUTE` fix.

`REVIEW` acceptance does not by itself complete a milestone. The user requires every completed milestone to be pushed and represented by a PR link. After Claude accepts `REVIEW` evidence, Claude must run the milestone publication gate before marking the milestone complete or advancing to the next milestone.

The `REVIEW` stage report must include:

- final milestone or stage synthesis;
- independent review evidence;
- final worker coverage summary;
- accepted risks;
- rollback notes;
- publication readiness status;
- next milestone recommendation or stop condition.

### Milestone Publication Gate

Before a milestone is marked complete, Codex Manager must provide Claude with:

- `.agent-docs/git_workflow.md` scan evidence;
- current `dev/*` branch name;
- commit SHA containing the milestone deliverables;
- pushed branch name;
- PR URL;
- PR title and target branch;
- any skipped scan with reason, if Claude accepts the skip;
- publication risks or blockers.

If push or PR creation is blocked by network, credentials, repository permissions, remote state, or scan failures, the milestone status becomes `ready_to_publish_blocked`, not complete. Claude must not start the next milestone until the blocker is resolved or the user explicitly changes the completion rule.

The PR must not include local-only Teamwork state or ignored governance overlays unless the user explicitly asks to publish those files. Do not merge the PR unless the user explicitly requests review and merge.

## Local Teamwork Files

### `workspace/task-board.md`

The local task board is the current task state.

It should contain:

- mission;
- active GenesisVLA milestone task;
- current stage;
- next actor;
- recent comm log;
- shared context and decisions.

### `messages.jsonl`

The local message log stores structured Teamwork events.

It is append-only for normal operation.

### `claude-inbox.md`

Codex writes consultations for Claude here.

Claude reads this file before deciding whether to continue, revise, or stop.

### `next-actor.json`

This file prevents uncontrolled simultaneous action.

Allowed values:

```text
Claude
Codex
User
Blocked
```

If `next-actor` is `Claude`, Codex must stop unless explicitly dispatched again.

### `roadmap_progress.md`

This file is Claude's project-level memory for GenesisVLA supervision.

It is the only progress authority for active milestone and stage state. GSD pause/resume/thread files can inform it only after Claude review.

It records:

- active milestone;
- stage status;
- major decisions;
- completed reports;
- next proposed action;
- user-level blockers.

## Required Handoff Shape

Every Codex stage must end with:

```text
===HANDOFF===
Completed:
- ...

Pending:
- ...

Decisions:
- ...

Files Affected:
- ...

Next-Actor-Notes:
...
===END HANDOFF===
```

The handoff must identify the intended next actor.

## Codex Worker Types

Claude may approve these worker types under the Codex Manager. Codex Manager may propose them during `PLAN`, but may not exceed the approved worker plan during `EXECUTE`.

### Read-Only Workers

- `explorer`: repository/code/config/doc inspection with no writes.
- `code_reviewer`: correctness, performance, baseline, dataset, Slurm, and governance review with no writes.
- `cleanup_proposal_agent`: deletion inventory and cleanup proposal with no deletion.
- `daily_task_planner`: operational planning for cleanup, dataset placement, git hygiene, storage transfer, or execution-state changes.
- `research_planner`: related-assets analysis and implementation/validation decomposition.
- `slurm_validation_engineer`: Slurm dry-run, job evidence, log, and output triage.

### Write-Capable Workers

- `coding_integration_engineer`: localized integration, code-input integration, config/script edits, and narrow GenesisVLA/StarVLA framework changes.
- `coding_heavy_engineer`: architecture-heavy, model-path, dataset-chain, Slurm-wrapper, performance, multi-file, or high-risk implementation.
- `slurm_environment_discovery_agent`: Slurm discovery and approved config/evidence updates when active config contains `TO_FILL`.
- `external_transfer_agent`: one-time user-authorized external path transfer into project-governed destinations.

### Worker Selection Rules

- Keep the worker set as small as possible.
- Use read-only workers before write-capable workers when uncertainty is high.
- Use `coding_integration_engineer` for narrow implementation.
- Use `coding_heavy_engineer` for shared contracts, model paths, dataset chains, Slurm wrappers, or performance-sensitive work.
- Parallel workers require independent scopes and non-overlapping write paths.
- Shared files, shared config contracts, baseline paths, dataset execution chains, model execution paths, and Slurm wrappers stay serial unless Claude explicitly approves a safe split.
- Starting with `M1`, implementation `EXECUTE` requires a write-capable worker, `VERIFY` requires an independent read-only worker or Claude external validation evidence, and `REVIEW` requires independent review evidence.
- If a worker category is skipped, the stage report must record the skip reason and compensating evidence.

## Wrapper Design Requirement

A project-local wrapper should call the global Teamwork scripts while forcing all project-specific paths into `.agent-docs/teamwork/`.

The wrapper must provide:

- local board path;
- local inbox path;
- local message log path;
- local next-actor path;
- milestone id;
- stage name;
- report output path;
- Codex read-only flag for `DISCUSS` and `PLAN` unless Claude authorizes writes.

The wrapper must also patch or override prompt instructions so Codex sees the local `consult_claude.py --board .agent-docs/teamwork/workspace/task-board.md` command instead of the global default board.

## Anti-Loop Rules

- Codex may consult Claude, but may not recursively start a new high-level supervisor loop.
- Claude may dispatch Codex, but only one assigned GSD stage at a time for a milestone.
- If the same blocker repeats twice, the next actor becomes `User`.
- If a stage exceeds the approved scope, Claude must return to `PLAN` or `DISCUSS`.
- If local Teamwork state conflicts with repository governance, repository governance wins.

## Current Decision

The adopted operating mode is:

```text
Claude-started primary flow
Codex-started only as bootstrap or fallback
project-local Teamwork records under .agent-docs/teamwork/
one GenesisVLA small milestone per local Teamwork task
Plan must stop for Claude review before execution
Milestone complete requires pushed PR URL
```
