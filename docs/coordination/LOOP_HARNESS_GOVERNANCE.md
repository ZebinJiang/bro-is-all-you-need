# Loop Harness Governance

## Purpose

The loop harness templates under `coordination/loops/` are governance-only
scaffolding. They help create auditable loop specs, resolved specs, plans,
Owner packets, Owner reports, deliveries, state, checkpoints, and run logs.

They do not execute model training, modify PRs, mutate branches, delete
worktrees, change dependencies, start GPU work, or submit Slurm jobs by
default.

`docs/coordination/THREAD_OWNER_LOOP_RUNTIME.md` defines the runtime hierarchy
that the harness represents.

## Harness Boundary

The harness may:

- validate that required spec fields are present;
- validate Owner thread and Owner subagent plans;
- validate plan and delivery gate fields;
- produce local governance logs;
- point to evidence ledgers;
- mark missing required fields as `BLOCKED_LOOP_SPEC`;
- preserve draft PR visibility unless the loop spec says otherwise.

The harness must not:

- infer missing budget or timeout policy;
- invent Owner counts, child-agent counts, or concurrency;
- turn a completed Owner thread into approval without a report;
- accept a child-agent report without the parent Owner report;
- rely on DevSpace MCP as internal execution evidence;
- replace validation, review, or scan gates;
- perform connector actions without explicit loop authorization;
- run compute, GPU, training, or Slurm work without explicit prompt
  authorization.

## Looper Mapping Table

| Loop surface | Owner of the surface | Portable artifact |
| --- | --- | --- |
| external discussion | User + ChatGPT | top-level loop prompt |
| goal + context | User + ChatGPT, validated by Manager | `loop.yaml`, `loop.resolved.json` |
| plan draft | Manager | `plan.md` |
| Owner startup and refresh | Manager -> Owner | `owner-packets/`, `state.json`, `run-log.md` |
| Owner child-agent execution | Owner | child-agent reports, Owner-local evidence |
| plan gate | Manager with reviewer Owners | `plan.md`, `owner-reports/`, `state.json` |
| delivery | Primary Owner | `delivery-N.md`, child-agent reports, Owner report |
| delivery gate | Manager with Quality and reviewer Owners | `delivery-N.md`, `owner-reports/`, `state.json` |
| state and checkpoints | Manager | `state.json`, `run-log.md`, `checkpoints/` |
| final output | Manager | final Manager summary and PR-visible state |

## Template Placeholders

Template placeholder values such as `<loop-id>` or
`<budget-policy-from-top-level-prompt>` are examples only. They are not
defaults. A resolved loop spec must replace every placeholder required for
execution.

Unresolved placeholders in a concrete resolved spec block as `BLOCKED_LOOP_SPEC`.

## Portable Recovery

A recovered Manager thread must be able to reconstruct loop state from:

- top-level prompt;
- `loop.resolved.json`;
- `plan.md`;
- Owner packets;
- Owner reports;
- child-agent reports referenced by Owner reports;
- `delivery-N.md`;
- `state.json`;
- `run-log.md`;
- checkpoints;
- validation evidence ledger.

Hidden chat memory, Tool Memory, or child-agent output alone is not a recovery
source for acceptance.
