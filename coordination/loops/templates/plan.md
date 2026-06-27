# Loop Plan

Loop id: `<loop-id>`
Task id: `<task-id>`
Model label: `gpt-5.5`

## Scope

- Objective: `<objective>`
- Allowed writes: `<allowed-write-paths>`
- Protected paths: `<protected-paths>`

## Required gates

- Spec completeness: missing required fields stop as `BLOCKED_LOOP_SPEC`.
- Budget and timeout: supplied by top-level prompt or resolved spec.
- Owner reports: completed turns without output do not count.
- Validation: evidence ledger path required.
- Publication: scans, exact head, and visibility gate required before PR mutation.

## Execution steps

1. Validate resolved spec.
2. Dispatch required Owners.
3. Apply scoped governance or implementation work.
4. Run local validation.
5. Record report and residual risk.
