# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Data-W2

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- Required branch matched. Baseline HEAD before Data-W1 matched the task packet.

## Inputs Reviewed

- `coordination/tasks/active/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001.yaml`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w1.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-quality-r1.md`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-compute-w1.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-compute-benchmark.md`
- `runs/tmp/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/compute/final-dataloader-perf.stderr.log`

## Root Cause

Compute-W1 entered the real source-dataset candidate-specific execution path and generated authorized working artifacts, but `_run_adapter_processes()` still used a fixed `queue.get(timeout=120.0)` for parent-side worker evidence collection.

For the primary matrix, `sample_count=4096` and `worker_count=8`, so each worker could receive about 512 samples. The raw/source adapter can spend substantial time materializing frames through the worker-owned route. The fixed 120-second parent queue wait therefore failed before long-but-alive workers could report evidence. The runner exited before `_write_outputs()`, so final metrics artifacts were missing.

This was an evidence-path timeout, not a scheduler rejection or source dataset mutation. Compute-W1 recorded Slurm route success and source mutation check `PASS`.

## Bounded Fix

- Replaced the hardcoded adapter queue wait with `adapter_worker_queue_timeout_seconds()`.
- Timeout is now bounded and deterministic:
  - minimum: `120s`
  - base: `180s`
  - adapter-specific per-sample budget:
    - `raw_source_rows`: `3.0s` per max worker chunk sample
    - `lerobot_v3_persistent`, `webdataset_persistent`, `robodm_persistent`: `0.75s`
    - `raw_payload_jsonl`: `0.1s`
  - maximum cap: `2400s`
- For the Compute-W1 primary shape, `raw_source_rows` with `4096 / 8` samples now gets about `1716s`, not `120s`, while still remaining finite.
- Added clear fail-closed timeout diagnostics with:
  - `adapter_kind`
  - `candidate_id`
  - `sample_count`
  - `worker_slots`
  - `reported_result_count`
  - `timed_out_slot_count`
  - `timeout_seconds`
  - per-process `slot`, `pid`, `alive`, and `exitcode`
- On timeout, the parent terminates only its own live worker children, joins briefly, and raises `TimeoutError`; it does not fake metrics or write success rows.
- Preserved candidate-specific adapter specs, no common shared measured payload JSONL route, D1 blocked semantics, D6 optional-not-implemented semantics, and `NO_BACKEND_WINNER` behavior.

## Files Changed

- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
- `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w2.md`

No dependency files, compute scripts, Makefile, README final docs, PR state, source dataset paths, or generated Compute-W1 evidence were modified.

## Tests And Validation

- RED check before implementation:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_actual_dataloader_worker_bakeoff.py -v`
  - Result: expected import failure for missing adaptive timeout helper.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_actual_dataloader_worker_bakeoff.py -v`: PASS, `6 passed`.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS, `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: PASS.

## Generated Artifacts

- No Compute-W1 generated artifacts were modified or cleaned.
- No new persistent task-local generated benchmark artifacts were created by Data-W2.
- Focused tests used pytest temporary directories only.
- `datasets/readonly/**` was not mutated.

## Rerun Readiness

- Quality-R2 can proceed on this bounded repair.
- Compute-W2 can proceed after Quality-R2 approval.
- Compute-W2 should rerun the existing primary source-dataset matrix and confirm that the runner now either emits final metrics tables or fails with the new detailed bounded timeout diagnostic.
- This repair does not claim final benchmark PASS, backend winner, training readiness, or D1/D6 completion.

## Compliance

- DevSpace MCP: no.
- Subagents: none used; retired yes.
- Stage/commit/push/PR mutation: no.
- Compute/Slurm execution by Data-W2: no.
- Dependency/pyproject/requirements/Makefile/.github/AGENTS.md edits: no.
- `datasets/readonly/**` mutation: no.

## Conclusion

PASS_READY_FOR_QUALITY_R2
