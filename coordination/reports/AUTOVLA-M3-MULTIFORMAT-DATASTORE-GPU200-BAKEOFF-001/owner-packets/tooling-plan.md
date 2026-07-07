# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Tooling`
- Owner thread name: `70-OWNER · Tooling`
- model_label: `gpt-5.4`
- owner_topology_mode: `reviewer_owner`
- reviewer_does_not_patch: `true`

## Assignment

- objective: `Read-only planning review for environment/tooling readiness, no-dependency-change boundary, generated-artifact exclusion, and publication scan safety.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `.agent-docs/git_workflow.md`
  - `scripts/quality/genesis_check_project_local.sh`
  - `autovla/dataloader/perf/__main__.py`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-tooling-plan.md`
- topology_write_scope:
  - `none`
- protected_paths:
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
  - `datasets/readonly/**`
- budget_slice: `planning_only`
- stop_boundaries:
  - `BLOCKED_TOOL_ENV if current project-local tooling cannot support the required validation path`
  - `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY if safe execution depends on a new undeclared package`

## Runtime Plan

- owner_thread_plan_ref: `task card + manager dispatch`
- owner_subagent_plan_ref: `read-only planning only; no child writer`
- activation_gate_ref: `installed loop v2 governance under current AutoVLA manager flow`
- runtime_smoke_required: `false`
- normal_loop_mode_allowed: `true`
- allowed_child_agent_types:
  - `Explorer`
  - `Reviewer`
- child_agent_depth_limit: 1
- child_agent_retirement_required: true

## Required Outputs

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-tooling-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/tooling/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/tooling/`
- required conclusions:
  - `APPROVE`
  - `REQUEST_CHANGES`
  - `BLOCKED_TOOL_ENV`
  - `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/tooling/`
- runtime smoke evidence path: `not_applicable`
