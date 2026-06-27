# Owner Report

## Identity

- Owner role: `<Owner-role>`
- Owner thread name: `<NN-OWNER · Domain>`
- task id: `<task-id>`
- loop id: `<loop-id>`
- reviewed artifact: `<plan-or-delivery>`
- report path: `<owner-report-path>`

## Child Agents Launched

| child id | type | capability | output path | retired |
| --- | --- | --- | --- | --- |
| `<child-id>` | `<type>` | `<capability>` | `<child-report-path>` | `<true-or-false>` |

## Child Agent Outputs

- `<child-report-path-and-summary>`

## Evidence Paths

- `<evidence-path>`
- activation evidence: `<runtime-smoke-evidence-path-or-none>`
- scan evidence: `<scan-evidence-path-or-none>`
- PR visibility evidence: `<pr-visibility-evidence-path-or-none>`

## Conclusion

`<PASS|APPROVE|REQUEST_CHANGES|BLOCKED_SCOPE|BLOCKED_LOOP_SPEC|BLOCKED_SCAN|FAIL>`

## Risks

- `<residual-risk>`

## Rollback Notes

- `<rollback-note>`

## Retirement Ledger

- all required child outputs collected: `<true-or-false>`
- child risks summarized: `<true-or-false>`
- all child contexts retired before Owner report acceptance: `<true-or-false>`
- child reports cited only through this Owner report: `<true-or-false>`
- completed Owner turn had visible output: `<true-or-false>`
