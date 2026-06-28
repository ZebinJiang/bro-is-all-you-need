# Owner Task Packet

## Identity

- loop_id: `<loop-id>`
- task_id: `<task-id>`
- Owner role: `<Owner-role>`
- Owner thread name: `<NN-OWNER · Domain>`
- model_label: `gpt-5.5`
- owner_topology_mode: `<spec_owner|delivery_owner|implementation_owner|reviewer_owner|publisher_owner|tooling_owner|compute_owner|none>`
- reviewer_does_not_patch: `<true-or-false>`

## Assignment

- objective: `<assigned-objective>`
- context_sources:
  - `<path-or-reference>`
- allowed_write_paths:
  - `<path-or-none>`
- topology_write_scope:
  - `<path-or-none>`
- protected_paths:
  - `<protected-path>`
- budget_slice: `<budget-slice-from-top-level-prompt>`
- stop_boundaries:
  - `<blocked-status-and-condition>`

## Runtime Plan

- owner_thread_plan_ref: `<owner-thread-plan-path-or-section>`
- owner_subagent_plan_ref: `<owner-subagent-plan-path-or-section>`
- activation_gate_ref: `<activation-gate-section-or-path>`
- runtime_smoke_required: `<true-or-false>`
- normal_loop_mode_allowed: `<true-or-false>`
- allowed_child_agent_types:
  - `<child-agent-type>`
- child_agent_depth_limit: 1
- child_agent_retirement_required: true

## Required Outputs

- Owner report path: `<owner-report-path>`
- child report directory: `<child-report-directory>`
- evidence paths:
  - `<evidence-path>`
- required conclusions:
  - `<allowed-conclusion>`

## Repository And PR State

- worktree: `<worktree>`
- branch: `<branch>`
- base_head: `<base-head>`
- expected_head: `<expected-head>`
- target PR: `<pr-or-none>`
- PR visibility: `<draft-or-ready-policy>`
- PR mutation authorization: `<authorized-or-forbidden>`
- scan evidence path: `<scan-evidence-path>`
- runtime smoke evidence path: `<runtime-smoke-evidence-path-or-none>`

## Refusal Conditions

Return `BLOCKED_LOOP_SPEC` for missing fields, unresolved placeholders, missing
subagent plan, missing report path, or child-agent depth greater than one.
Return `BLOCKED_OWNER_TOPOLOGY` for missing topology, non-empty topology
write_scope without implementation Owner, publication without publisher Owner,
tool recovery without Tooling Owner, compute without Compute/HPC Owner, or
reviewer-does-not-patch violations.
Return `BLOCKED_SCOPE` for protected path conflicts.
Return `LOOP_NOT_ACTIVATED` when normal loop mode is requested before runtime
smoke activation. Return `OWNER_THREAD_COMPLETED_NO_OUTPUT` when an Owner turn
finishes without visible output or the required report.
# Runtime Memory And Compute Checks

Before acting, the Owner must confirm whether the packet contains `OWNER_THREAD_NO_ACTIVE_TURN_TO_STEER`, owner replacement, compute command classification, heavy validation, Slurm, or Git LFS locksverify candidate fields. If any are present, the Owner must verify role authorization and fail closed rather than patching or executing outside scope.
