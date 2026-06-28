# New Thread Bootstrap

## Purpose

This document bootstraps prompt-controlled Manager threads, persistent Owner
threads, and Owner-owned short-lived child agents for AutoVLA governance.

The active model label remains `gpt-5.5` unless the top-level user prompt
explicitly changes it.

## Required Startup Order

Each new Manager or Owner thread reads:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md`
5. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
6. `docs/coordination/OWNER_ROLE_REGISTRY.md`
7. `docs/coordination/OWNER_DISPATCH_GOVERNANCE.md`
8. `docs/coordination/TOOL_MEMORY_GOVERNANCE.md`
9. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
10. the assigned top-level prompt, loop spec, Owner packet, or task card
11. the relevant role charter or loop prompt template

## Manager Startup

The Manager starts as the control-plane thread. On startup it must:

- verify repository path, git root, branch, head, and status;
- read the top-level loop prompt and resolved loop spec;
- validate budget and timeout authority from the prompt or resolved spec;
- validate `owner_thread_plan`;
- validate `owner_subagent_plan`;
- validate plan and delivery gates;
- validate allowed writes and protected paths;
- validate compute, connector, scan, exact-head, and PR visibility policy;
- identify every routed Owner;
- refresh or construct routed Owner threads only when authorized;
- send Owner packets only to refreshed Owners;
- collect Owner reports before gate acceptance.

The Manager does not conduct a default interview. It asks the user only when a
required policy, authorization, validation evidence path, external action,
deletion, credential, endpoint, budget, timeout, publication, or safety decision
is missing or ambiguous.

## Owner Refresh Or Construction

Existing Owner threads may remain in use, but each routed Owner must refresh
for loop v2 before dispatch. If a routed Owner thread is absent, stale, silent,
or lacks a valid role-refresh response, the Manager records one of:

- `OWNER_THREAD_REQUIRED`
- `ROLE_REFRESH_REQUIRED`
- `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`

The Manager may construct or initialize an Owner thread only when the top-level
prompt explicitly authorizes Owner construction for that role. Without that
authorization, the Manager stops before dispatch with the relevant blocker.

## Owner Startup Packet

The Manager sends a startup packet before the task packet. The startup packet
must include:

- Owner role and thread name;
- model label `gpt-5.5`;
- required governance files to read;
- role registry entry;
- allowed child-agent types;
- allowed write scope;
- prohibited scope;
- required Owner report path;
- conclusion values;
- stop boundaries;
- child-agent depth limit;
- role-refresh handshake token.

## Role Refresh Handshake

An Owner is dispatchable only after it replies with:

```text
ROLE_REFRESHED_FOR_GVLA_LOOP_V2
```

The Owner response must also confirm:

- role name;
- thread-level Owner status;
- child-agent depth limit;
- Owner report requirement;
- completed-no-output is not approval;
- allowed write scope;
- protected paths;
- required output report path.

Missing handshake, missing visible output, or missing report is not approval and
must be recorded in Owner Dispatch Memory.

## Child-Agent Startup

Child agents start only from inside the owning Owner thread. The Owner must pass
the child:

- child id;
- parent Owner;
- child type;
- capability;
- allowed write paths;
- protected paths;
- required output report path;
- start dependencies;
- retirement condition.

No child-agent depth greater than one is allowed.

## Fail-Closed Startup Checks

Before work starts, the thread checks:

- repository path and branch;
- task id and loop id;
- allowed write paths and protected paths;
- required Owner routes;
- `owner_thread_plan`;
- `owner_subagent_plan`;
- Owner packet and report paths;
- budget and timeout policy source;
- compute authorization;
- validation evidence ledger path;
- scan gate;
- exact-head and PR visibility gate;
- Owner Dispatch Memory path;
- Tool Memory policy.

Any missing or ambiguous required field results in `BLOCKED_LOOP_SPEC`.

## Silent Owner Handling

If a persistent Owner dispatch records a completed turn with no visible output
or missing report, the Manager records:

- `OWNER_THREAD_COMPLETED_NO_OUTPUT`
- `ROLE_REFRESH_REQUIRED_OWNER_CHANNEL_SILENT`

The completed turn is not approval and must not satisfy plan, delivery, review,
publication, or completion evidence.
