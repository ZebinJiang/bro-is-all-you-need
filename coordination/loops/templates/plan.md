# Loop Plan

Loop id: `<loop-id>`
Task id: `<task-id>`
Model label: `gpt-5.5`

## Scope

- Objective: `<objective>`
- Allowed writes: `<allowed-write-paths>`
- Protected paths: `<protected-paths>`
- Non-goals: `<explicit-non-goals>`

## Owner Thread Plan

- Owner topology: `<owner-topology-summary>`
- Spec Owner: `<spec-owner>`
- Delivery Owner: `<delivery-owner>`
- Implementation Owner(s): `<implementation-owners-or-none>`
- Reviewer Owner(s): `<reviewer-owners>`
- Publisher Owner: `<publisher-owner-or-none>`
- Tooling Owner: `<tooling-owner-or-none>`
- Compute Owner: `<compute-owner-or-none>`
- Topology fail-closed status: `BLOCKED_OWNER_TOPOLOGY`
- Primary Owner: `<primary-owner>`
- Required reviewer Owners: `<required-reviewer-owners>`
- Consulted Owners: `<consulted-owners-or-none>`
- Skipped Owners and reasons: `<skipped-owners-and-reasons>`
- Owner packet paths: `<owner-packet-paths>`
- Owner report paths: `<owner-report-paths>`
- Owner refresh or construction authorization: `<authorization-source>`

## Child-Agent Plan

- Owner subagent plan reference: `<owner-subagent-plan-path-or-section>`
- Child-agent depth limit: `1`
- Child-agent report paths: `<child-agent-report-paths>`
- Child retirement ledger path: `<retirement-ledger-path>`

## Plan Gate Reviewers

- `<Owner-role-and-required-report-path>`

Required field: `child_reports_cannot_bypass_owner_report: true`.
Plan gate passes only when every required Owner report exists and passes.
Completed Owner turns without output are not approval.

## Delivery Gate Reviewers

- `<Owner-role-and-required-report-path>`

Required field: `child_reports_cannot_bypass_owner_report: true`.
Delivery gate passes only when every required Owner report exists, required
child agents have retired, validation evidence exists, and publication scans
pass when publication is in scope.

## Concurrency Plan

- Owner thread concurrency: `<supplied-by-top-level-prompt>`
- Child-agent concurrency by Owner: `<supplied-by-top-level-prompt>`
- Source writer concurrency: `<supplied-by-top-level-prompt>`
- Publication writer concurrency: `<supplied-by-top-level-prompt>`
- Compute runner concurrency: `<supplied-by-top-level-prompt>`

## Serial Write Plan

- Write-capable Owner: `<Owner-role-or-none>`
- Write-capable child agent: `<child-id-or-none>`
- Allowed write paths: `<allowed-write-paths>`
- Topology write scope: `<topology-write-scope-or-none>`
- Protected paths: `<protected-paths>`
- Starts after: `<dependencies>`
- Retires before: `<owner-report-path>`

## Required Gates

- Spec completeness: missing required fields stop as `BLOCKED_LOOP_SPEC`.
- Budget and timeout: supplied by top-level prompt or resolved spec.
- Owner refresh: routed Owners must return `ROLE_REFRESHED_FOR_GVLA_LOOP_V2`.
- Owner reports: completed turns without output do not count.
- Child reports: cannot bypass parent Owner reports.
- Validation: evidence ledger path required.
- Publication: scans, exact head, and visibility gate required before PR mutation.

## Wave Schedule

| Wave | Manager state transition | Owner dispatch | Child-agent sequence | Gate result | Checkpoint |
| --- | --- | --- | --- | --- | --- |
| `<wave-id>` | `<state-transition>` | `<owner-packet-path>` | `<child-sequence>` | `<gate-status>` | `<checkpoint-path>` |
