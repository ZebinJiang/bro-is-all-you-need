# 30-OWNER Data Review

Task: `AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `cb5ca3f12e01d7900b2f04945db0137a6ba8a15c`
- `git status --short --branch`: branch tracks `origin/dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`; current candidate has modified README/docs/native timing file plus untracked fair native-loader source/test and this report path.
- `workspace_check`: PASS

## Scope Reviewed

- Source implementation:
  - `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
  - `autovla/dataloader/perf/native_loader_timing_v2.py`
- Focused tests:
  - `tests/dataloader/test_fair_native_loader_bakeoff.py`
- Rerun evidence:
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/fair-native-loader-bakeoff.md`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/shared-sample-window-manifest.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/fair-benchmark/generated-artifact-ledger.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/invalidation/pr30-invalidated-results-manifest.json`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.status`
  - `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/compute/fair-native-loader-srun.log`
- Compute owner evidence:
  - `coordination/reports/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001/owner-compute.md`

## Findings

No blocking Data issues found.

## Evidence Summary

- Compute rerun completed with `fair-native-loader-srun.status` containing `0`.
- The rerun log records `conclusion=NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.
- Result schema is `autovla.fair_native_loader_bakeoff.v1` with four rows:
  - `zjh_lerobot_v21_raw`
  - `zjh_lerobot_v3_local`
  - `zjh_webdataset_tar`
  - `zjh_robodm_container_v1`
- All four rows record:
  - `status=RUNNABLE_NOW`
  - `worker_count=8`
  - `batch_size=8`
  - `sample_count=2048`
  - `measured_batches=50`
  - `repeats=3`
  - `camera_payload_mode=materialized_rgb`
  - `payload_complete=true`
  - `missing_metrics=[]`
  - all external-effect flags false for real training, model load, checkpoint read, tokenizer load, HF network, W&B, endpoint, and robot.

## Data Contract Checks

- Identical subset/window manifest: PASS.
  - Shared manifest checksum: `4766c5bd89d40e3d3b8c94b655c0965c5860714138e16b313908758d934c42b4`.
  - Dataset root: `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`.
  - `max_episodes=16`, `max_samples=2048`, `seed=11`.
  - Manifest records 8 selected episodes, 2048 selected sample IDs, and 2048 selected window IDs.
  - `jq` equality check confirmed all four candidate rows carry the same ordered `sample_ids` array.
- Materialized payload completeness: PASS.
  - Result rows require `materialized_rgb`.
  - Candidate validation files report `camera_stream_count=3`, `payload_complete=true`, and `payload_missing_fields=[]`.
  - Generated artifact ledger includes 12,288 RGB payload sidecar files, matching 3 RGB payloads for 2048 samples across three converted candidates.
  - Implementation rejects `camera_refs`/stream-only payloads in `validate_benchmark_batch`.
- State/action/language/action_mask coverage: PASS.
  - `validate_materialized_payload` requires `action`, `language`, `state`, `action_mask`, and `deterministic_payload_hash`.
  - Result rows report no missing metrics and no missing payload fields.
- Fair raw/local-v3/WebDataset/RoboDM comparison: PASS for Data review.
  - Raw route remains source-native ffmpeg materialization.
  - Local v3 route writes/reads local parquet plus RGB sidecars.
  - WebDataset route writes/reads tar samples through the WebDataset package streaming reader.
  - RoboDM-style route writes/reads an AutoVLA-owned prototype JSONL/sidecar container and remains a prototype, not upstream Robo-DM package support.
  - The table explicitly does not select a final backend winner.

## Artifact And Dataset Safety

- Source dataset mutation: not observed.
  - Invalidation manifest records `source_dataset_mutation_status=not_mutated`.
  - Generated artifact ledger records `source_dataset_mutated=false`.
- Generated store location:
  - `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_fair_native_loader_bakeoff_v1`.
  - This path is outside the worktree git root but inside the root project `datasets/working/**` governed artifact area.
- Tracking/ignore status:
  - `git -C /home/cz-jzb/workspace/vla-flywheel ls-files datasets/working/autovla_fair_native_loader_bakeoff_v1` produced no tracked files.
  - Root `git check-ignore -v` reports `.gitignore:275:datasets/` for the generated store.
  - Worktree `git ls-files datasets/working runs/tmp` produced no tracked generated artifacts.

## Residual Risks

- The RoboDM-style `loader_contract.json` is prototype-specific and does not mirror the fair-loader contract fields present in the result row. This is not blocking for Data acceptance because the row, payload validation, artifact ledger, and rendered table carry the reviewed fair native-loader evidence, but future publication cleanup could make the candidate-local contract more uniform.
- `worker_count=8` is recorded as benchmark configuration in the result rows. This review focused on the requested Data fairness contract and did not independently require a separate per-worker execution ledger.

## Compliance

- DevSpace MCP: not used.
- Source/tests/docs/PR mutation by Data review: none, except this report file.
- Compute/Slurm run by Data review: none.
- PR #16 mutation: none.
- Stage/commit/push/PR/merge: none.
- Subagent ledger: none used; retired yes.

## Decision

APPROVE
