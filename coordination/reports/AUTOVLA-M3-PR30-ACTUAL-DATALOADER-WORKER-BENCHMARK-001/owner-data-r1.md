# AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 Data-R1 Final Review

Role: 30-OWNER - Data

## Conclusion

APPROVE_REQUEST_CHANGES_DRAFT_UPDATE

Data-R1 approves the current PR30 actual-worker benchmark update as a request-changes draft update, not as final benchmark PASS, backend-winner evidence, merge readiness, training readiness, or format-selection evidence.

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `2322606f26fecbef37eafdb7504c848d476cd29e`
- Required branch/head: matched.
- Shell note: local shell startup prints `whoami: cannot find name for user ID 2000`; command exit codes and outputs were otherwise usable.

## Evidence Reviewed

- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
- `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`
- `README.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md`
- `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md`
- `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-data-w2.md`
- `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-quality-r2.md`
- `coordination/reports/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/owner-compute-w1r.md`
- Tiny Data-W2 evidence under `runs/tmp/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001/tiny-local-w2/**`

## Review Findings

No Data-R1 correctness blocker found.

The current source/test/docs state is consistent with Quality-R2:

- D2-D5 worker evidence is represented as actual-worker evidence for the Compute-W1R route, with worker counts `0,2,4,8` completed on the readonly source dataset.
- D1 `zjh_lerobot_v21_gr00t_or_lerobot_native` remains `NOT_RUN_UNSAFE_OR_UNAVAILABLE` / blocked; it is not silently omitted.
- D6 `zjh_zarr_cache` remains `NOT_IMPLEMENTED_IN_CURRENT_PR`; it is not treated as mandatory comparable evidence.
- `backend_decision_table` fail-closes to `NO_BACKEND_WINNER`.
- The docs/README preserve no-backend-winner wording and do not claim final benchmark PASS, training format selection, fine-tune readiness, model quality, or deployment readiness.
- Missing prompt-contract timing/metric coverage is surfaced through `missing_telemetry_table` with blocking status.

## Payload And Manifest Semantics

Reviewed code and tiny evidence show the expected Data contract surfaces:

- `BenchmarkPayload` requires action, state, language, action mask, three RGB byte payloads, sample id, episode id, window id, and deterministic payload hash.
- `validate_benchmark_payload` rejects camera-refs-only/proof-only rows for RUN payloads.
- `collate_benchmark_batch` validates payloads before hashing batch content.
- Shared sample/window manifest records sample ids, window ids, source dataset, seed, camera policy, decode policy, and checksum.
- Tiny Data-W2 evidence shows identical manifest checksum across D1-D6 rows in payload completeness output.

Residual caveat: the implementation still materializes candidate payload artifacts before worker execution; this is acceptable for the current request-changes draft posture because docs and decision tables do not claim final comparable backend PASS.

## Candidate And Worker Evidence Semantics

Reviewed evidence supports the current labels/statuses:

- D1: `NOT_RUN_UNSAFE_OR_UNAVAILABLE`
- D2: runnable adapter row when actual worker evidence exists
- D3: runnable local-v3 row when actual worker evidence exists
- D4: runnable WebDataset-tar row when actual worker evidence exists
- D5: runnable RoboDM-container row when actual worker evidence exists
- D6: `NOT_IMPLEMENTED_IN_CURRENT_PR`

Tiny Data-W2 worker evidence records numeric `actual_worker_count`, process ids, worker ids, per-worker sample counts, execution mode, and `worker_count_evidence_status=PASS` for runnable rows. Not-run rows do not pretend worker evidence exists.

Compute-W1R separately recorded real source-dataset execution for D2-D5 at worker counts `0,2,4,8`, but correctly concluded `REQUEST_CHANGES_COMPUTE_EVIDENCE`.

## Generated Artifact And Source Dataset Safety

Checks performed:

- `git ls-files runs/tmp runs/slurm_debug datasets/working datasets/readonly checkpoints`
  - Result: no tracked generated evidence, source dataset files, working dataset artifacts, or checkpoints.
- `git check-ignore -v` confirmed:
  - `runs/tmp/**` evidence is ignored.
  - `datasets/working/**` generated working artifacts are ignored.
  - `docs/benchmarks/ACTUAL_DATALOADER_WORKER_BAKEOFF.md` and `docs/benchmarks/PR30_RESULT_CONSISTENCY_AUDIT.md` are also ignored by the current `.gitignore` rule.
- Tiny generated artifact ledger records `generated_artifacts_tracked=false` and `tracked_status=ignored_generated_artifact`.
- Source dataset mutation check evidence records `source_dataset_mutation_check: PASS`.

Publication caveat: if `ACTUAL_DATALOADER_WORKER_BAKEOFF.md` or `PR30_RESULT_CONSISTENCY_AUDIT.md` must be visible in PR #30, the publication step needs an explicit narrow force-add decision. This is a publication-surface caveat, not a Data correctness blocker for the current request-changes draft update.

## Validation Evidence Reviewed

Quality-R2 reports:

- Focused pytest: PASS, `5 passed`.
- Py compile: PASS.
- Ruff: PASS.
- Pyright: PASS, `0 errors, 0 warnings, 0 informations`.
- Black single-file checks: PASS.
- `git diff --check`: PASS.

Data-R1 also ran read-only inspection/scans:

- Workspace/root/branch/head verification: PASS.
- Stale-claim scan across reviewed README/docs: no blocking stale final-winner or training-readiness claim found.
- `git diff --check`: PASS.
- `git ls-files runs/tmp runs/slurm_debug datasets/working datasets/readonly checkpoints`: empty.
- Tiny evidence table inspection: `NO_BACKEND_WINNER`, payload completeness for D2-D5, D1/D6 not-run rows, and worker evidence were consistent with request-changes semantics.

## Residual Risks

- D1 remains blocked and therefore the benchmark cannot be final comparable PASS evidence.
- D6 remains optional/not implemented in current PR.
- Persistent-worker and prefetch matrix evidence is missing.
- Prompt-contract timing/metric coverage remains incomplete and blocking for final benchmark acceptance.
- Some publication surfaces are ignored and require explicit narrow staging if they are intended to be PR-visible.
- No backend winner or training format has been selected.

## Compliance And Ledger

- DevSpace MCP / vla-flywheel-devspace / MCP open_workspace/read/write/edit/bash: no.
- Source/test/docs/config/dependency modification by Data-R1: no.
- Git stage/commit/push/PR mutation: no.
- Compute/Slurm rerun: no.
- Training/model/checkpoint/tokenizer/HF/W&B/endpoint/robot: no.
- Source dataset mutation: no.
- Subagents: none used.
- Retirement: Data-R1 complete; retired yes.
