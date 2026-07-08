# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Data-W1

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- `git status --short --branch`: branch on required PR30 worktree; modified files are limited to Data-W1 source/test plus this report. Existing untracked coordination files from prior PR30 waves were not staged or mutated by this wave.

## Files Changed

- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
- `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001/owner-data-w1.md`

No dependency files, Makefile, README, final result docs, PR state, or dataset source paths were modified.

## Adapter/Runner Fixes

- Added a `CandidateAdapterSpec` / `AdapterBatchResult` layer so actual worker execution can rebuild a candidate-native reader inside each worker process.
- Preserved the legacy JSONL runner only for focused compatibility tests and D2 tiny fixture baseline; measured D3-D5 no longer share one common prebuilt payload JSONL.
- Added candidate-specific artifact routes:
  - D2 `zjh_lerobot_v21_autovla_adapter`: raw/source route materializes in worker for source runs; tiny route uses a D2-specific payload JSONL only for login-node tests.
  - D3 `zjh_lerobot_v3_local`: writes/reads a local-v3 parquet plus RGB sidecar artifact with persistent worker-local metadata.
  - D4 `zjh_webdataset_tar`: writes a WebDataset package TarWriter shard and reads it with worker-local streaming/cache semantics.
  - D5 `zjh_robodm_container_v1`: writes an owned RoboDM-style tar container plus index and reads grouped container payloads with persistent worker-local handles.
- Kept D1 `zjh_lerobot_v21_gr00t_or_lerobot_native` blocked as `NOT_RUN_UNSAFE_OR_UNAVAILABLE`.
- Kept D6 `zjh_zarr_cache` as `NOT_IMPLEMENTED_IN_CURRENT_PR`.
- Added worker evidence propagation for candidate adapter kind, persistent reader flag, process ids, worker ids, per-worker sample counts, and numeric `actual_worker_count`.
- Kept backend decision fail-closed as `NO_BACKEND_WINNER`; blocking missing telemetry remains explicit.

## Candidate Matrix Status

| Candidate | Data-W1 status |
|---|---|
| D1 `zjh_lerobot_v21_gr00t_or_lerobot_native` | `NOT_RUN_UNSAFE_OR_UNAVAILABLE`; no safe data-only native route proven. |
| D2 `zjh_lerobot_v21_autovla_adapter` | Runnable in tiny validation; source route defers raw materialization to worker. |
| D3 `zjh_lerobot_v3_local` | Runnable in tiny validation through local-v3 parquet/sidecar reader. |
| D4 `zjh_webdataset_tar` | Runnable in tiny validation through WebDataset package shard reader. |
| D5 `zjh_robodm_container_v1` | Runnable in tiny validation through owned prototype container reader; not actual Robo-DM. |
| D6 `zjh_zarr_cache` | `NOT_IMPLEMENTED_IN_CURRENT_PR`; optional and not added. |

## Validation

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_actual_dataloader_worker_bakeoff.py -v`: PASS, `5 passed`.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`: PASS after formatting this file.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS after formatting this file.
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py tests/dataloader/test_actual_dataloader_worker_bakeoff.py`: PASS, `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: PASS.

## Generated Artifacts

- No persistent task evidence or dataset working artifacts were generated outside pytest `tmp_path` during this Data-W1 validation.
- The implementation writes generated benchmark artifacts only under caller-provided `output_dir` and `working_root`; tests use temporary directories.
- `datasets/readonly/**` was not mutated.
- No generated artifacts were staged or committed.

## Remaining Quality/Compute Requirements

- Compute/HPC still needs to run the repaired entrypoint on the real readonly source dataset before PR30 can claim source-dataset evidence.
- This wave does not resolve D1 native GR00T/LeRobot route availability and does not implement D6 Zarr.
- Blocking prompt-contract telemetry remains visible for final benchmark acceptance: full persistent worker/prefetch matrix and several core timing fields are still fail-closed in `missing_telemetry_table`.
- No final backend winner is selected, and no training/fine-tune readiness is claimed.

## Compliance

- DevSpace MCP: no.
- PR #30 state mutation: no.
- PR #16 mutation: no.
- Stage/commit/push/merge/PR mutation: no.
- Compute/Slurm/GPU/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: no.
- Dependency/pyproject/requirements/Makefile/.github/AGENTS.md edits: no.
- Subagent ledger: none used; retired yes.

## Conclusion

PASS_READY_FOR_QUALITY_R1
