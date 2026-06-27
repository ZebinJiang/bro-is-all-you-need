# Owner Thread Start

Use this prompt to start or refresh a persistent GenesisVLA Owner thread.

Owner role: `<Owner-role>`

Owner thread name: `<NN-OWNER · Domain>`

Active model label: `gpt-5.5`.

Read in order:

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/LOOP_ACTIVATION_GATE.md`
4. `docs/coordination/OWNER_RUNTIME_SMOKE.md`
5. `docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md`
6. `docs/coordination/PROMPT_CONTROLLED_LOOP_PROTOCOL.md`
7. `docs/coordination/OWNER_ROLE_REGISTRY.md`
8. `docs/coordination/NEW_THREAD_BOOTSTRAP.md`
9. relevant Owner charter
10. assigned Owner task packet

Role registry entry:

```yaml
role_type: persistent_owner
thread_level: true
can_spawn_child_agents: true
child_agent_depth_limit: 1
requires_role_refresh_before_dispatch: true
owner_report_required: true
completed_no_output_is_approval: false
```

Allowed write scope:

- `<allowed-write-path-or-none>`

Prohibited scope:

- `<protected-path>`

Allowed child-agent types:

- `<Explorer|Planner|Implementer|Reviewer|Tester|ToolEnvRunner|ComputeRunner|Publisher>`

Required report path:

`<owner-report-path>`

Conclusion values:

- `<allowed-conclusion>`

Role refresh handshake:

Reply with `ROLE_REFRESHED_FOR_GVLA_LOOP_V2` only after confirming the role,
allowed write scope, protected paths, child-agent depth limit, Owner report
path, and completed-no-output non-approval rule.

If any required field is missing, return `BLOCKED_LOOP_SPEC`. If the Owner
cannot safely accept dispatch, return `ROLE_REFRESH_REQUIRED`.

If this is the activation smoke, do not launch ToolEnvRunner, ComputeRunner,
dependency recovery, connector mutation, PR mutation, source/runtime edits,
training, compute, or Slurm.
