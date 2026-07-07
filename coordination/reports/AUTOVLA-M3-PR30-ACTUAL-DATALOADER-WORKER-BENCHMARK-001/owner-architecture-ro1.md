# AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001 · Architecture RO1

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- expected HEAD: `2322606f26fecbef37eafdb7504c848d476cd29e`
- status before report write: `?? coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- workspace_check: PASS

## Evidence reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/AUTOVLA-M3-PR30-ACTUAL-DATALOADER-WORKER-BENCHMARK-001.yaml`
- `README.md`
- `docs/benchmarks/ADAPTER_PERFORMANCE_AUDIT_PR30.md`
- `docs/benchmarks/FAIR_NATIVE_LOADER_BAKEOFF_V2.md`
- `autovla/dataloader/perf/fair_native_loader_bakeoff.py`
- `autovla/dataloader/perf/native_loader_timing_v2.py`
- Read-only checks: workspace verification, `git diff --stat`, `git diff --cached --name-only`, focused `rg` over worker/adapter/fairness terms.

## Architecture decision

Conclusion: APPROVE_BOUNDARY

The requested actual dataloader worker benchmark is architecturally acceptable as a bounded PR #30 continuation if it remains a fairness/measurement task and does not become backend selection, training readiness, or runtime expansion. Current PR #30 docs and code already state that adapter-v1 numbers are diagnostic only and record `worker_count_label=configured_8` with `actual_worker_count=not_measured`; the new work must preserve that distinction and produce measured worker evidence before claiming actual worker-count behavior.

## Required guardrails

1. Prior adapter-v1 numbers are diagnostic-only.
   - They may remain as adapter-v0/v1 bottleneck evidence.
   - They must not be relabeled as actual W8 dataloader evidence.
   - They must not drive final backend selection.

2. No final backend winner unless mandatory candidates are comparable.
   - If any mandatory candidate is not runnable under the same manifest and actual-worker contract, the dashboard conclusion must stay no-winner, such as `NO_BACKEND_WINNER_CONTINUE_RAW_TELEMETRY`, or stricter.
   - Converted/prototype candidates must not win over blocked dependency candidates through fake equivalence.

3. `BenchmarkBatch` public surface should stay Data/perf-local.
   - It should represent a concrete batch of identical sample/window rows across candidates.
   - Required fields should include stable sample/window ids, action, language, state, action_mask, three materialized RGB payload proofs, payload hash/checksum, batch size, and manifest checksum.
   - It must reject `camera_refs`-only, path-only, missing RGB, missing action/state/mask, or non-identical sample windows.
   - It must not mutate M1/M2 dataloader contracts or become a training/model protocol.

4. `CandidateNativeAdapter` public surface should stay Data/perf-local.
   - It may define candidate id, native loader name, build/prepare hooks, batch read hook, cleanup/close hook, and instrumentation metadata.
   - It must hide backend-specific shortcuts behind the benchmark interface and must not expose raw model/training/runtime APIs.
   - It must not introduce dependency changes, compatibility shims, or PR #16 coupling.

5. Actual-worker evidence must be concrete.
   - Required report fields should separate `requested_worker_count`, `actual_worker_count`, `worker_execution_mode`, `worker_ids` or equivalent proof, per-worker sample counts, multiprocessing/prefetch status, and failure/blocker status.
   - A configured label alone is insufficient.
   - If actual worker proof is unavailable, the row must be diagnostic/not-run, not PASS evidence.

6. Same-manifest equivalence is mandatory.
   - All candidates must consume the same selected sample ids, window ids, camera keys, action/state/mask fields, seed, batch size, and bounded sample count.
   - A manifest checksum should be included in every candidate row.
   - Any candidate-specific sample subset, reordered manifest, or missing payload field invalidates comparability.

7. Anti-cheating rules.
   - No preloaded `SourceSample` lookup may be timed as native loader work.
   - No `camera_refs`-only or symlink/path-only payload can satisfy batch completeness.
   - No candidate may use post-hoc caches or in-memory preloads unless the same stage is explicitly measured and labeled outside comparable batch latency.
   - Source data under `datasets/readonly/**` must remain read-only.
   - Generated artifacts must stay under governed `datasets/working/**` or `runs/tmp/**` paths and must not be committed as product source.

8. Documentation language.
   - README and benchmark docs must keep "decision-support", "diagnostic-only", "draft PR", and "no final backend winner" wording unless all fairness gates pass.
   - Docs must not imply GPU200 training, fine-tune readiness, model quality, deployment, endpoint, robot use, or final data-backend selection.
   - Any ignored linked benchmark doc requires explicit publication handling before PR publication.

## Allowed/protected path assessment

Allowed implementation/review surface from the task card is coherent: `autovla/dataloader/perf/**`, `autovla/dataloader/stores/**`, `tests/dataloader/**`, benchmark docs/README, task reports, task-local runs evidence, and `datasets/working/autovla_actual_worker_bakeoff_v1/**`.

Protected surface remains excluded: `datasets/readonly/**`, checkpoints/model weights, robot endpoints, `.agent-docs/feature_list.json`, global/system env files, dependency specifications unless separately authorized, M1/M2 public contracts, model/training runtime activation, PR #16 mutation, PR ready/merge.

## Public contract and M1/M2 risk

No M1/M2 public contract break is required for the plan. `BenchmarkBatch` and `CandidateNativeAdapter` should be introduced only as AutoVLA Data/perf benchmark contracts. They should consume existing payload/materialization rules rather than modifying core dataloader or training/model APIs.

## Residual risks

- Actual worker measurement may expose runtime/tool-env or compute-node blockers; those should be classified as blocker/not-run evidence rather than filled with configured labels.
- The existing adapter-v1 implementation uses persistent reader caching for converted candidates; future actual-worker comparison must ensure any persistent-reader or cache stage is measured, shared, or excluded consistently.
- Publication can still be blocked if tracked docs link to ignored benchmark reports without explicit narrow force-add handling.

## DevSpace MCP compliance

DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash were not used. Evidence came from local shell/git/file inspection only.

## Model/thinking override record

User override recorded in the task card and followed for this review: model `gpt-5.5`, thinking `high`. No `thinking=max` was used or recommended.

## Subagent retirement ledger

- Child subagents used: none.
- Architecture RO1 owner review: direct read-only review.
- retired: yes.
