# Manager Summary

Task: `AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001`

Conclusion: `FORMAT_NATIVE_LOADER_BACKEND_DECISION_DRAFT_UPDATED`

## Scope

This task updates existing draft PR #18 with a format-native-loader backend
decision surface. It does not create a new PR, does not mutate PR #16, does not
start fine-tune, and does not mark PR #18 ready or merge it.

## Live PR State Before Publication

- PR #18: `https://github.com/ZebinJiang/bro-is-all-you-need/pull/18`
- PR #18 state: open draft
- PR #18 previous head: `56c55bfeb2ef33f736713a454484bbee5031908d`
- PR #18 base: `main`
- PR #16 state: open draft
- PR #16 head: `aaf3b79dccd1e82b57b09867b7ba3097f982b240`
- PR #16 mutation: none

## Implemented Update

- Added the format-native BenchmarkPayload contract in
  `autovla/dataloader/perf/bakeoff.py`.
- Added five required native-loader candidate rows:
  - `zjh_lerobot_v21_raw`
  - `lerobot_v3_converted`
  - `webdataset_converted`
  - `robodm_style_converted`
  - `zarr_converted`
- Added tests in `tests/dataloader/test_format_native_loader_bakeoff.py`.
- Updated `docs/benchmarks/README.md` to avoid linking to an ignored generated
  markdown report.
- Added required owner reports under
  `coordination/reports/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/`.
- Wrote required task-local technical reports under
  `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/`.

## Required Technical Reports

- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/gr00t-raw-loader-contract.md`
  - Conclusion: `GR00T_RAW_DATALOADER_UNSAFE_OR_UNAVAILABLE`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/dependency-and-safety-review.md`
  - Conclusion: `APPROVE_PARTIAL_FEASIBLE_BENCHMARKS`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/native-loader-backend-bakeoff-report.md`
  - Conclusion: `READY_FOR_USER_DECISION_BACKEND`
- `runs/tmp/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/generated-artifact-ledger.json`
  - `generated_artifacts_tracked=false`
  - `source_dataset_mutated=false`

## Owner Results

- Data: `PASS_IMPLEMENTATION`
- Data repair: `PASS_REPAIR_READY_FOR_REVIEW`
- Architecture rereview: `APPROVE`
- Quality rereview: `PASS`
- Training/Model/Tooling/Compute/Product/Deployment merge-ready reviews:
  skipped because the decision remains draft/user-gated and no backend winner
  or merge-ready state is claimed.

## Validation

- Focused pytest:
  `tests/dataloader/test_backend_bakeoff_dashboard.py tests/dataloader/test_format_native_loader_bakeoff.py`
  - PASS, 16 passed.
- Full dataloader pytest:
  - PASS, 166 passed.
- Meta policy pytest:
  - PASS, 27 passed.
- Ruff:
  - PASS.
- Black:
  - PASS via single-file `--workers 1` checks on changed Python files.
  - Two-file Black command was interrupted after hanging; this matches the known
    project-local Black batch behavior, and both changed Python files pass
    single-file checks.
- Pyright:
  - PASS, 0 errors, 0 warnings, 0 informations.
- `git diff --check`:
  - PASS.
- `bash scripts/quality/autovla_check_project_local.sh`:
  - PASS.
  - Product pytest: 333 passed.
  - Governance pytest: 27 passed.
  - Product/governance Black/Ruff/Pyright: PASS.

## Decision State

The format-native table is complete as a draft decision record, but it does not
claim compute-node W8 winner evidence. Current candidate rows are explicit:

- raw/GR00T-compatible path: unsafe/unavailable or compute-pending, no silent
  AutoVLA substitution;
- LeRobot v3: dependency blocked;
- WebDataset: compute pending in this PR18 format-native table;
- Robo-DM-style: compute pending / prototype-only;
- Zarr: dependency blocked.

Final decision remains user-gated:

`READY_FOR_USER_DECISION_BACKEND`

## Safety

- Source dataset remains read-only and unchanged.
- No generated artifacts under `datasets/working/**`, `datasets/derived/**`, or
  `runs/tmp/**` are staged for publication.
- No symlink-only candidate output is accepted as valid.
- No dependency files are changed by this format-native update.
- No real training, model load, checkpoint load, tokenizer load, HF/W&B network,
  endpoint, or robot behavior occurred.
- No DevSpace MCP was used.
- Root checkout was not used for implementation.

## Publication Plan

Stage only:

- `autovla/dataloader/perf/bakeoff.py`
- `docs/benchmarks/README.md`
- `tests/dataloader/test_format_native_loader_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-FORMAT-NATIVE-LOADER-BACKEND-BAKEOFF-001/`

Then run staged scans, commit, push
`dev/feat-autovla-m3-data-backend-bakeoff-dashboard`, and update PR #18 body as
a draft decision update. Do not mark ready and do not merge.

## Next Action

Use PR #18 as the review-visible decision record. If the user wants merge-ready
state later, assign a follow-up that runs the real compute-node native-loader W8
bakeoff or records explicit not-run decisions for every dependency-blocked
candidate with full Owner approval.
