# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Data`
- Owner thread name: `30-OWNER · Data`
- model_label: `gpt-5.4`
- owner_topology_mode: `delivery_owner`
- reviewer_does_not_patch: `false`

## Assignment

- objective: `Read-only planning for shared sample/window manifest, raw/v3/WebDataset/RoboDM-style store build/reader contracts, and source read-only guarantees.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `autovla/dataloader/perf/bakeoff.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/training_store.py`
  - `autovla/dataloader/format_pipeline/pipeline.py`
  - `tests/dataloader/test_backend_bakeoff_dashboard.py`
  - `tests/dataloader/test_format_native_loader_bakeoff.py`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-plan.md`
- topology_write_scope:
  - `none during planning`
- protected_paths:
  - `datasets/readonly/**`
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
- budget_slice: `planning_only`
- stop_boundaries:
  - `BLOCKED_SCOPE if the proposal requires source-dataset mutation or unauthorized dependency changes`
  - `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY if an official dependency route is the only safe path`

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

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/data/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/data/`
- required conclusions:
  - `APPROVE`
  - `REQUEST_CHANGES`
  - `BLOCKED_SCOPE`
  - `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/data/`
- runtime smoke evidence path: `not_applicable`
