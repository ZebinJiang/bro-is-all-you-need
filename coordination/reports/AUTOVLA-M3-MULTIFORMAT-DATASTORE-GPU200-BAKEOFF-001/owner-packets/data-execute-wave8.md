# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Data Execute Wave 8 Packet

## Role

You are `30-OWNER · Data`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Single writer only.
No parallel write.

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

You may modify only:

- `autovla/dataloader/stores/**`
- `tests/dataloader/**`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave8.md`

Do not modify:

- `autovla/training/**`
- `configs/**`
- `scripts/**`
- `docs/**`
- `README.md`
- `datasets/readonly/**`
- `datasets/working/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`
- task state / program state files

## Required inputs

Read before writing:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-diagnose-wave7.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-diagnose-wave7.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave6.md`
- `autovla/dataloader/stores/benchmark.py`
- `autovla/dataloader/stores/common.py`
- `autovla/dataloader/stores/lerobot_v3_builder.py`
- `autovla/dataloader/stores/lerobot_v3_reader.py`
- `tests/dataloader/test_multiformat_datastore_bakeoff.py`
- read-only external references:
  - `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/data/dataset/lerobot_episode_loader.py`
  - `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/configs/finetune_with_val_config.py`

## Manager synthesis of Wave 7 diagnosis

Wave 7 established:

1. `zjh_lerobot_v21_raw` is fundamentally usable, but the current telemetry path
   pointed at the immutable source root, which lacks GR00T-required
   `meta/modality.json` and `meta/episodes.jsonl`.
2. `zjh_lerobot_v3_local` is not merely missing metadata; its current
   JSON-record layout is structurally incompatible with Isaac's LeRobot
   parquet/video loader.
3. The cleanest next step is Data-owned repair that produces task-owned,
   Isaac-consumable candidate roots, rather than hiding Data defects in a broad
   Training proxy.

## Required implementation goals

Implement the narrowest honest Data-side repair so that the next compute wave
can retry telemetry against task-owned candidate roots.

### Goal A — Raw baseline candidate root becomes Isaac-consumable

Keep the raw benchmark semantics the same, but make the task-owned raw candidate
artifact root under:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/zjh_lerobot_v21_raw`

become an Isaac-consumable dataset root for later telemetry.

Requirements:

1. Do **not** mutate `datasets/readonly/**`.
2. Use a task-owned compatibility root under the existing raw candidate path.
3. Provide the GR00T-required metadata surface:
   - `meta/info.json`
   - `meta/episodes.jsonl`
   - `meta/tasks.jsonl`
   - `meta/modality.json`
   - `meta/stats.json`
4. Reuse the immutable source `data/` and `videos/` content by safe reference
   from the task-owned candidate root when possible.
5. Metadata content must be authoritative Data-owned generation, not invented by
   Training.

### Goal B — `zjh_lerobot_v3_local` becomes Isaac-consumable

Repair the generated candidate root under:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local`

by changing the underlying builder/reader contract so the candidate is no longer
just a JSON-record layout.

Requirements:

1. The candidate root must expose a true LeRobot-compatible dataset surface for
   Isaac:
   - standard `meta/*.json*`
   - actual data layout that matches `meta/info.json`
   - actual video layout that matches `meta/info.json`
2. Do not fake compatibility with metadata-only cosmetics.
3. Keep the candidate id and bakeoff role as `zjh_lerobot_v3_local`.
4. Update the local benchmark reader so it measures the repaired candidate's
   real layout rather than the old JSON-record-only layout.

### Goal C — Focused tests

Add/update focused tests proving:

1. raw candidate root contains the required GR00T metadata surface without
   mutating the read-only source;
2. `zjh_lerobot_v3_local` candidate root contains the required `meta/` surface;
3. `zjh_lerobot_v3_local` no longer depends on `records/sample-*.json` as its
   sole consumable layout;
4. the multiformat bakeoff still emits all four candidates and numeric rows.

## Validation requirements

Use:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python`

Required validation:

1. `py_compile` for changed Python files
2. `pytest tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
3. any additional focused pytest you add for the repaired builder surface
4. changed-path Ruff
5. changed-path Black
6. `git diff --check`
7. local rerun of the reduced store benchmark:
   - `python -m autovla.dataloader.stores run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`

The benchmark rerun is local product validation only in this wave.
Do not run compute telemetry in this wave.

## Required output

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave8.md`

Include:

1. workspace verification
2. files changed
3. exact raw-candidate repair shape
4. exact `zjh_lerobot_v3_local` repair shape
5. focused validation commands and results
6. whether reduced benchmark rerun completed locally
7. any residual blocker for the next compute wave
8. DevSpace MCP compliance
9. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- use `PASS` if raw and `zjh_lerobot_v3_local` candidate roots are repaired and
  the reduced benchmark rerun succeeds locally;
- use `BLOCKED_SCOPE` only if the repair would require edits outside this packet
  scope or changes to protected/source-external paths.
