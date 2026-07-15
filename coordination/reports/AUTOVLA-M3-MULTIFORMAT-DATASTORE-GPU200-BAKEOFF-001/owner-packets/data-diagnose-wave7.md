# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Data Diagnose Wave 7 Packet

## Role

You are `30-OWNER · Data`.

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

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-diagnose-wave7.md`

Do not modify any source, tests, configs, datasets, or task state in this wave.

## Required inputs

Read before writing:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave5.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave6.md`
- `autovla/dataloader/format_pipeline/pipeline.py`
- `autovla/dataloader/perf/bakeoff.py`
- `autovla/dataloader/adapters/zjh.py`
- `tests/dataloader/test_multiformat_datastore_bakeoff.py`
- read-only source dataset root:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- generated best non-raw candidate root:
  `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local`
- external read-only exception:
  `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/data/dataset/lerobot_episode_loader.py`
  `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/configs/finetune_with_val_config.py`

## Problem to diagnose

Wave 6 proved:

1. reduced benchmark completes successfully;
2. compute wrapper route is healthy;
3. raw telemetry fails because the raw dataset root lacks `meta/modality.json`;
4. `zjh_lerobot_v3_local` telemetry fails because the generated candidate root lacks `meta/info.json`.

The Manager now needs a Data-owned diagnosis of the minimal artifact/data-surface
repair needed to make the raw baseline and best non-raw candidate consumable by
the Isaac GR00T LeRobot dataset contract.

## Required questions

Answer all of these with evidence:

1. For `zjh_lerobot_v21_raw`, is the minimal safe repair:
   - a task-local compatibility proxy root, or
   - a reusable working-root artifact, or
   - impossible without mutating the read-only source?
2. For `zjh_lerobot_v3_local`, is the current artifact merely missing metadata
   files, or is its whole layout incompatible with the Isaac LeRobot loader even
   after metadata repair?
3. Which exact metadata files are required for the raw baseline?
4. Which exact metadata files are required for `zjh_lerobot_v3_local`?
5. What is the narrowest Data write scope that could repair the candidate side?
6. What would still remain Training-owned even after Data-side artifact repair?

## Required output

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-diagnose-wave7.md`

Include:

1. workspace verification
2. raw baseline diagnosis
3. `zjh_lerobot_v3_local` diagnosis
4. exact missing files and why they matter
5. whether `zjh_lerobot_v3_local` is structurally compatible or not
6. recommended minimal Data repair scope
7. recommended handoff boundary to Training
8. DevSpace MCP compliance
9. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS_PLAN`
- `BLOCKED_SCOPE`
- `FAIL`
