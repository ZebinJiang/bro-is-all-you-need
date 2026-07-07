# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Training Execute Wave 10 Packet

## Role

You are `20-OWNER · Training`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Do not create child write-capable subagents.
No parallel source writes.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD for this write wave: `3573930421a2f9be66b222d602db680a77aadf3f`

Before writing, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

## Allowed write scope

- `autovla/training/telemetry/**`
- `tests/training/**`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave10.md`

Do not write:

- `autovla/dataloader/**`
- `configs/**`
- `scripts/**`
- `docs/**`
- `README.md`
- `requirements/**`
- `pyproject.toml`
- `Makefile`
- `datasets/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`
- task state / program state files

## Required inputs

Read before writing:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave9.md`
- `autovla/training/telemetry/config.py`
- `autovla/training/telemetry/bridge_runtime.py`
- `tests/training/test_gpu200_multiformat_telemetry.py`

## Manager handoff facts you must treat as true

1. Wave 9 compute report exists and concludes:
   - `BLOCKED_TEST`
2. Both required runnable candidates were attempted through the approved wrapper:
   - `zjh_lerobot_v21_raw`
   - `zjh_lerobot_v3_local`
3. Both runs progressed materially into the real GR00T runtime:
   - modality config loaded
   - model parameters enumerated
   - candidate-root stats generated
   - shards generated
   - `Current global step: 0`
   - `Creating custom train dataloader`
4. Neither run failed on candidate-root metadata compatibility.
5. Both runs then failed on the same late runtime boundary:
   - `OSError: AF_UNIX path too long`
   - repeated Python multiprocessing resource-sharer failure during dataloader creation
6. The Wave 9 retry configs used:
   - `dataloader_num_workers: 4`
7. Current telemetry config validation rejects `dataloader_num_workers: 0` because the field is validated as strictly positive.

## Exact wave intent

This is a **narrow Training-owned source repair** wave.

The goal is to make the telemetry config contract capable of expressing a
single-process dataloader retry for the next compute wave, without widening
into wrapper repair, scheduler policy changes, dataset mutation, or real compute
execution in this wave.

You are not fixing the Slurm wrapper here.
You are not launching compute here.
You are not changing benchmark or README surfaces here.

## Required implementation outcomes

### 1. Allow telemetry configs to express single-process dataloader mode

Change the telemetry config contract so that:

- `dataloader_num_workers` may be:
  - omitted / `null`
  - `0`
  - a positive integer
- `bool` remains rejected
- negative integers remain rejected
- strings remain rejected

Use the narrowest honest implementation.

Guidance:

- keep the rest of the telemetry contract unchanged
- do not loosen unrelated integer fields
- do not add ignore comments or typing suppression

### 2. Preserve bridge argv behavior

Keep bridge command rendering consistent:

- if `dataloader_num_workers` is present, continue to pass
  `--dataloader-num-workers <n>`
- this must work for `0` as well as positive integers

Do not add new CLI flags in this wave.

### 3. Add focused tests for the zero-worker escape path

Add or update focused training tests so they prove at minimum:

1. `dataloader_num_workers: 0` is accepted by config loading / validation
2. the rendered bridge command preserves `--dataloader-num-workers 0`
3. `dataloader_num_workers: -1` is rejected
4. `dataloader_num_workers: true` is rejected
5. no unrelated telemetry config rule is loosened

Prefer extending `tests/training/test_gpu200_multiformat_telemetry.py`
instead of creating a new broad test surface, unless a second tiny test file is
clearly cleaner.

## Required validation

Run and record:

1. `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/training/test_gpu200_multiformat_telemetry.py -v`
2. `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
3. `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
4. `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/training/telemetry/*.py tests/training/test_gpu200_multiformat_telemetry.py`
5. `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 autovla/training/telemetry/config.py autovla/training/telemetry/bridge_runtime.py tests/training/test_gpu200_multiformat_telemetry.py`
6. `git diff --check`

If Black hangs again, record the hang and use the narrowest file-by-file
fallback evidence, just as prior Training waves did.

## Required output

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-training-execute-wave10.md`

Include:

1. workspace verification
2. exact files changed
3. narrow implementation summary
4. why this wave is the correct minimal response to Wave 9
5. exact validation command results
6. DevSpace MCP compliance
7. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- use `PASS` only if the telemetry contract now honestly accepts the
  single-process `dataloader_num_workers: 0` path and all focused validations
  pass;
- use `BLOCKED_TEST` if the required focused validations fail inside the allowed
  scope;
- use `BLOCKED_SCOPE` only if solving this would require edits outside the
  allowed write scope above.
