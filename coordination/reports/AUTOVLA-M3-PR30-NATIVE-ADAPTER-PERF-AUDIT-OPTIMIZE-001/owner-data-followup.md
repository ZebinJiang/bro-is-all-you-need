# AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001 Data Follow-up

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `f194b6e8d3d6679448749da36e6bfc68f690ef91`
- PR #30: not mutated; no stage, commit, push, mark-ready, merge, or PR update.

## Changed Files

- `README.md`
- `docs/benchmarks/README.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `tests/dataloader/test_fair_native_loader_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/owner-data-followup.md`

Carry-over source/test changes from the prior Data wave remain present in:

- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`

## Follow-up Summary

- Used existing generated evidence only:
  `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun`.
- Did not rerun the fair native-loader benchmark.
- Added PR30 adapter audit documentation stating:
  - corrected PR30 V1 fair native-loader result is the adapter-v0 baseline;
  - bounded adapter-v1 profiling is diagnostic only;
  - no final backend winner is selected;
  - no GPU200, Slurm, training, model/checkpoint/tokenizer, W&B/HF, endpoint, or robot behavior occurred;
  - `worker_count_label=configured_8` is only a configured label;
  - `actual_worker_count=not_measured`.
- Added the v0/v1 summary table from the Data Owner report to
  `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`.
- Added `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md` as a bounded
  adapter-v1 diagnostic summary.
- Updated existing benchmark README, root README, and V1 dashboard to point at
  the adapter audit / V2 surfaces.
- Updated focused docs consistency test coverage.

## Adapter-v0 vs Adapter-v1 Table

| Candidate | v0 p50 ms | v0 p95 ms | v0 samples/s | v1 p50 ms | v1 p95 ms | v1 samples/s | worker_count_label | actual_worker_count | Decision |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| `zjh_lerobot_v21_raw` | 1412.945935 | 1649.215997 | 5.437251 | 1011.893106 | 1085.541792 | 6.429297 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_lerobot_v3_local` | 43.912011 | 49.341909 | 174.028064 | 0.091163 | 0.097437 | 67790.542926 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_webdataset_tar` | 224.916599 | 395.097018 | 36.113377 | 0.154350 | 0.165612 | 39933.333567 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |
| `zjh_robodm_container_v1` | 158.422529 | 182.784043 | 47.459339 | 0.101197 | 0.114727 | 62410.635260 | `configured_8` | `not_measured` | `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY` |

## Validation Results

- Py compile:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: PASS.
- Focused pytest:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_fair_native_loader_bakeoff.py -v`
  - Result: `6 passed`.
- Ruff:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: `All checks passed!`.
- Black, source file:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - Result: PASS, unchanged.
- Black, focused test:
  - Manager found this file needed formatting; Data ran:
    `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --line-length 100 --workers 1 tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Then Data reran:
    `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: PASS, unchanged.
- Pyright:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/perf/fair_native_loader_bakeoff.py tests/dataloader/test_fair_native_loader_bakeoff.py`
  - Result: `0 errors, 0 warnings, 0 informations`.
- `git diff --check`: PASS.

## Generated Artifact / Publication Notes

- No new benchmark rerun was performed.
- No generated dataset/store artifact was mutated in this follow-up.
- Existing generated evidence remains under:
  `runs/tmp/AUTOVLA-M3-PR30-NATIVE-ADAPTER-PERF-AUDIT-OPTIMIZE-001/fair-native-loader-rerun`.
- Existing generated working artifacts remain under:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_fair_native_loader_bakeoff_v2`.
- `git status --ignored` reports the new docs as ignored:
  - `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
  - `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- If these files must be PR-visible, publication needs an explicit force-add or
  ignore exception by the publication owner. Data did not stage files.

## Residual Risks

- Adapter-v1 remains diagnostic only and should not be used to select a final
  backend winner.
- `actual_worker_count` remains `not_measured`; the configured worker-count
  label must not be interpreted as actual eight-worker evidence.
- The two new docs are currently ignored by gitignore policy and need explicit
  publication handling if they are intended to appear in PR #30.

## Compliance

- DevSpace MCP: not used.
- Subagents: none used; retired yes.
- PR #30: not mutated; draft/open state untouched.
- PR #16: untouched.
- Git actions: no stage, no commit, no push, no merge.
- Dependencies: not modified.
- Source dataset: not modified.
- Compute/Slurm/GPU/training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot:
  not used.

## Conclusion

PASS
