# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Training Diagnose Wave 7 Packet

## Role

You are `20-OWNER · Training`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Read-only diagnosis only.
No source write in this wave.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`

Before acting, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

## Allowed write scope

Write only:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-diagnose-wave7.md`

Do not modify source, tests, configs, datasets, or task state in this wave.

## Required inputs

Read before writing:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave3.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave6.md`
- `autovla/training/telemetry/config.py`
- `autovla/training/telemetry/bridge_runtime.py`
- `autovla/training/telemetry/slurm.py`
- `configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
- task-local raw telemetry config:
  `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v21_raw.yaml`
- task-local best non-raw telemetry config:
  `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave6-telemetry/configs/zjh_lerobot_v3_local.yaml`
- external read-only exception:
  `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/data/dataset/lerobot_episode_loader.py`
  `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/configs/finetune_with_val_config.py`
  `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/data/stats.py`

## Problem to diagnose

Wave 6 proved the bridge route is healthy but the dataset roots are not yet
acceptable to Isaac GR00T:

- raw baseline: missing `meta/modality.json`
- `zjh_lerobot_v3_local`: missing `meta/info.json`

The Manager needs a Training-owned diagnosis of whether the next repair should:

1. keep `bridge-run` passing `candidate_store_root` directly and require purely
   Data-side artifact fixes; or
2. add a Training-owned task-local compatibility proxy/staging layer before
   invoking Isaac; or
3. split responsibilities between Data artifact repair and Training bridge
   adaptation.

## Required questions

Answer all of these with evidence:

1. Is the current `bridge-run -> --dataset-path candidate_store_root` contract
   still the right public surface?
2. Would a task-local compatibility proxy under `runs/tmp/**` be the minimal
   honest Training-side adaptation for the raw baseline?
3. Would the same proxy pattern help `zjh_lerobot_v3_local`, or does that
   candidate need Data-side structural repair first?
4. What is the narrowest Training write scope for a follow-up fix, if any?
5. Which fixes must remain Data-owned and should not be hidden in Training?

## Required output

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-diagnose-wave7.md`

Include:

1. workspace verification
2. bridge-contract diagnosis
3. raw-baseline Training diagnosis
4. `zjh_lerobot_v3_local` Training diagnosis
5. recommended minimal Training repair scope, if any
6. recommended Data-vs-Training boundary
7. whether a task-local compatibility proxy is acceptable
8. DevSpace MCP compliance
9. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS_PLAN`
- `BLOCKED_SCOPE`
- `FAIL`
