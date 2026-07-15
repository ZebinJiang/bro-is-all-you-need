# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Packet · Compute/HPC Feasibility Wave 2

You are `80-OWNER · Compute/HPC`.

Workspace:
- `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`

Execution mode:
- read-only feasibility review
- report-only
- no file writes outside the required owner report
- no compute execution yet
- no DevSpace MCP

Manager dispatch settings:
- `model=gpt-5.4`
- `thinking=high`

## First read

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `docs/coordination/COMPUTE_EXECUTION_GOVERNANCE.md`
5. `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
6. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-plan.md`
7. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute.md`
8. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute.md`
9. `autovla/dataloader/stores/**`
10. `autovla/training/telemetry/**`
11. `scripts/slurm/request_compute_debug.sh`
12. `scripts/slurm/submit_sandbox_job.sh`
13. `configs/slurm/default_sandbox.json`
14. `configs/slurm/debug_profiles.json`

External read-only exception for this task:
- `/home/cz-jzb/workspace/Isaac-GR00T17`
- `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`

## Workspace verification required in report

Record:
- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short --branch`

## What Manager needs from you now

Current manager finding:
- Data wave 1 and Training wave 1 are both scaffold-level.
- Data wave 2 is now in flight to make the datastore side compute-runnable.
- Training wave 1 is still metadata-only and does not yet satisfy the real GPU200 requirement.

You are not executing jobs in this wave.
You are deciding the exact feasible compute path for the later execution wave.

## Questions you must answer

1. What is the correct governed job split for this task?
   - CPU-only datastore benchmark job(s)
   - 1-GPU 200-step telemetry job(s)
   - optional 2-GPU communication job(s)

2. Which candidates are plausibly runnable for the real GPU200 step, based on the current repo plus the read-only external `Isaac-GR00T17` training surfaces?
   - `zjh_lerobot_v21_raw`
   - `zjh_lerobot_v3_local`
   - `zjh_webdataset_tar`
   - `zjh_robodm_container_v1`

3. Is the most realistic bounded training execution path:
   - through AutoVLA local wrapper code,
   - through a governed AutoVLA-generated wrapper that launches read-only `Isaac-GR00T17`,
   - or blocked unless a new Training wave implements that bridge?

4. What exact preflight checks should happen before the first real compute submission?
   - dataset path visibility
   - candidate artifact path visibility
   - local checkpoint/model path visibility
   - env/tool path visibility
   - wrapper/config presence
   - offline env vars

5. If a candidate cannot honestly participate in the 200-step run, what should its exact compute-side status token be?

## Constraints

- Do not run `srun`
- Do not run `sbatch`
- Do not allocate compute
- Do not modify source/tests/configs/scripts
- Do not mutate git/PR state
- Do not inspect or paste large run logs

## Output required

Write only:
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-feasibility-wave2.md`

The report must include:

1. Workspace verification
2. Current blocker map
3. Recommended exact job topology
4. Which candidates are likely runnable for real GPU200 and why
5. Which candidates are likely load-benchmark-only and why
6. Whether AutoVLA needs a new Training bridge wave before compute can start
7. Preflight checklist
8. DevSpace MCP compliance
9. Subagent retirement ledger
10. Conclusion:
   - `APPROVE_READY_FOR_EXECUTION_PACKET`
   - or `BLOCKED_SCOPE`
   - or `BLOCKED_COMPUTE_ENV`
   - or `BLOCKED_COMPUTE_POLICY`

Manager cares most about an honest feasibility call, not optimism.
