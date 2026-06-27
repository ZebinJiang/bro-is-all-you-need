# Loop Run Log

Loop id: `<loop-id>`
Task id: `<task-id>`

## Preflight

- pwd: `<pwd>`
- git root: `<git-root>`
- branch: `<branch>`
- head: `<head>`
- status: `<status>`

## Owner Refresh

| Owner | Action | Result | Evidence |
| --- | --- | --- | --- |
| `<Owner-role>` | `<refresh-or-construct>` | `<result>` | `<evidence-path-or-summary>` |

## Owner Dispatch

| Owner | Packet | Result | Report |
| --- | --- | --- | --- |
| `<Owner-role>` | `<owner-packet-path>` | `<dispatch-result>` | `<owner-report-path>` |

## Child-Agent Launch And Retirement

| Owner | child id | type | launch result | report | retirement |
| --- | --- | --- | --- | --- | --- |
| `<Owner-role>` | `<child-id>` | `<child-type>` | `<launch-result>` | `<subagent-report-path>` | `<retired-or-blocked>` |

## Validation

| Command | Result | Evidence |
| --- | --- | --- |
| `<command>` | `<result>` | `<evidence-path-or-summary>` |

## Plan Gate

| Owner report | Result |
| --- | --- |
| `<owner-report-path>` | `<pass-or-blocked>` |

## Delivery Gate

| Owner report | Child retirement | Result |
| --- | --- | --- |
| `<owner-report-path>` | `<retirement-status>` | `<pass-or-blocked>` |

## Checkpoints

| Checkpoint | State | Evidence |
| --- | --- | --- |
| `<checkpoint-path>` | `<state>` | `<summary>` |

## Gate Outcome

`<PASS-or-BLOCKED-status>`
