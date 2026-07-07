# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Compute Execute Wave 11 Packet

## Role

You are `80-OWNER · Compute/HPC`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
No source/test/config/doc writes outside the packet scope below.
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

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
- `runs/slurm/autovla-m3-multiformat-gpu200-*/**`
- `runs/slurm_debug/autovla-m3-multiformat-*/**`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave11.md`

Do not modify:

- `autovla/**`
- `tests/**`
- `configs/**`
- `scripts/**`
- `docs/**`
- `README.md`
- `datasets/readonly/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`
- task state / program state files

## Required inputs

Read before writing:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave9.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave10.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave8.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave9-telemetry/configs/zjh_lerobot_v21_raw.yaml`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave9-telemetry/configs/zjh_lerobot_v3_local.yaml`

## Manager gate

This wave is valid only after:

1. `owner-data-execute-wave8.md` exists and concludes `PASS`
2. `owner-compute-execute-wave9.md` exists and concludes `BLOCKED_TEST`
3. `owner-training-execute-wave10.md` exists and concludes `PASS`

Wave 9 already proved:

1. the minimum telemetry matrix is exactly:
   - `zjh_lerobot_v21_raw`
   - `zjh_lerobot_v3_local`
2. both candidate roots are compatible enough to pass the repaired metadata gate
   and reach real GR00T runtime startup;
3. the remaining blocker is the multiprocessing dataloader worker path with
   `dataloader_num_workers: 4`, not scheduler policy and not candidate-root
   metadata compatibility.

Wave 10 is expected to have repaired:

1. the telemetry config contract so `dataloader_num_workers: 0` is legal;
2. focused tests so the zero-worker escape hatch is validated and the strict
   reject cases remain fail-closed.

Do not proceed if Wave 10 does not explicitly prove those points.

## Required work

### Phase A — Prelaunch evidence checks

Confirm before any compute launch:

1. `owner-data-execute-wave8.md` exists and concludes `PASS`.
2. `owner-compute-execute-wave9.md` exists and concludes `BLOCKED_TEST`.
3. `owner-training-execute-wave10.md` exists and concludes `PASS`.
4. the raw candidate root still contains:
   - `meta/info.json`
   - `meta/episodes.jsonl`
   - `meta/tasks.jsonl`
   - `meta/modality.json`
   - `meta/stats.json`
5. the local v3 candidate root still contains:
   - `meta/info.json`
   - `meta/episodes.jsonl`
   - `meta/tasks.jsonl`
   - `meta/modality.json`
   - `meta/stats.json`
   - real parquet data under `data/**`
6. write task-local Wave 11 retry configs under:
   - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/configs/`
7. change only the fields required for the retry:
   - `run_id`
   - `dataset_fingerprint`
   - `output_dir`
   - `logs_root`
   - `table_output_root`
   - `dataloader_num_workers`
8. both Wave 11 configs must set:
   - `dataloader_num_workers: 0`
9. all configs actually used in this wave must pass:
   - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.training.telemetry validate-config --config <path>`

If any candidate root is now missing its required surface, stop with
`BLOCKED_SCOPE` and record exact missing files.

### Phase B — Exact telemetry rerun

Rerun the same two minimum-matrix GPU telemetry jobs through the approved wrapper.

Use the same debug profile envelope unless a packet-authorized narrower envelope
is required by scheduler policy:

- profile: `h800-gpu`
- partition: `a100`
- cpus: `16`
- mem: `64G`
- gres: `gpu:1`
- time: `01:00:00`

Required candidate jobs:

1. raw baseline
   - run id: `autovla-m3-multiformat-gpu200-wave11-raw`
   - retry config path:
     `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/configs/zjh_lerobot_v21_raw.yaml`
   - required candidate store root:
     `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/zjh_lerobot_v21_raw`

2. best non-raw
   - run id: `autovla-m3-multiformat-gpu200-wave11-zjh-lerobot-v3-local`
   - retry config path:
     `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/wave11-telemetry/configs/zjh_lerobot_v3_local.yaml`
   - required candidate store root:
     `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local`

Use the approved wrapper:

- `scripts/slurm/request_compute_debug.sh`

Preserve exact wrapper command evidence, output roots, logs, and bridge result
JSON for both jobs.

### Phase C — Result extraction

For each attempted candidate, record:

1. whether the job launched;
2. wrapper command;
3. retry config path actually used;
4. final `candidate_store_root` value used;
5. final `dataloader_num_workers` value used;
6. output root;
7. bridge runtime result path;
8. return code;
9. whether the run completed the bounded 200-step telemetry path successfully;
10. exact failure if not successful.

### Phase D — Final telemetry matrix disposition

Record final candidate dispositions:

- `PASS_200_STEP_TELEMETRY`
- `ATTEMPTED_FAIL_<exact_reason>`
- `NOT_RUN_<exact_reason>`

If both required candidates now succeed, this wave should conclude `PASS`.

If the wrapper path and zero-worker contract are healthy but one or both
candidates still fail inside the runtime path, conclude `BLOCKED_TEST`.

If the wave cannot proceed because Wave 10 did not actually deliver the
zero-worker config contract or report evidence, conclude `BLOCKED_SCOPE`.

## Required output

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave11.md`

Include:

1. workspace verification
2. Wave 8 / Wave 9 / Wave 10 gate confirmation
3. exact candidate-root prelaunch checks
4. exact retry config paths and final `candidate_store_root` values used
5. exact `dataloader_num_workers` values used
6. exact wrapper commands used
7. exact output/log/result paths for both jobs
8. final telemetry disposition for each candidate
9. successful 200-step telemetry rows vs not-run rows
10. job ids or explicit `unknown_debug_wrapper_no_job_id`
11. DevSpace MCP compliance
12. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- use `PASS` only if both required telemetry jobs complete successfully and the
  bounded telemetry evidence is written;
- use `BLOCKED_TEST` if launches are healthy but runtime still fails inside the
  candidate/runtime path;
- use `BLOCKED_SCOPE` if the Wave 10 gate is incomplete or the zero-worker
  contract repair is not actually present.
