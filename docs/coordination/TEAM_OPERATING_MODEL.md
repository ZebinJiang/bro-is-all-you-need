# GenesisVLA Codex Thread-Team Operating Model

## Operating principle

The Codex Manager is the single control-plane thread. Domain Owner threads are stable peer threads with fixed responsibility boundaries. Task-specific Explorer, Implementer, Reviewer, and Tester agents are short-lived direct subagents used only inside an Owner thread.

The purpose is to preserve long-context ownership without turning every implementation detail into a Manager concern.

Prompt-controlled loops preserve the active model label `gpt-5.5` unless the top-level user prompt explicitly changes it. The Manager proceeds from the top-level prompt and resolved loop spec, not from a default interview.

The publication copy of `coordination/THREAD_REGISTRY.yaml` tracks the stable
registry shape, prompts, charters, archived flags, and sanitized startup-smoke
fields. Real thread ids, local absolute paths, Codex session ids, and resume
commands are runtime ledger state and must not be required as source-control
contracts.

## Persistent threads

| Thread | Owner | Primary authority |
| --- | --- | --- |
| `00-MANAGER · GenesisVLA Program` | Manager | Program state, task cards, dependencies, user reporting |
| `10-OWNER · Architecture` | Architecture Owner | Core protocols, config schema, registry, factories, API review, breaking-change approval |
| `20-OWNER · Training` | Training Owner | Runner system, checkpoint manager, distributed training, optimizer and scheduler lifecycle |
| `30-OWNER · Data` | Data Owner | RawSample usage, transforms, statistics, LeRobot and Parquet fixtures, mixture datasets |
| `40-OWNER · Model` | Model Owner | Native frameworks, action heads, processors, model output contract, policy integration |
| `50-OWNER · Deployment` | Deployment Owner | Policy server, HTTP/ZMQ clients, RTC policy, acceleration backend interfaces |
| `60-OWNER · Quality` | Quality Owner | CI, pre-commit, pyright, test matrix, documentation gates, final quality evidence |

## Dispatch path

```text
User discussion
  -> Manager updates program state or drafts a task card
  -> Manager dispatches the task card to the Primary Owner
  -> Owner runs Explorer if impact is unclear
  -> Owner runs exactly one Implementer for writes when implementation is needed
  -> Owner runs Reviewer and Tester for independent evidence
  -> Owner writes an Owner report
  -> Manager verifies approvals and updates task state
  -> Manager reports the concise result to the user
```

## Single-writer rule

For each task, exactly one write-capable worker may modify the approved write scope at a time. The Manager may create governance-only task cards and reports, but source, tests, configs, scripts, model paths, data paths, training paths, deployment paths, and Slurm paths require an Owner-owned Implementer when they change behavior.

Read-only Explorer, Reviewer, and Tester work may run in parallel only when their scopes do not conflict and no shared mutable contract is being changed.

## Subagent retirement ledger

Owner threads must keep task-specific subagents short lived. Every Owner report must include a Subagent retirement ledger that records each subagent role, assigned scope, whether its output was collected, whether risks were summarized, and whether the subagent context was retired.

The Manager must not accept an Owner report while any required subagent is still active, missing output, or missing retirement status. If a subagent is replaced, the Owner report must record the retired subagent, replacement reason, replacement scope, and final evidence.

## Parallel write proposal protocol

Within one task, an Owner may decide how many read-only Explorer, Reviewer, and Tester subagents are needed for evidence. For behavior-changing work, the default remains exactly one Implementer for the approved write scope.

If an Owner identifies genuinely disjoint write scopes that could benefit from parallel Implementers, the Owner must not launch parallel writes directly. The Owner must create a parallel write proposal that lists each proposed writer, writable paths, protected paths, shared contracts, expected conflicts, validation commands, rollback notes, and subagent retirement plan.

The Manager reviews all Owner proposals, checks cross-task conflicts, and either keeps execution serial or requests Manager approval through the user-facing gate before creating separate task cards or worker threads for parallel writes. Parallel write approval is valid only for the listed disjoint scopes and does not weaken the single-writer rule inside each resulting task.

## Approval matrix

| Change type | Primary Owner | Required reviewer |
| --- | --- | --- |
| Public protocol, dataclass contract, registry, factory, config schema | Architecture | Quality |
| Runner, checkpoint, distributed backend, optimizer, scheduler | Training | Architecture + Quality |
| Dataset contract, transform, fixture, statistics, normalization | Data | Architecture + Quality |
| Framework, action head, processor, masked loss, policy integration | Model | Architecture + Quality |
| Policy server, client schema, RTC, acceleration backend | Deployment | Architecture + Quality |
| CI, lint, pyright, pre-commit, docs gates | Quality | Architecture when public contracts are affected |

## M1-T validation route

M1-T is a governance and coordination test node. It validates the Codex-only Manager and Owner-thread workflow before using it for further GenesisVLA implementation.

M1-T does not change model, data, training, deployment, Slurm, dataset, or robot behavior. It may update local coordination files, Owner charters, task templates, and repository meta tests that verify the control plane exists.

M1-T may also run a real thread startup smoke that creates one disposable Owner-style Codex thread, confirms it can read its prompt and respond, records evidence, and then archives or retires the disposable thread. This smoke proves thread creation plumbing only; it must not replace formal implementation validation, Owner review, or task-specific verification.

## Thread recovery

Each persistent thread must be recoverable from files, not memory alone. Recovery sources are:

- Manager: `docs/coordination/MANAGER_ENTRYPOINT.md`, `coordination/PROGRAM_STATE.yaml`, `coordination/TASK_INDEX.yaml`
- Persistent thread registry shape: `coordination/THREAD_REGISTRY.yaml`
- Owner: its Owner charter, the assigned task card, and the previous Owner report
- Task: the task card and validation evidence

If thread memory and file state disagree, file state wins unless the user explicitly overrides it.

## Owner dispatch memory

Owner Dispatch Memory is recorded in `coordination/OWNER_DISPATCH_MEMORY.yaml` and is distinct from Tool Memory. It records channel health, thread id, task id, sent turn, status ping, report expectations, output presence, classification, role-refresh state, and resolution history.

If a persistent Owner dispatch completes with no visible output or no required report, the Manager records `OWNER_THREAD_COMPLETED_NO_OUTPUT`. If that channel cannot satisfy role review, the Manager also records `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`. This state blocks approval until a refreshed Owner or approved replacement reviewer supplies evidence.

Tool Memory is advisory and cannot replace Owner reports, validation evidence, PR mutation authorization, or completion-state decisions.
