# Loop Harness Governance

## Purpose

The loop harness templates under `coordination/loops/` are governance-only scaffolding. They help create auditable loop specs, resolved specs, plans, deliveries, state, and run logs.

They do not execute model training, modify PRs, mutate branches, delete worktrees, change dependencies, start GPU work, or submit Slurm jobs by default.

## Harness boundary

The harness may:

- validate that required spec fields are present;
- produce local governance logs;
- point to evidence ledgers;
- mark missing required fields as `BLOCKED_LOOP_SPEC`;
- preserve draft PR visibility unless the loop spec says otherwise.

The harness must not:

- infer missing budget or timeout policy;
- turn a completed Owner thread into approval without a report;
- rely on DevSpace MCP as internal execution evidence;
- replace validation, review, or scan gates;
- perform connector actions without explicit loop authorization.

## Template placeholders

Template placeholder values such as `<loop-id>` or `<budget-policy-from-top-level-prompt>` are examples only. They are not defaults. A resolved loop spec must replace every placeholder required for execution.
