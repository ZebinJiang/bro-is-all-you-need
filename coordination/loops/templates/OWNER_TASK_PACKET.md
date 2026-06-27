# Owner Task Packet

## Identity

- loop_id: `<loop-id>`
- task_id: `<task-id>`
- Owner role: `<Owner-role>`
- Owner thread name: `<NN-OWNER · Domain>`
- model_label: `gpt-5.5`

## Assignment

- objective: `<assigned-objective>`
- context_sources:
  - `<path-or-reference>`
- allowed_write_paths:
  - `<path-or-none>`
- protected_paths:
  - `<protected-path>`
- budget_slice: `<budget-slice-from-top-level-prompt>`
- stop_boundaries:
  - `<blocked-status-and-condition>`

## Runtime Plan

- owner_thread_plan_ref: `<owner-thread-plan-path-or-section>`
- owner_subagent_plan_ref: `<owner-subagent-plan-path-or-section>`
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

## Refusal Conditions

Return `BLOCKED_LOOP_SPEC` for missing fields, unresolved placeholders, missing
subagent plan, missing report path, or child-agent depth greater than one.
Return `BLOCKED_SCOPE` for protected path conflicts.
