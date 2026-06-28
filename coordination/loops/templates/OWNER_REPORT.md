# Owner Report

## Identity

- Owner role: `<Owner-role>`
- Owner thread name: `<NN-OWNER · Domain>`
- task id: `<task-id>`
- loop id: `<loop-id>`
- reviewed artifact: `<plan-or-delivery>`
- report path: `<owner-report-path>`
- owner_topology_mode: `<spec_owner|delivery_owner|implementation_owner|reviewer_owner|publisher_owner|tooling_owner|compute_owner|none>`
- reviewer_does_not_patch_confirmed: `<true-or-false>`

## Owner Topology

- task_class: `<task-class>`
- implementation_owner_scope: `<write-scope-or-none>`
- publication_owner_scope: `<publisher-scope-or-none>`
- tool_recovery_owner_scope: `<tooling-scope-or-none>`
- compute_owner_scope: `<compute-scope-or-none>`
- topology_blocker: `<none-or-BLOCKED_OWNER_TOPOLOGY-reason>`

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

`<PASS|APPROVE|REQUEST_CHANGES|BLOCKED_SCOPE|BLOCKED_LOOP_SPEC|BLOCKED_OWNER_TOPOLOGY|BLOCKED_SCAN|FAIL>`

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
# Runtime Memory And Compute Evidence

Owner reports must record:

- `ROLE_REFRESHED_FOR_GVLA_LOOP_V2`;
- whether `OWNER_THREAD_NO_ACTIVE_TURN_TO_STEER` was present and how it was resolved;
- any replacement Owner thread id and registry/refresh-ledger evidence;
- compute command classification and login-node safety;
- Compute/HPC routing evidence when command class is unknown or heavy;
- Slurm escalation or scheduler rejection handling, if authorized;
- confirmation that Git LFS locksverify bypass was not made default/canonical;
- child-agent retirement ledger, depth limit 1, and reviewer-does-not-patch acknowledgement.
