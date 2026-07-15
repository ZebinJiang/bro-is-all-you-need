# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Training`
- Owner thread name: `20-OWNER · Training`
- model_label: `gpt-5.4`
- owner_topology_mode: `delivery_owner`
- reviewer_does_not_patch: `false`

## Assignment

- objective: `Read-only planning for bounded GR00T-N1D6 1-GPU 200-step telemetry, manifest/output schema, no-real-training boundary, and loader integration contract.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `autovla/training/local_runner.py`
  - `autovla/training/cli.py`
  - `autovla/training/baseline_metrics.py`
  - `tests/training/test_baseline_metrics.py`
  - `tests/training/test_cli_local_smoke_execution.py`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`
- topology_write_scope:
  - `none during planning`
- protected_paths:
  - `datasets/readonly/**`
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
- budget_slice: `planning_only`
- stop_boundaries:
  - `BLOCKED_SCOPE if the proposal requires real long training, external network, or protected-path mutation`
  - `READY_FOR_USER_DECISION_MODEL_CHECKPOINT if the local checkpoint manifest cannot be safely approved`

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

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/training/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/training/`
- required conclusions:
  - `APPROVE`
  - `REQUEST_CHANGES`
  - `BLOCKED_SCOPE`
  - `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/training/`
- runtime smoke evidence path: `not_applicable`
