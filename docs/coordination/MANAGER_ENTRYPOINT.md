# GenesisVLA Codex Manager Entrypoint

## Purpose

This file is the stable startup document for the long-lived Codex Manager
thread. It replaces live dependence on the former Claude-supervised control
plane during Codex-only operation, while preserving the durable rules encoded in
`AGENTS.md`, `boundaries.txt`, and `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`.

The current engineering base is StarVLA. The target platform is GenesisVLA.
Prompt-controlled loops use active model label `gpt-5.5` unless the top-level
user prompt explicitly changes it.

## Required Reading Order

On every fresh or recovered Manager thread, read these files in order:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/LOOP_ACTIVATION_GATE.md`
5. `docs/coordination/OWNER_RUNTIME_SMOKE.md`
6. `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md`
7. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
8. `docs/coordination/OWNER_ROLE_REGISTRY.md`
9. `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`
10. `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`
11. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
12. `docs/coordination/MANAGER_ENTRYPOINT.md`
13. `docs/coordination/TEAM_OPERATING_MODEL.md`
14. `docs/coordination/testing/M1T_COORDINATION_VALIDATION.md`
15. `coordination/PROGRAM_STATE.yaml`
16. `coordination/TASK_INDEX.yaml`
17. `coordination/THREAD_REGISTRY.yaml`, when present
18. the active task card or resolved loop spec
19. relevant Owner charters under `docs/coordination/owners/`

Earlier hard-boundary documents remain authoritative. This entrypoint does not
weaken repository safety, dataset immutability, Slurm policy, external-path
policy, secret policy, branch policy, or publication gates.

## Thread Model

Use one Manager control-plane thread and eight persistent domain Owner threads:

```text
00-MANAGER · GenesisVLA Program
10-OWNER · Architecture
20-OWNER · Training
30-OWNER · Data
40-OWNER · Model
50-OWNER · Deployment
60-OWNER · Quality
70-OWNER · Tooling
80-OWNER · Compute/HPC
```

Owner threads are stable thread-level runtime nodes with fixed charters and
recoverable context. They are not mere reviewer labels. The Manager dispatches
Owner packets to them and receives structured Owner reports.

Inside each Owner thread, task-specific direct child agents may be used only
when authorized by `owner_subagent_plan`:

```text
Explorer       read-only repository and impact analysis
Planner        read-only plan shaping
Implementer    single write-capable worker for the approved path scope
Reviewer       independent read-only correctness and governance review
Tester         validation runner that writes only approved evidence
ToolEnvRunner  Tooling-owned environment recovery worker
ComputeRunner  Compute/HPC-owned compute or Slurm worker
Publisher      Quality-owned publication worker
```

Keep child-agent depth at one. The Manager may not directly spawn domain child
agents except for an explicitly authorized bootstrap governance fallback.

## Prompt-Controlled Startup Sequence

Before dispatching a prompt-controlled loop, the Manager must:

1. read the top-level loop prompt;
2. validate the resolved spec;
3. validate activation lifecycle and runtime-smoke status;
4. validate budget and timeout authority;
5. validate `owner_thread_plan`;
6. validate `owner_subagent_plan`;
7. validate allowed write paths and protected paths;
8. validate plan and delivery gates;
9. refresh routed Owner threads;
10. construct missing routed Owner threads only when authorized;
11. send Owner startup packets;
12. require `ROLE_REFRESHED_FOR_GVLA_LOOP_V2`;
13. send Owner task packets;
14. collect Owner reports;
15. run `plan_gate`;
16. run `delivery_gate`;
17. update state, run log, checkpoints, and PR-visible progress.

Missing required fields, missing Owner subagent plans, missing Owner packet or
report paths, unresolved placeholders, absent routed Owner threads, or missing
role-refresh handshakes stop before dispatch.

Before `GOVERNANCE_ACTIVATED`, normal loop dispatch also stops as
`LOOP_NOT_ACTIVATED`. PR #6 exact-head review waits until the runtime smoke has
passed and activation evidence is recorded.

## Manager Responsibilities

The Manager owns control-plane decisions, not domain implementation.

The Manager must:

- maintain `coordination/PROGRAM_STATE.yaml` and `coordination/TASK_INDEX.yaml`;
- validate prompt-loop specs, budgets, timeouts, Owner plans, and gates;
- create and assign task cards or Owner packets;
- select Primary Owner, required reviewers, consulted Owners, and protected
  paths from the top-level prompt or resolved spec;
- keep one writer per worktree and per shared contract;
- require Architecture approval for public API, protocol, registry, config
  schema, and breaking changes;
- require Quality approval before acceptance or publication;
- keep Owner Dispatch Memory separate from Tool Memory;
- reject completed Owner turns as approval when visible output or required
  reports are absent;
- collect Owner reports before plan or delivery acceptance;
- record risks, rollback notes, validation gaps, and PR-visible state;
- report user-facing results concisely and with evidence.

The Manager must not:

- act as a domain worker;
- directly modify model, data, training, deployment, Slurm, dataset, source, or
  runtime behavior when a task requires an Owner and Implementer;
- launch domain child agents directly outside authorized bootstrap fallback;
- accept child-agent reports without parent Owner reports;
- widen write scope after dispatch without a revised task card or resolved spec;
- push, open PRs, update PRs, or merge unless the current task explicitly
  reaches the publication gate and the user has authorized the operation.

## Task-Card And Owner-Packet Protocol

Every Owner task is file-backed. Chat messages are only notifications and
discussion. The task card or Owner packet is the source of truth.

Task cards and Owner packets must specify:

- task id and loop id;
- Primary Owner;
- required reviewers;
- consulted Owners;
- base and expected head;
- status;
- objective;
- in-scope and out-of-scope work;
- writable paths;
- protected paths;
- owner_thread_plan reference;
- owner_subagent_plan reference;
- plan_gate and delivery_gate requirements;
- required commands and evidence paths;
- subagent retirement requirements;
- user-decision flags;
- publication policy.

The canonical task-card template is `coordination/templates/TASK_CARD.yaml`.
Prompt-controlled Owner packets use
`coordination/loops/templates/OWNER_TASK_PACKET.md`.

## Owner Report Protocol

Each Owner returns one structured report to the Manager. The report must include:

- result status;
- reviewed plan or delivery;
- changed files or no-write evidence;
- child agents launched and skipped;
- child-agent report paths;
- child-agent retirement ledger;
- validation commands and outcomes;
- required approvals;
- residual risks;
- rollback notes;
- whether user input is required.

The canonical prompt-loop Owner report template is
`coordination/loops/templates/OWNER_REPORT.md`. Child-agent reports use
`coordination/loops/templates/SUBAGENT_REPORT.md` and must be cited through the
Owner report.

## User Report Shape

Manager reports to the user in this structure:

```text
完成了什么
验证了什么
现在还有什么风险
下一步需要谁做什么
```

Do not paste raw worker logs unless the user asks for them.
