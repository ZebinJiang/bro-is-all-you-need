# Owner Task Packet

## Identity

- loop_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- task_id: `AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001`
- Owner role: `Compute/HPC`
- Owner thread name: `80-OWNER · Compute/HPC`
- model_label: `gpt-5.4`
- owner_topology_mode: `compute_owner`
- reviewer_does_not_patch: `true`

## Assignment

- objective: `Read-only planning for compute classification, login-node vs compute-node split, Slurm/srun execution policy, telemetry collection, and sequential-vs-parallel candidate run strategy.`
- context_sources:
  - `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
  - `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
  - `.agent-docs/slurm_sandbox_policy.md`
  - `.agent-docs/slurm_environment_discovery.md`
  - `scripts/slurm/request_compute_debug.sh`
  - `scripts/slurm/submit_sandbox_job.sh`
- allowed_write_paths:
  - `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-plan.md`
- topology_write_scope:
  - `none during planning`
- protected_paths:
  - `datasets/readonly/**`
  - `requirements/**`
  - `pyproject.toml`
  - `Makefile`
- budget_slice: `planning_only`
- stop_boundaries:
  - `BLOCKED_COMPUTE_ENV if the required compute path cannot be safely executed from current wrappers/env`
  - `BLOCKED_SCOPE if the proposal requires unauthorized scheduler or resource policy changes`

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

- Owner report path: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-plan.md`
- child report directory: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/`
- evidence paths:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/`
- required conclusions:
  - `APPROVE`
  - `REQUEST_CHANGES`
  - `BLOCKED_COMPUTE_ENV`
  - `BLOCKED_SCOPE`

## Repository And PR State

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- base_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected_head: `3573930421a2f9be66b222d602db680a77aadf3f`
- target PR: `none yet`
- PR visibility: `draft PR later; no mutation during planning`
- PR mutation authorization: `forbidden`
- scan evidence path: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/`
- runtime smoke evidence path: `not_applicable`
