# AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001 Data Owner Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `f194b6e8d3d6679448749da36e6bfc68f690ef91`
- status before final report:
  - modified: `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - modified: `tests/dataloader/test_fair_native_loader_bakeoff.py`
  - untracked: `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/`

## Changed Files

- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - Added adapter version field with `adapter_v0` / `adapter_v1` validation.
  - Added required stage taxonomy and schema validation for:
    `source_row_load`, `materialize_payload`, `build_artifact`, `reader_init`,
    `batch_read`, `payload_validate`, `report_write`.
  - Added adapter stage table outputs:
    `adapter_stage_timing_v0.{json,csv,md}`,
    `adapter_stage_timing_v1.{json,csv,md}`,
    `adapter_v0_vs_v1_summary.{json,csv,md}`,
    `adapter_bottleneck_table.{json,csv,md}`,
    `backend_decision_status.md`.
  - Added explicit `worker_count_label` vs `actual_worker_count` separation.
    Current bounded rerun records `worker_count_label=configured_8` and
    `actual_worker_count=not_measured`; it does not claim actual 8-worker
    execution evidence.
  - Added bounded adapter-v1 reader behavior:
    WebDataset one-time shard scan/cache, RoboDM-style persistent index/sidecar
    cache, and LeRobot-v3 local parquet/sidecar cache.
  - Preserved raw route as `adapter_v1` row with raw ffmpeg/materialization cost
    separated in stage table rather than claiming raw reader optimization.
- `tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Added coverage for stage schema, adapter-v1 summary outputs, worker-count
    label vs actual count, persistent converted readers, and no backend winner.
- This report.

No dependency, pyproject, requirements, source dataset, generated dataset,
Slurm, training, model/checkpoint/tokenizer, W&B/HF, endpoint, robot, commit,
push, stage, or PR mutation was performed.

## Suspected Item Verification / Refutation

- `fair_native_loader_bakeoff.py`: confirmed adapter-v0 risk. Corrected PR #30
  fair native-loader V1 evidence is now treated as adapter-v0 baseline, and the
  new bounded adapter-v1 run emits stage tables and v0/v1 summary rows.
- `native_loader_timing_v2.py`: not modified in this wave. Existing timing path
  remains the underlying materialized payload source; this wave did not broaden
  timing-v2 behavior.
- `stores/lerobot_v21_reader.py`: not modified. Raw v2.1 remains baseline/raw
  context; no final backend claim is made.
- `stores/lerobot_v3_reader.py`: not modified. The PR30 fair benchmark path now
  uses a bounded cached local-v3 reader in `fair_native_loader_bakeoff.py` for
  adapter-v1 measurement rather than changing store-wide reader contracts.
- `stores/webdataset_reader.py`: not modified. The adapter-v1 benchmark path uses
  one-time WebDataset shard scan/cache in the fair benchmark module to avoid
  per-batch shard-start rescans in this bounded audit.
- `stores/robodm_reader.py`: not modified. The adapter-v1 benchmark path uses a
  persistent RoboDM-style bounded prototype reader/cache in the fair benchmark
  module.
- builders: not modified. This wave did not alter datastore build contracts.
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`: not modified; the existing
  corrected V1 evidence remains adapter-v0 baseline.
- `README.md` and PR-visible benchmark docs: not completed before Manager stop
  request. This is a publication-surface gap and the main reason this report
  concludes `REQUEST_CHANGES` rather than pass.

## Bounded Adapter-v1 Evidence

Command completed on login node without GPU/Slurm/training:

```bash
/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python \
  -m autovla.dataloader.perf.fair_native_loader_bakeoff \
  --source-dataset /home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz \
  --working-root /home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_fair_native_loader_bakeoff_v2 \
  --output-dir runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun \
  --gr00t-root /home/cz-jzb/workspace/Isaac-GR00T17 \
  --worker-count 8 --batch-size 8 --warmup-batches 2 \
  --measured-batches 8 --repeats 1 --max-episodes 4 --max-samples 128 --seed 11
```

Result: `conclusion=NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

Generated evidence path:

- `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun/`

Generated evidence files refreshed at 2026-07-07 22:51:

- `fair-native-loader-bakeoff.{json,csv,md}`
- `adapter_stage_timing_v0.{json,csv,md}`
- `adapter_stage_timing_v1.{json,csv,md}`
- `adapter_v0_vs_v1_summary.{json,csv,md}`
- `adapter_bottleneck_table.{json,csv,md}`
- `backend_decision_status.md`
- `generated-artifact-ledger.json`
- `shared-sample-window-manifest.json`

Generated working artifacts:

- `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_fair_native_loader_bakeoff_v2`

The generated artifacts are task/local evidence only and were not staged or
committed.

## Adapter-v0 vs Adapter-v1 Metrics

Adapter-v0 values are the existing corrected fair native-loader V1 baseline.
Adapter-v1 values are the bounded 128-sample login-node rerun above. These rows
are diagnostic only; they must not be used as final backend selection.

| Candidate | v0 p50 ms | v0 p95 ms | v0 samples/s | v1 p50 ms | v1 p95 ms | v1 samples/s | v1 persistent reader | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |
| `zjh_lerobot_v21_raw` | 1412.945935 | 1649.215997 | 5.437251 | 1011.893106 | 1085.541792 | 6.429297 | false | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_lerobot_v3_local` | 43.912011 | 49.341909 | 174.028064 | 0.091163 | 0.097437 | 67790.542926 | true | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_webdataset_tar` | 224.916599 | 395.097018 | 36.113377 | 0.154350 | 0.165612 | 39933.333567 | true | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_robodm_container_v1` | 158.422529 | 182.784043 | 47.459339 | 0.101197 | 0.114727 | 62410.635260 | true | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |

Stage bottleneck table reports `materialize_payload` as the largest measured
stage for all four candidates in this bounded run. Converted reader batch-read
latencies are now dominated by cached/persistent benchmark reader behavior, so
the numbers are useful for adapter-overhead diagnosis but require Manager/Compute
interpretation before any performance claim.

## Prompt Checklist

- Required stage list semantics: implemented for all seven required stages, with
  `not_applicable` sentinel values for raw/nonconverted stages instead of blanks.
- Generated artifact ledger output: implemented and generated at
  `fair-native-loader-rerun/generated-artifact-ledger.json`.
- README/docs updates: incomplete. `README.md`,
  `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`, and
  `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md` were not completed before
  stop/wrap.
- Worker-count label vs actual worker count: implemented; bounded rerun records
  `worker_count_label=configured_8`, `actual_worker_count=not_measured`,
  `multiprocessing_enabled=false`, `prefetch_enabled=false`, and
  `persistent_reader_enabled` per row.
- No-final-backend-winner wording: implemented in generated
  `backend_decision_status.md` and row/table decision status.
- No GPU200/Slurm/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot:
  preserved.

## Validation Results

- TDD RED:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_fair_native_loader_bakeoff.py -q`
  - Initial result before implementation: expected import failure for missing
    `REQUIRED_STAGE_COLUMNS`.
- Focused pytest:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_fair_native_loader_bakeoff.py -v`
  - Result: `6 passed`.
- Ruff:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: `All checks passed!`.
- Pyright:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: `0 errors, 0 warnings, 0 informations`.
- Py compile:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: pass.
- Black:
  - Single file checks passed before the final baseline-summary patch.
  - Final combined targeted check on both files did not return within 30 seconds
    and was interrupted with exit 130 per Manager stop/wrap direction.
  - This remains an incomplete validation item.
- `git diff --check`: pass.
- Generated artifact tracking scan:
  - `git ls-files datasets/working runs/tmp`
  - Result: no tracked generated artifacts listed.

## Residual Risks / Required Follow-up

- PR-visible documentation surfaces are incomplete. Manager should dispatch a
  narrow docs/report follow-up if this source/test direction is acceptable.
- Final Black proof after the last patch is incomplete because combined targeted
  Black hung/stalled and was interrupted under the stop/wrap instruction.
- The bounded adapter-v1 run is only 128 samples and records
  `actual_worker_count=not_measured`. It is not GPU200 evidence and does not
  prove actual 8-worker execution.
- Adapter-v1 converted reader caches intentionally remove per-batch adapter
  overhead for diagnosis. That is useful for overhead isolation, but not a final
  production-loader winner claim.
- Store-wide `autovla/dataloader/stores/**` readers/builders were not modified;
  optimization is currently scoped to the PR30 fair benchmark module.

## Governance

- DevSpace MCP: not used.
- Subagents: none used; retired yes.
- PR #30: left draft/open; no PR mutation.
- PR #16: untouched.
- Git actions: no stage, no commit, no push, no merge.
- Source dataset mutation: no writes to `datasets/readonly/**`.
- Generated artifacts committed: no.

## Conclusion

REQUEST_CHANGES

Rationale: the bounded adapter-v1 profiler/reader source and focused tests are
partially implemented and green, and regenerated task-local evidence exists.
However, required README/docs publication surfaces and final Black validation are
incomplete under the Manager stop/wrap request. This should not be accepted as a
finished PR30 Data implementation yet.
