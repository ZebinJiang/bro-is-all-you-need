# Top-Level Loop Prompt Template

Task id: `<task-id>`
Loop id: `<loop-id>`
Active model label: `gpt-5.5`

Objective:
`<objective-from-user-or-manager>`

In scope:
`<explicit-in-scope-list>`

Out of scope:
`<explicit-out-of-scope-list>`

Allowed write paths:
`<explicit-allowed-write-paths>`

Protected paths:
`<explicit-protected-paths>`

Budget policy:
`<budget-policy-from-top-level-prompt>`

Timeout policy:
`<timeout-policy-from-top-level-prompt>`

Validation evidence ledger:
`<validation-evidence-ledger-path>`

Connector actions:
`<authorized-connector-actions-or-none>`

Compute actions:
`<authorized-compute-actions-or-none>`

PR visibility:
`<draft-or-ready-policy-from-top-level-prompt>`

If any required field remains unresolved, stop as `BLOCKED_LOOP_SPEC`.
