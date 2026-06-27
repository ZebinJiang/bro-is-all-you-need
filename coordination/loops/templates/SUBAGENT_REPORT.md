# Subagent Report

## Identity

- child id: `<child-id>`
- parent Owner: `<Owner-role>`
- type: `<Explorer|Planner|Implementer|Reviewer|Tester|ToolEnvRunner|ComputeRunner|Publisher>`
- capability: `<specific-capability>`

## Scope

- allowed writes:
  - `<path-or-none>`
- protected paths:
  - `<protected-path>`

## Evidence

- `<evidence-path-or-command-summary>`

## Result

`<PASS|APPROVE|REQUEST_CHANGES|BLOCKED_SCOPE|BLOCKED_LOOP_SPEC|BLOCKED_SCAN|FAIL>`

## Residual Risks

- `<residual-risk>`

## Retirement Status

- output collected by parent Owner: `<true-or-false>`
- risk summarized by parent Owner: `<true-or-false>`
- retired before Owner report acceptance: `<true-or-false>`
- parent Owner report path: `<owner-report-path>`
- usable only through parent Owner report: `<true-or-false>`
