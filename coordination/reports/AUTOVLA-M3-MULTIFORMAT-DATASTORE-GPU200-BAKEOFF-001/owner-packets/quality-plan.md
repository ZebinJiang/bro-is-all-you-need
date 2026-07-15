# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Quality`
- Owner thread name: `60-OWNER · Quality`
- model_label: `gpt-5.4`
- owner_topology_mode: `reviewer_owner`
- reviewer_does_not_patch: `true`

## Assignment

- objective: `Read-only planning review for test matrix, validation commands, generated-artifact exclusion, scan gates, and draft-PR publication safety.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `.agent-docs/git_workflow.md`
  - `tests/dataloader/test_backend_bakeoff_dashboard.py`
  - `tests/dataloader/test_format_native_loader_bakeoff.py`
  - `tests/training/test_baseline_metrics.py`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-quality-plan.md`
- topology_write_scope:
  - `none during planning`
- protected_paths:
  - `datasets/readonly/**`
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
- budget_slice: `planning_only`
- stop_boundaries:
  - `BLOCKED_TOOL_ENV if the required validation path is unavailable with current project-local tooling`
  - `BLOCKED_SCOPE if publication safety would require forbidden staging or generated-artifact commit`

## Runtime Plan

- owner_thread_plan_ref: `task card + manager dispatch`
- owner_subagent_plan_ref: `read-only planning only; no child writer`
- activation_gate_ref: `installed loop v2 governance under current AutoVLA manager flow`
- runtime_smoke_required: `false`
- normal_loop_mode_allowed: `true`
- allowed_child_agent_types:
  - `Explorer`
  - `Planner`
  - `Reviewer`
- child_agent_depth_limit: 1
- child_agent_retirement_required: true

## Required Outputs

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-quality-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/quality/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/quality/`
- required conclusions:
  - `PASS`
  - `REQUEST_CHANGES`
  - `BLOCKED_TOOL_ENV`
  - `BLOCKED_SCOPE`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/quality/`
- runtime smoke evidence path: `not_applicable`
