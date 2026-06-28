# Thread-Owner Loop Runtime

## Purpose

This document is the normative runtime contract for prompt-controlled loop v2.
It makes the intended hierarchy explicit and machine-checkable:

```text
User + ChatGPT
  produce top-level loop prompt
        |
        v
00-MANAGER · GenesisVLA Program
  validates loop spec
  drafts plan.md
  runs plan_gate
  dispatches to the Primary Owner thread
  dispatches to Required Reviewer Owner threads
        |
        v
Persistent Owner Thread
  reads Owner task packet
  creates or validates the Owner-local child-agent plan
  launches only prompt-authorized short-lived child agents
  collects child-agent reports
  writes one Owner report
        |
        v
Owner-owned child agents
  Explorer
  Planner
  Implementer
  Reviewer
  Tester
  ToolEnvRunner
  ComputeRunner
  Publisher
```

The Manager is the control plane. It may not replace an Owner child-agent tree
with direct domain child-agent dispatch except for an explicitly authorized
bootstrap governance migration fallback. Such fallback evidence must be labeled
as bootstrap evidence and must not be cited as proof that future Owner runtime
dispatch worked.

Owner topology is validated before dispatch. The resolved spec must define
`owner_topology` as described in
`docs/coordination/OWNER_TOPOLOGY_GOVERNANCE.md`; otherwise the Manager stops
as `BLOCKED_OWNER_TOPOLOGY` before Owner packets, implementation, publication,
tool recovery, compute, or PR mutation.

Normal loop mode additionally requires activation. `GOVERNANCE_INSTALLED`
means the governance files are present; it does not prove runtime dispatch.
`GOVERNANCE_ACTIVATED` requires
`GVLA-LOOP-V2-OWNER-RUNTIME-SMOKE-001` to pass with Owner packets, Owner
reports, child retirement evidence, run log, checkpoint, and Manager review.

## Codex Thread Tool Settings

Every persistent Owner thread creation, Owner refresh, Manager-to-Owner packet
dispatch, and Owner or Manager worker-thread creation must request
`thinking: "xhigh"` when the Codex thread tool exposes that field. This value is
the repository-wide Owner runtime setting.

The Manager must not use the schema value `max` for GenesisVLA Owner runtime
work. If a top-level prompt says "maximum" or "extra-high reasoning", the
runtime schema value remains `xhigh`. If the tool schema does not expose a
`thinking` field, the Manager omits the field and records `thinking=xhigh
requested/not exposed` in the dispatch evidence.

## Thread-Level Owners

All core domains are persistent thread-level Owner roles when routed:

| Role | Thread name | Runtime duty |
| --- | --- | --- |
| Architecture | `10-OWNER · Architecture` | contracts, schema, API, protocol, baseline contamination review |
| Product/Spec | `15-OWNER · Product/Spec` | specification, user-facing acceptance, compatibility decision routing |
| Training | `20-OWNER · Training` | training/runtime feasibility, no-auto-compute review, future training loop usability |
| Engineering/Codebase Migration | `25-OWNER · Engineering/Codebase Migration` | scoped implementation and repo-wide rename delivery |
| Data | `30-OWNER · Data` | dataset immutability, transforms, manifests, evidence paths |
| Model | `40-OWNER · Model` | model paths, policy interfaces, tensor/action contracts |
| Deployment | `50-OWNER · Deployment` | endpoints, serving, RTC, publication and robot safety |
| Quality | `60-OWNER · Quality` | scans, validation ledger, completion gates, publication safety |
| Tooling | `70-OWNER · Tooling` | tool recovery, connector fallback review, Tool Memory review |
| Compute/HPC | `80-OWNER · Compute/HPC` | compute, GPU, Slurm, scheduler, login-node safety |

Each role has these runtime invariants:

- `role_type: persistent_owner`
- `thread_level: true`
- `can_spawn_child_agents: true`
- `child_agent_depth_limit: 1`
- `requires_role_refresh_before_dispatch: true`
- `owner_report_required: true`
- `completed_no_output_is_approval: false`

If Tooling or Compute/HPC has no live thread when routed, the Manager records
`OWNER_THREAD_REQUIRED` or `ROLE_REFRESH_REQUIRED`. The Manager may construct or
refresh that Owner only when the top-level prompt authorizes it. Without that
authorization, the loop stops before dispatch.

## Owner Packet

The Manager sends each routed Owner one task packet. The packet must contain:

- `loop_id`
- `task_id`
- Owner role and thread name
- assigned objective
- context sources
- allowed write scope
- owner topology role: spec, delivery, implementation, reviewer, publisher,
  tooling, compute, or none
- reviewer-does-not-patch and role-separation limits for that Owner
- protected paths
- budget slice supplied by the top-level prompt or resolved spec
- allowed child-agent plan for that Owner
- required Owner report path
- required conclusion values
- stop boundaries
- evidence paths
- PR, branch, worktree, and expected-head state
- child-agent retirement ledger requirement

Missing Owner packet path is `BLOCKED_LOOP_SPEC`.

Missing topology, unsafe topology, or packet topology that contradicts the
resolved spec is `BLOCKED_OWNER_TOPOLOGY`.

## Owner-Owned Child Agents

Every child agent is owned by exactly one Owner thread and has depth one.

| Child type | Owner use |
| --- | --- |
| Explorer | read-only context discovery |
| Planner | read-only implementation, validation, or review plan |
| Implementer | write-capable worker for one approved write scope |
| Reviewer | read-only independent review |
| Tester | validation runner; writes only approved evidence |
| ToolEnvRunner | Tooling-owned environment recovery worker |
| ComputeRunner | Compute/HPC-owned compute-node, Slurm, or scheduler-policy runner |
| Publisher | Quality-owned publication worker for scan-gated connector or git publication |

Child-agent reports cannot satisfy Manager gates directly. The parent Owner must
collect child outputs, summarize risks, record retirement, and write the Owner
report. A child report without its parent Owner report is evidence of incomplete
dispatch, not approval.

A completed Owner turn with no visible output or no required Owner report is
`OWNER_THREAD_COMPLETED_NO_OUTPUT`. During activation smoke this blocks
activation rather than serving as partial approval.

## Owner Subagent Plan

Every top-level loop prompt and resolved spec must include `owner_subagent_plan`
for every routed Owner:

```yaml
owner_subagent_plan:
  <owner>:
    max_child_agents: <supplied_by_prompt>
    peak_concurrency: <supplied_by_prompt>
    child_agent_depth_limit: 1
    sequence:
      - child_id: <owner-child-id>
        type: <Explorer|Planner|Implementer|Reviewer|Tester|ToolEnvRunner|ComputeRunner|Publisher>
        capability: <specific-capability>
        allowed_write_paths:
          - <path-or-none>
        protected_paths:
          - <protected-path>
        required_output: <subagent-report-path>
        conclusion_values:
          - <allowed-conclusion>
        starts_after:
          - <dependency-or-none>
        retires_before: <owner-report-path>
```

If `owner_subagent_plan` is missing, or if any routed Owner lacks a subagent
plan, the Manager returns `BLOCKED_LOOP_SPEC`.

If topology lists an implementation Owner, that Owner needs an Implementer child
before write work can start. If topology lists a publisher Owner for PR
publication, that Owner needs a Publisher child before publication can start.
Reviewer Owners do not patch the artifact under review.

## Parallelism Policy

Only the user/ChatGPT top-level prompt or resolved loop spec decides:

- how many Owner threads may run concurrently;
- which Owner child agents may run in parallel;
- which child agents must remain serial;
- which Owner can write;
- peak source writer concurrency;
- peak publication writer concurrency;
- peak compute runner concurrency.

Governance must not invent numeric defaults for budgets, timeouts, Owner count,
child-agent count, or concurrency. Governance enforces these hard rules:

- no parallel source writes unless the prompt defines disjoint write scopes and
  required Owners approve;
- no parallel publication writes;
- no child-agent depth greater than one;
- every child agent retires before Owner report acceptance;
- Manager direct domain child-agent dispatch is blocked outside an explicitly
  authorized bootstrap fallback.

## Plan Gate

Plan gate sequence:

1. Manager validates the resolved spec.
2. Manager drafts `plan.md` from the top-level prompt.
3. Manager sends the plan to designated reviewer Owners.
4. Reviewer Owners may launch Reviewer child agents if the prompt authorizes it.
5. Reviewer Owners write Owner reports.
6. Manager accepts the plan only when every required Owner report exists and
   passes.

Completed Owner turns without visible output or without required reports remain
`OWNER_THREAD_COMPLETED_NO_OUTPUT`; they are never approval.

## Delivery Gate

Delivery gate sequence:

1. Primary Owner receives an Owner packet.
2. Primary Owner launches only prompt-authorized child agents.
3. Implementer writes only inside the approved scope.
4. Tester produces validation evidence when routed.
5. Reviewer produces independent review when routed.
6. Primary Owner consolidates child reports into one Owner report.
7. Quality and required domain reviewer Owners run the delivery gate.
8. Manager accepts delivery only when required Owner reports exist and pass.

## Portable Artifacts

Every loop must emit or reference:

- `RUN_IN_SESSION.md`
- `loop.yaml`
- `loop.resolved.json`
- `plan.md`
- `owner-packets/`
- `owner-reports/`
- `delivery-N.md`
- `state.json`
- `run-log.md`
- `checkpoints/`
- final Manager summary

These artifacts must be portable: another Manager thread should be able to read
them and recover loop state without hidden chat memory.

## PR-Visible Progress

Implementation loops end with one PR-visible or publication-visible state:

- existing PR updated;
- draft PR created;
- ready PR prepared;
- merged PR when explicitly authorized;
- connector action required;
- classified blocker.

Publication states remain scan-gated, exact-head-gated, and visibility-gated.
Draft PRs remain draft unless the top-level prompt explicitly authorizes a
ready transition.

## Wave Mapping

The old Wave prompt structure remains valid as an execution schedule. The loop
runtime does not delete Waves; it makes Waves portable inside `plan.md`.

Each Wave maps to:

- Manager state transition;
- Owner thread dispatch;
- Owner child-agent sequence;
- gate result;
- `state.json` checkpoint.

Wave reports are therefore runtime evidence only when they are tied to Owner
packets, Owner reports, child-agent reports, gate outcomes, and checkpoints.
