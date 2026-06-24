# codex-thread-team

`codex-thread-team` is a Codex skill for coordinating real Codex worker threads from one leader thread.

It turns a large, parallelizable coding task into a small-team workflow: the current thread acts as the leader, creates isolated worker threads, gives each worker a bounded task and branch, polls progress, collects committed reports, merges branches serially, and performs the final whole-task review.

## What this skill is for

Use this skill when a task is large enough that real parallel worker threads can save time without creating more coordination cost than value.

Good fits include:

- independent backend, frontend, migration, documentation, or test workstreams;
- branch-isolatable changes with low file overlap;
- tasks where the leader can define stable contracts before workers begin;
- work where serial merge and per-merge verification will make integration safer.

Poor fits include:

- small one-person edits;
- vague requests that cannot be split responsibly yet;
- tight refactors across the same core files;
- work where one continuous context is more valuable than parallel throughput.

The skill is intentionally conservative: it first evaluates whether thread-team execution is worth it, and recommends direct single-thread execution when parallelism would mostly add overhead.

## Collaboration model

This skill treats Codex threads like a small engineering team, not a pool of interchangeable agents.

The leader thread owns the work as a whole. It analyzes the task, decides whether parallelism is justified, defines task boundaries, creates worker threads, assigns branches and worktrees, makes team-wide decisions, coordinates blockers, serially integrates worker branches, and performs the final review. The leader does not disappear after delegation; it remains accountable for the final result.

Each worker thread owns one bounded responsibility. A worker gets one task boundary, one branch, and one isolated working directory. It may collaborate with peer workers for interface details or dependency questions, but it must escalate shared-contract changes, cross-responsibility issues, unresolved blockers, and completion back to the leader.

The collaboration model is deliberately asymmetric:

- **Leader decides and integrates**: architecture, public APIs, data model changes, merge order, conflict handling, and final correctness stay with the leader.
- **Workers execute scoped work**: workers implement, self-review, verify, commit, and report within their assigned boundary.
- **Peers coordinate, but do not govern**: workers may talk to each other, but peer agreement does not replace leader approval for team-wide decisions.
- **Parallelism is earned**: the workflow only creates workers when task boundaries, branch isolation, and acceptance criteria are clear enough to justify coordination overhead.

The goal is not simply to run more Codex instances. The goal is to make parallel Codex work behave more like disciplined engineering collaboration: clear ownership, explicit contracts, isolated workspaces, structured reporting, serial integration, and final accountability.

## Requirements

This skill expects Codex app thread-management capabilities:

- `create_thread`
- `send_message_to_thread`
- `read_thread`
- optionally `list_threads`, `set_thread_title`, `set_thread_archived`, `fork_thread`, and heartbeat automations

For repository-scoped work, each worker must have an exclusive working directory, preferably created through a Codex project worktree. A branch alone is not enough isolation.

Worker thread creation follows the active Codex tool schema. The skill does not force a specific worker model; it uses the user's configured default unless the user explicitly requests a model override.

## Installation

Clone this repository into your Codex skills directory as `thread-team`:

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/itmada/codex-thread-team.git "${CODEX_HOME:-$HOME/.codex}/skills/thread-team"
```

To update an existing install:

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/thread-team"
git pull
```

## Usage

Ask Codex to use the skill explicitly:

```text
Use $thread-team to split this task across a leader thread and collaborating worker threads.
```

Or describe a task that is clearly large, parallelizable, and branch-isolatable. In that case the skill should first propose thread-team mode instead of immediately creating workers.

Example prompts:

```text
Use $thread-team to implement the new billing settings page. Split backend API work, frontend UI work, and tests across workers.
```

```text
Use $thread-team to parallelize this migration: one worker handles schema changes, one updates the data access layer, and one updates tests/docs.
```

## Workflow

The skill enforces a six-phase leader workflow:

1. **Deep task analysis and parallel split**
   The leader inspects the task, checks whether parallel work is justified, defines boundaries, and records initial state.

2. **Worker thread initialization**
   The leader creates real worker threads, assigns worker branches, and ensures each worker has an isolated working directory.

3. **Per-worker deep task design and dispatch**
   The leader writes a self-contained dispatch for each worker, including scope, non-goals, contracts, verification, commit expectations, and report format.

4. **Progress polling and collaboration decisions**
   The leader runs a startup gate, verifies each worker has started in the expected `pwd`, branch, and HEAD, then uses heartbeat polling when delayed checks are appropriate.

5. **Report collection and merge orchestration**
   Workers self-review, verify, commit, and report. The leader merges worker branches one at a time and verifies after each merge.

6. **Final leader review and repair**
   The leader performs the whole-task review, fixes integration issues if needed, verifies again, and confirms cleanup.

## Safety model

The skill is built around a few guardrails that prevent common multi-thread failures:

- **Preflight viability check**: worker threads are not created unless parallelism is likely to beat direct execution.
- **Workspace isolation**: every worker must operate in its own working directory; two workers must never share a checkout.
- **Deterministic branch names**: worker branches use `worker-<short-task>-<worker-role>`.
- **Startup verification**: after dispatch, each worker must confirm actual `pwd`, branch, and HEAD before the leader treats workspace isolation as verified.
- **Persistent leader state**: the leader records roster, branches, worktrees, decisions, reports, merge order, heartbeat state, and cleanup state in `.thread-team/state.md`.
- **Structured worker completion**: a worker is not complete until it self-reviews, fixes findings, verifies, commits, and sends a completion report.
- **Serial integration**: the leader merges one worker branch at a time and verifies after each merge.
- **Heartbeat cleanup**: any heartbeat automation created by the workflow must be deleted before the workflow ends or exits early.

## Repository layout

```text
thread-team/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── final-report-template.md
    ├── leader-state-template.md
    ├── status-template.md
    ├── worker-dispatch-template.md
    ├── worker-registration-template.md
    └── worker-report-template.md
```

## Reference templates

- `references/worker-registration-template.md` registers a worker before the full task dispatch is ready.
- `references/worker-dispatch-template.md` gives a worker its full task boundary, verification plan, and completion requirements.
- `references/worker-report-template.md` standardizes worker completion reports.
- `references/leader-state-template.md` defines the leader's persistent coordination record.
- `references/status-template.md` standardizes user-facing progress updates.
- `references/final-report-template.md` standardizes final leader handoff after integration and review.

## Development notes

- Keep `SKILL.md` focused on instructions Codex needs while running the workflow.
- Put reusable prompt/report/state formats in `references/`.
- Do not replace real Codex worker threads with temporary subagents when thread tools are available.
- When updating thread-tool behavior, follow the active Codex tool schema rather than hard-coding model or runtime defaults.
- Avoid deleting and recreating existing files during maintenance; prefer small diffs so template history stays easy to review.
