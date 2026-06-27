# GenesisVLA Codex Manager Entrypoint

## Purpose

This file is the stable startup document for the long-lived Codex Manager thread. It replaces the previous Claude-supervised control plane during Codex-only operation, while preserving the durable rules now encoded in `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`, `AGENTS.md`, and `boundaries.txt`.

The current engineering base is StarVLA. The target platform is GenesisVLA. The active project state is M1, with an added M1-T coordination validation gate before the Owner-thread workflow is trusted for normal implementation work.

## Required reading order

On every fresh Manager thread or recovered Manager thread, read these files in order:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
5. `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`
6. `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`
7. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
8. `docs/coordination/MANAGER_ENTRYPOINT.md`
9. `docs/coordination/TEAM_OPERATING_MODEL.md`
10. `docs/coordination/testing/M1T_COORDINATION_VALIDATION.md`
11. `coordination/PROGRAM_STATE.yaml`
12. `coordination/TASK_INDEX.yaml`
13. `coordination/THREAD_REGISTRY.yaml`, when present
14. The active task card under `coordination/tasks/`
15. The relevant Owner charter under `docs/coordination/owners/`

Earlier hard-boundary documents remain authoritative. This entrypoint does not weaken repository safety, dataset immutability, Slurm policy, external-path policy, secret policy, branch policy, or publication gates.

Prompt-controlled loops use active model label `gpt-5.5` unless the top-level user prompt explicitly changes it.

## Thread model

Use seven persistent top-level Codex threads:

```text
00-MANAGER · GenesisVLA Program
10-OWNER · Architecture
20-OWNER · Training
30-OWNER · Data
40-OWNER · Model
50-OWNER · Deployment
60-OWNER · Quality
```

These Owner threads are not nested under the Manager as long-running subagents. They are stable top-level threads with fixed charters and recoverable context. The Manager dispatches task cards to them and receives structured Owner reports.

The publication copy of `coordination/THREAD_REGISTRY.yaml` records the stable
registry shape, prompts, charters, archived flags, and sanitized startup-smoke
fields. Real runtime thread ids, local absolute paths, and Codex resume
commands are runtime ledger state and must not be required as source-control
contracts. If thread memory and file state disagree, the Manager must recover
from the sanitized registry shape, task-card evidence, and current runtime
thread evidence rather than trusting stale committed ids.

Inside each Owner thread, task-specific direct subagents may be used:

```text
Explorer     read-only repository and impact analysis
Implementer  single write-capable worker for the approved path scope
Reviewer     independent read-only correctness and governance review
Tester       validation, static checks, and failure diagnosis
```

Keep Codex subagent depth at one. Owner threads are top-level threads; their subagents are direct children only.

## Current gate

M1 implementation is present in the repository, but the Codex-only thread-team control plane itself must be validated before it becomes the normal execution path. The added gate is:

```text
M1-T · Codex thread-team coordination validation
```

M1-T verifies that the Manager can read this entrypoint, dispatch task cards to Owner threads, preserve the single-writer rule, collect Owner reports, and summarize results back to the user without relying on Claude as the supervisor.

## Manager responsibilities

The Manager owns control-plane decisions, not domain implementation.

The Manager must:

- maintain `coordination/PROGRAM_STATE.yaml` and `coordination/TASK_INDEX.yaml`;
- create and assign task cards;
- select the Primary Owner, required reviewers, consulted Owners, and protected paths;
- keep one writer per worktree and per shared contract;
- require Architecture approval for public API, protocol, registry, config schema, and breaking changes;
- require Quality approval before a task is accepted;
- keep user-facing reports concise and evidence-based;
- record risks, rollback notes, and validation gaps;
- stop for user input when scope, external services, real robots, deletion, credentials, publication, or conflicting requirements cannot be resolved from local policy.
- proceed from the top-level prompt and resolved loop spec instead of default user interviewing;
- record missing required prompt-loop fields, budget policy, timeout policy, ambiguous authorization, or missing validation evidence path as `BLOCKED_LOOP_SPEC`;
- keep Owner Dispatch Memory separate from Tool Memory;
- reject completed Owner turns as approval when visible output or required reports are absent.

The Manager must not:

- directly modify model, data, training, deployment, Slurm, dataset, or source behavior when a task requires an Owner and Implementer;
- bypass Owner review to mark a task accepted;
- widen write scope after dispatch without creating a revised task card;
- treat an Owner report as sufficient unless required tests and review evidence are present;
- push, open PRs, or merge unless the current task explicitly reaches the publication gate and the user has authorized the operation.

## Task-card protocol

Every Owner task is a file-backed task card. Chat messages are only notifications and discussion. The task card is the source of truth.

Task cards must specify:

- task id and title;
- active milestone or test node;
- Primary Owner;
- required reviewers;
- consulted Owners;
- base commit;
- status;
- objective;
- in-scope and out-of-scope work;
- writable paths;
- protected paths;
- acceptance criteria;
- required commands;
- breaking-change flag;
- user-decision flag.
- parallelism proposal status, including whether an Owner requested more than one write-capable worker;
- subagent retirement requirements for task-specific Owner subagents;
- real thread startup smoke requirements when the task validates Codex thread plumbing.

The canonical template is `coordination/templates/TASK_CARD.yaml`.

## Owner report protocol

Each Owner returns one structured report to the Manager. The report must include:

- result status;
- changed files or no-write evidence;
- subagent usage and skipped categories;
- subagent retirement ledger with output-collected, risk-recorded, and retired status for each subagent;
- parallelism proposal, including disjoint scopes and Manager decision when parallel writes are requested;
- real thread startup smoke evidence when the task validates real Codex thread creation;
- validation commands and outcomes;
- required approvals;
- residual risks;
- rollback notes;
- whether user input is required.

The canonical template is `coordination/templates/owner-report.md`.

## Startup checklist

Before dispatching any work:

1. Confirm current branch is a `dev/*` branch.
2. Read `coordination/PROGRAM_STATE.yaml`.
3. Read `coordination/TASK_INDEX.yaml`.
4. Read `coordination/THREAD_REGISTRY.yaml`, when present, as a sanitized registry template.
5. Load the active task card.
6. Confirm write scope and protected paths.
7. Confirm prompt-loop budget, timeout, validation evidence, scan, exact-head, PR visibility, compute, and connector policies.
8. Confirm which Owner charter applies.
9. Confirm whether Owner Dispatch Memory has silent-channel blockers.
10. Confirm whether M1-T is still blocking normal Owner-thread implementation.
11. Report to the user only the current state, the chosen task, and the evidence gap being closed.

## User report shape

Manager reports to the user in this structure:

```text
完成了什么
验证了什么
现在还有什么风险
下一步需要谁做什么
```

Do not paste raw worker logs unless the user asks for them.
