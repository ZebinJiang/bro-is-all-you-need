# Owner Architecture Review

Task: `AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`
Role: `10-OWNER · Architecture`
Mode: read-only review plus assigned report write only
Decision: `REQUEST_CHANGES`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `cb5ca3f12e01d7900b2f04945db0137a6ba8a15c`
- Workspace check: `PASS`
- User/runtime override recorded: `model=gpt-5.5`, `thinking=high`
- `thinking=max` used: no

## Evidence Reviewed

- Current `git status --short --branch`
- Current tracked diff:
  - `README.md`
  - `autovla/dataloader/perf/native_loader_timing_v2.py`
  - `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
  - `docs/benchmarks/README.md`
- Current untracked candidate files:
  - `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - `tests/dataloader/test_fair_native_loader_bakeoff.py`
- Ignored PR-visible dashboard candidate:
  - `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`
- Task evidence:
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/invalidation/pr30-invalidated-results-manifest.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.md`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/generated-artifact-ledger.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/shared-sample-window-manifest.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.status`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.log`
  - `coordination/reports/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/owner-compute.md`

Read-only commands included workspace verification, `git diff`, `git status --short --ignored`, `git diff --check`, file inspection with `sed`, and targeted `rg` scans. No source, tests, docs, PR, git index, branch, dataset, checkpoint, or runtime artifact was modified by this Architecture review.

## Findings

### P1 - PR-visible docs link to an ignored/untracked dashboard file without a recorded force-add publication decision

Tracked docs now link to `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md` from `README.md`, `docs/benchmarks/README.md`, and `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`. The target file exists in the worktree, but `git status --short --ignored docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md` reports it as ignored (`!!`) and `git ls-files docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md` returns no tracked path.

That means the current publication surface would either ship broken tracked links or depend on an implicit force-add. Prior AutoVLA benchmark publication repairs have treated this exact class as requiring an explicit Manager publication decision/pathspec before Architecture approval. The fix can be narrow: either force-add exactly `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md` with the publication pathspec and scans recorded, or remove tracked links to the ignored/untracked dashboard and keep it task-local evidence only.

## Architecture Assessment

The fair native-loader rerun contract is otherwise architecturally sound:

- The invalidation manifest explicitly marks prior PR #30 benchmark numbers as invalid because the raw row used preloaded `SourceSample` lookup and `camera_refs`, and sets `must_not_use_for_backend_selection=true`.
- The fair rerun uses four candidates: `zjh_lerobot_v21_raw`, `zjh_lerobot_v3_local`, `zjh_webdataset_tar`, and `zjh_robodm_container_v1`.
- The fair benchmark evidence records `worker_count=8`, `batch_size=8`, `sample_count=2048`, `payload_complete=true`, and `camera_payload_mode=materialized_rgb` for every row.
- The implementation rejects `camera_refs`-only payloads and validates materialized RGB/state/action/action_mask payload completeness.
- The shared sample/window manifest keeps the comparison bounded and auditable.
- The generated artifact ledger records generated stores as ignored artifacts and `source_dataset_mutated=false`.
- The compute report and compute status support a successful bounded rerun with conclusion `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

## Boundary and Contract Review

- Final backend winner: not selected. Current result remains `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- Training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot scope: not introduced by the reviewed fair benchmark rows or docs.
- M1/M2 public contract regression: none found. The changed source is under `autovla/dataloader/perf/**`; no `genesisvla/**`, Model, Training runtime, dependency, workflow, pyproject, or requirements diff was found in the reviewed changed-file set.
- PR #30 invalidation: architecturally appropriate and necessary; prior unfair numbers must not drive backend selection.
- Fair native-loader boundary: acceptable, provided the publication surface blocker above is resolved before approval/publication.

## DevSpace MCP Compliance

- DevSpace MCP used: no
- `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash used: no
- Evidence source: local filesystem, local git, task-local reports/evidence only

## Subagent Ledger

- Child subagents used: none
- Child-agent depth: `0`
- Retirement status: `retired yes`

## Conclusion

`REQUEST_CHANGES`

The Architecture boundary for invalidating the unfair PR #30 benchmark and replacing it with a fair native-loader rerun is acceptable. Approval is blocked only by the PR-visible docs publication surface: tracked docs link to `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`, but that file is currently ignored and untracked with no recorded explicit force-add/publication decision.
