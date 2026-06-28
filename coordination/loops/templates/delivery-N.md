# Loop Delivery `<N>`

Loop id: `<loop-id>`
Task id: `<task-id>`

## Changed Files

`<changed-files-or-no-write-evidence>`

## Owner Topology

- task_class: `<task-class>`
- implementation_owner(s): `<owners-or-none>`
- reviewer_owner(s): `<owners>`
- publisher_owner: `<owner-or-none>`
- tooling_owner: `<owner-or-none>`
- compute_owner: `<owner-or-none>`
- reviewer_does_not_patch: `<true-or-false>`
- fail_closed_status: `<none-or-BLOCKED_OWNER_TOPOLOGY>`

## Owner Packet References

- `<Owner-role>: <owner-packet-path>`

## Owner Reports

- `<Owner-role>: <owner-report-path-and-conclusion>`

## Child-Agent Report References

- `<Owner-role>/<child-id>: <subagent-report-path-and-retirement-status>`

Child-agent reports are evidence only through their parent Owner report.

## Validation Evidence

`<validation-evidence>`

## Plan Gate Result

- reviewers: `<plan-gate-reviewer-owners>`
- child_reports_cannot_bypass_owner_report: `<true>`
- required reports present: `<true-or-false>`
- conclusion: `<pass-or-blocked>`

## Delivery Gate Result

- reviewers: `<delivery-gate-reviewer-owners>`
- child_reports_cannot_bypass_owner_report: `<true>`
- required reports present: `<true-or-false>`
- required child agents retired: `<true-or-false>`
- scans: `<pass-or-blocked-or-not-applicable>`
- exact head: `<pass-or-blocked-or-not-applicable>`
- PR visibility: `<pass-or-blocked-or-not-applicable>`
- compute: `<authorized-or-not-applicable>`
- conclusion: `<pass-or-blocked>`

## Residual Risks

`<residual-risks>`

## Rollback

`<rollback-note>`
