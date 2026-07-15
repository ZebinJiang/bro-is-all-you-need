# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Product/Spec`
- Owner thread name: `15-OWNER · Product/Spec`
- model_label: `gpt-5.4`
- owner_topology_mode: `spec_owner`
- reviewer_does_not_patch: `true`

## Assignment

- objective: `Read-only planning review for fairness criteria, decision matrix semantics, README/dashboard story, and final recommendation language boundaries.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `README.md`
  - `docs/benchmarks/README.md`
  - `docs/benchmarks/DATA_PIPELINE_BACKEND_BAKEOFF.md`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-product-plan.md`
- topology_write_scope:
  - `none`
- protected_paths:
  - `datasets/readonly/**`
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
- budget_slice: `planning_only`
- stop_boundaries:
  - `REQUEST_CHANGES if proposed decision language overclaims winner status or training readiness`
  - `BLOCKED_SCOPE if the requested publication surface exceeds README/docs numeric-table scope`

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

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-product-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/product/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/product/`
- required conclusions:
  - `APPROVE`
  - `REQUEST_CHANGES`
  - `BLOCKED_SCOPE`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/product/`
- runtime smoke evidence path: `not_applicable`
