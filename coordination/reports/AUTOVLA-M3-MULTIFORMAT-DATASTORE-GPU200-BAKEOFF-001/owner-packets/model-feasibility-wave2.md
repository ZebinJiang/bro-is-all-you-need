# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Packet · Model Feasibility Wave 2

You are `40-OWNER · Model`.

Workspace:
- `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`

Mode:
- read-only feasibility review
- no source/config/test writes
- write only the required owner report
- no DevSpace MCP

Manager dispatch settings:
- `model=gpt-5.4`
- `thinking=high`

## First read

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
5. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-plan.md`
6. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`
7. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute.md`
8. `autovla/models/**`
9. `autovla/training/**`

Authorized external read-only surfaces for this task:
- `/home/cz-jzb/workspace/Isaac-GR00T17`
- `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`

## Workspace verification required in report

Record:
- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short --branch`

## Why this wave exists

Manager has verified:
- current `autovla/training/telemetry/**` is still metadata-only
- current `autovla/models/gr00t_n1d6/**` remains a fail-closed skeleton
- the top-level task *does* authorize bounded local checkpoint use for a real 200-step GPU telemetry run if the manifest/runtime boundary can be governed honestly

Before a Training execution wave can bridge to real compute, Model needs to answer what is allowed and what exact proof is required.

## Questions you must answer

1. What is the minimum model/checkpoint manifest required to support a real bounded 200-step run while staying inside the task’s authorization?

2. Can the later compute wave honestly use:
   - local path `/home/cz-jzb/workspace/Isaac-GR00T17/base_model/GR00T-N1.6-3B`
   - read-only
   - no download
   - no mutation
   - no HF online
   as the base model input?

3. What exactly may be claimed if a later 200-step run succeeds?
   - runnable bounded telemetry only?
   - loader/backend comparison only?
   - definitely *not* model compatibility / training readiness / checkpoint correctness?

4. Does Model require a new explicit `checkpoint manifest` artifact in AutoVLA before Training/Compute can launch the later run?
   If yes, what exact fields are mandatory?

5. Is a bridge that launches read-only `Isaac-GR00T17` training entrypoints from an AutoVLA-governed wrapper acceptable, or does Model require more AutoVLA-native runtime ownership first?

6. What exact conditions should trigger:
   - `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`
   - `BLOCKED_SCOPE`
   - `REQUEST_CHANGES`

## Constraints

- No code edits
- No PR mutation
- No Slurm / GPU / heavy runtime
- No model weight loading yourself
- No download
- No cache mutation

## Output required

Write only:
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-feasibility-wave2.md`

The report must include:

1. Workspace verification
2. Current model-runtime blocker map
3. Allowed local-checkpoint boundary
4. Required checkpoint/manifest fields, if any
5. What a later successful 200-step run may and may not claim
6. Whether an AutoVLA-governed bridge to read-only `Isaac-GR00T17` is acceptable
7. DevSpace MCP compliance
8. Subagent retirement ledger
9. Conclusion:
   - `APPROVE_BOUNDARY`
   - or `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`
   - or `REQUEST_CHANGES`
   - or `BLOCKED_SCOPE`

Manager wants a fail-closed boundary, not optimism.
