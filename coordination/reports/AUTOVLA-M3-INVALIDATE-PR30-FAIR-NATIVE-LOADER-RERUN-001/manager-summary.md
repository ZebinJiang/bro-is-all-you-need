# AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001 Manager Summary

## Conclusion

`PASS_PR30_DRAFT_UPDATED_PENDING_PUBLICATION`

PR #30's prior multiformat benchmark numbers were invalidated because the raw
row measured preloaded `SourceSample` lookup and `camera_refs`, not the same
materialized native-loader payload contract used by converted candidates.

The corrected fair native-loader rerun completed on Slurm/compute with all four
required candidates runnable and the conservative conclusion
`NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`.

## Scope

- PR: #30, `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- Source dataset:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- Generated store:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_fair_native_loader_bakeoff_v1`
- Evidence root:
  `runs/tmp/AUTOVLA-M3-INVALIDATE-PR30-FAIR-NATIVE-LOADER-RERUN-001`

## Implemented

- Added `autovla.dataloader.perf.fair_native_loader_bakeoff`.
- Added fair rerun tests for four candidates, materialized payload rejection,
  timing row validation, CLI entrypoint, and PR-visible invalidation docs.
- Exposed public helper wrappers from `native_loader_timing_v2` so the fair rerun
  does not depend on private helper imports.
- Replaced old active PR #30 telemetry wording with explicit invalidation.
- Added PR-visible `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`.
- Narrow force-added the ignored fair dashboard doc:
  `git add -f -- docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V1.md`.

## Corrected Benchmark Results

| Candidate | p50 ms | p95 ms | p99 ms | Samples/s | Frames/s | Conversion s | Artifact GB | Status |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| `zjh_lerobot_v21_raw` | 1412.945935 | 1649.215997 | 2093.333878 | 5.437251 | 16.311753 | 0.0 | 6e-07 | `RUNNABLE_NOW` |
| `zjh_lerobot_v3_local` | 43.912011 | 49.341909 | 54.92134 | 174.028064 | 522.084193 | 367.683332 | 1.211325296 | `RUNNABLE_NOW` |
| `zjh_webdataset_tar` | 224.916599 | 395.097018 | 426.476422 | 36.113377 | 108.34013 | 364.576253 | 1.221707328 | `RUNNABLE_NOW` |
| `zjh_robodm_container_v1` | 158.422529 | 182.784043 | 201.11354 | 47.459339 | 142.378016 | 366.478184 | 1.217494455 | `RUNNABLE_NOW` |

No final backend winner is selected.

## Validation

- Focused fair/native timing pytest: 11 passed.
- Product pytest: 428 passed.
- Model pytest: 5 passed.
- Governance pytest: 27 passed.
- Ruff: PASS.
- Pyright: PASS, 0 errors.
- `git diff --check`: PASS.
- Changed-path Black single-file checks: PASS.
- `scripts/quality/autovla_check_project_local.sh`: blocked by missing
  worktree-local `runs/tmp/m1-tool-venv` readiness stamp; direct root
  project-local toolenv validation passed.
- Combined changed-path Black invocation was interrupted after a tool hang;
  single-file checks passed for each changed Python file.

## Owner Reviews

- Architecture: initial `REQUEST_CHANGES` for ignored/untracked fair dashboard
  link; rereview `APPROVE` after narrow force-add.
- Data: `APPROVE`.
- Quality: `PASS`.
- Compute/HPC: `APPROVE_COMPUTE`.

All persistent Owner dispatches used user override `model=gpt-5.5` and
`thinking=high`. No `thinking=max` dispatch was used.

## Boundaries

- No DevSpace MCP used.
- No training run.
- No model/checkpoint/tokenizer load.
- No Hugging Face or W&B operation.
- No endpoint or robot behavior.
- No source dataset mutation.
- Generated `runs/tmp/**` and `datasets/working/**` artifacts remain ignored and
  untracked.

## Publication Notes

PR #30 should remain draft/open unless the user separately authorizes ready or
merge. This task updates the existing PR with the corrected fair native-loader
rerun and invalidation evidence only.
