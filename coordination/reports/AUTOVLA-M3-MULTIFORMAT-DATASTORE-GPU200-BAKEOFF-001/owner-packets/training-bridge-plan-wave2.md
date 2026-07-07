# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Packet · Training Bridge Plan Wave 2

You are `20-OWNER · Training`.

Workspace:
- `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`

Mode:
- read-only design/bridge diagnosis
- no source/config/test writes in this wave
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
5. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-plan.md`
6. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute.md`
7. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-model-plan.md`
8. `autovla/training/**`
9. `autovla/models/**`

Authorized external read-only surfaces:
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
- current telemetry package is metadata-only
- current AutoVLA training runner is CPU/dry-run oriented
- the top-level goal requires a real bounded 200-step GPU telemetry run on runnable datastore candidates
- external `Isaac-GR00T17` contains real `launch_finetune_n1d6.py` entrypoints and local base model path, but no AutoVLA-governed bridge exists yet

Before a write-capable Training wave is dispatched, Manager needs the smallest honest bridge design.

## Questions you must answer

1. What is the narrowest acceptable AutoVLA-owned bridge from this worktree to a real 200-step `Isaac-GR00T17` GR00T-N1.6 run?

2. Should the later execution wave:
   - launch `Isaac-GR00T17` through a generated governed wrapper/subprocess surface,
   - or attempt to import any Isaac-GR00T17 Python directly,
   - or be blocked pending a different runtime contract?

3. What exact artifacts must that later bridge emit for this bakeoff?
   Minimum expected examples:
   - run manifest
   - checkpoint/base-model manifest
   - per-step telemetry JSON
   - aggregate telemetry JSON
   - CSV / Markdown / README-feed tables
   - log path manifest

4. What exact datastore candidate interface is required from Data/Compute for Training to run the real 200-step jobs?

5. What exact configuration fields must a later write-capable Training wave own?

6. What exact claims remain forbidden even after a successful bounded run?

7. Is there any honest path to reuse the current `autovla/training/telemetry/**` package, or should the later execution wave add a distinct real-run bridge rather than extending the current metadata-only command?

## Constraints

- No code edits in this wave
- No Slurm/GPU execution
- No checkpoint loading by you
- No downloads
- No PR mutation

## Output required

Write only:
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-bridge-plan-wave2.md`

The report must include:

1. Workspace verification
2. Current bridge gap summary
3. Recommended minimal bridge architecture
4. Required inputs from Data
5. Required inputs from Model
6. Required emitted artifacts/tables
7. Which current telemetry pieces can be reused and which should not
8. DevSpace MCP compliance
9. Subagent retirement ledger
10. Conclusion:
   - `APPROVE_BRIDGE_PLAN`
   - or `REQUEST_CHANGES`
   - or `BLOCKED_SCOPE`

Manager wants the smallest real bridge that still moves toward the actual goal.
