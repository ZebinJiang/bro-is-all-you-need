# GenesisVLA Codex Thread-Team Operating Model

## Operating Principle

The Codex Manager is the single control-plane thread. Domain Owners are
persistent thread-level runtime nodes. Task-specific child agents are short
lived, direct children of exactly one Owner thread.

Prompt-controlled loops preserve active model label `gpt-5.5` unless the
top-level user prompt explicitly changes it. The Manager proceeds from the
top-level prompt and resolved loop spec, not from a default interview.

`docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md` is the normative runtime
contract for Manager -> Owner thread -> Owner-owned child-agent execution.

Thread runtime settings are part of the control-plane contract. When the Codex
thread tool schema exposes `thinking`, Manager-to-Owner dispatch, Owner refresh,
Owner construction, and worker-thread creation use `thinking: "xhigh"`. The
schema value `"max"` is not used for this project; prompt language such as
"maximum" maps to `xhigh`.

Prompt-controlled loop v2 must pass
`GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` before normal loop mode is active. PR #7
merge installs the governance; it does not activate it. PR #6 review remains
blocked until activation is recorded.

## Persistent Threads

| Thread | Runtime role | Primary authority |
| --- | --- | --- |
| `00-MANAGER · GenesisVLA Program` | Manager | Program state, loop spec validation, Owner dispatch, user reporting |
| `10-OWNER · Architecture` | Architecture Owner | Core protocols, config schema, registry, factories, API review, breaking-change approval |
| `20-OWNER · Training` | Training Owner | Runner system, checkpoint manager, distributed training, optimizer and scheduler lifecycle |
| `30-OWNER · Data` | Data Owner | RawSample usage, transforms, statistics, LeRobot and Parquet fixtures, mixture datasets |
| `40-OWNER · Model` | Model Owner | Native frameworks, action heads, processors, model output contract, policy integration |
| `50-OWNER · Deployment` | Deployment Owner | Policy server, HTTP/ZMQ clients, RTC policy, acceleration backend interfaces |
| `60-OWNER · Quality` | Quality Owner | CI, scans, validation ledger, documentation gates, final quality evidence |
| `70-OWNER · Tooling` | Tooling Owner | Tool Memory, connector fallback, tool-environment recovery review |
| `80-OWNER · Compute/HPC` | Compute/HPC Owner | Compute, GPU, Slurm, scheduler, login-node safety |

An Owner is not a mere reviewer role. It is a persistent thread-level runtime
node that receives an Owner packet, runs or reviews child-agent work, and writes
one Owner report.

## Dispatch Path

```text
User + ChatGPT top-level prompt
  -> Manager validates resolved spec
  -> Manager refreshes or constructs routed Owner threads when authorized
  -> Manager sends Owner packets
  -> Owner launches only prompt-authorized child agents
  -> child agents write reports and retire
  -> Owner consolidates child reports into an Owner report
  -> Manager runs plan_gate and delivery_gate from Owner reports
  -> Manager updates state, run log, checkpoints, and user report
```

The Manager is not a domain worker. The Manager cannot directly spawn domain
child agents except for an explicitly authorized bootstrap governance fallback.
Child-agent reports cannot bypass the Owner report.

## Owner-Owned Child Agents

Allowed child-agent types are:

- Explorer
- Planner
- Implementer
- Reviewer
- Tester
- ToolEnvRunner
- ComputeRunner
- Publisher

Every child has one parent Owner, one required output report path, one
retirement condition, and depth one. ToolEnvRunner is Tooling-owned.
ComputeRunner is Compute/HPC-owned. Publisher is Quality-owned.

## Single-Writer Rule

For each task or delivery, exactly one write-capable worker may modify the
approved write scope at a time unless the top-level prompt explicitly defines
disjoint write scopes and required Owners approve the split.

The Manager may write governance-only task cards, reports, and control-plane
state when scoped. Source, tests, configs, scripts, model paths, data paths,
training paths, deployment paths, and Slurm paths require the relevant Owner and
Owner-owned Implementer when they change behavior.

## Prompt-Controlled Parallelism

The top-level prompt or resolved spec controls:

- Owner thread concurrency;
- child-agent counts;
- child-agent peak concurrency;
- write-capable child-agent sequence;
- source writer concurrency;
- publication writer concurrency;
- compute runner concurrency.

Owners may not invent child-agent counts or concurrency. They may request a
revised plan, but they must not exceed `owner_subagent_plan`.

## Subagent Retirement Ledger

Every Owner report must include a child-agent retirement ledger that records:

- child id;
- child type;
- assigned scope;
- output report path;
- whether output was collected;
- whether risks were summarized;
- whether the child retired before Owner report acceptance.

The Manager must not accept an Owner report while any required child agent is
still active, missing output, missing risk summary, or missing retirement status.

## Approval Matrix

| Change type | Primary Owner | Required reviewer |
| --- | --- | --- |
| Public protocol, dataclass contract, registry, factory, config schema | Architecture | Quality |
| Runner, checkpoint, distributed backend, optimizer, scheduler | Training | Architecture + Quality |
| Dataset contract, transform, fixture, statistics, normalization | Data | Architecture + Quality |
| Framework, action head, processor, masked loss, policy integration | Model | Architecture + Quality |
| Policy server, client schema, RTC, acceleration backend | Deployment | Architecture + Quality |
| CI, lint, pyright, pre-commit, docs gates | Quality | Architecture when public contracts are affected |
| Tool recovery, connector fallback, Tool Memory active use | Tooling | Quality |
| Compute, GPU, Slurm, scheduler, login-node policy | Compute/HPC | Quality |

## Thread Recovery

Each persistent thread must be recoverable from files, not memory alone.
Recovery sources are:

- Manager: `docs/coordination/MANAGER_ENTRYPOINT.md`,
  `coordination/PROGRAM_STATE.yaml`, `coordination/TASK_INDEX.yaml`
- Persistent thread registry shape: `coordination/THREAD_REGISTRY.yaml`
- Owner: role registry entry, Owner charter, assigned Owner packet, previous
  Owner report
- Task: task card, resolved spec, validation evidence, state, run log

If thread memory and file state disagree, file state wins unless the user
explicitly overrides it.

## Owner Dispatch Memory

Owner Dispatch Memory is recorded in `coordination/OWNER_DISPATCH_MEMORY.yaml`
and is distinct from Tool Memory. It records channel health, thread id, task id,
sent turn, status ping, report expectations, output presence, classification,
role-refresh state, and resolution history.

If a persistent Owner dispatch completes with no visible output or no required
report, the Manager records `OWNER_THREAD_COMPLETED_NO_OUTPUT`. If that channel
cannot satisfy role review, the Manager also records
`ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`. This state blocks approval until a
refreshed Owner or approved bootstrap fallback supplies valid Owner evidence.

Tool Memory is advisory and cannot replace Owner reports, validation evidence,
PR mutation authorization, or completion-state decisions.
