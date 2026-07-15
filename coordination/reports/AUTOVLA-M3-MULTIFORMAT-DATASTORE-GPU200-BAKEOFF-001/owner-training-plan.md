# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Owner Training Plan

## Workspace Verification

- role: `20-OWNER · Training`
- mode: read-only planning plus owner report only
- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`
- expected HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`
- workspace check: PASS
- note: shell emitted `whoami: cannot find name for user ID 2000`; this did not affect repository evidence.

## Evidence Reviewed

- owner packet:
  `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-packets/training-plan.md`
- task card:
  `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- training runtime surfaces:
  - `autovla/training/local_runner.py`
  - `autovla/training/cli.py`
  - `autovla/training/baseline_metrics.py`
- training tests:
  - `tests/training/test_baseline_metrics.py`
  - `tests/training/test_cli_local_smoke_execution.py`

## Training Position

Training planning is feasible within current scope. The bounded GR00T-N1D6 GPU200 telemetry tranche can stay real enough to exercise an actual 200-step data-to-runner path while still remaining clearly below long-training scope, provided the implementation keeps the existing AutoVLA dry-run discipline:

- bounded step count only: exactly 200 steps
- single-GPU telemetry only
- no optimizer-long-run success claim
- no checkpoint download or network dependency
- no W&B online sync or HF online operation
- no README/docs wording that implies backend winner equals training readiness

This is a telemetry-run contract, not a training-readiness declaration.

## Bounded 200-Step Telemetry Contract

The minimum Training contract should be:

- mode: a dedicated telemetry mode under `autovla/training/telemetry/**`, separate from readiness/local-smoke naming
- execution length: fixed bounded run with `max_steps=200`
- device scope: one governed GPU allocation only
- dataset contract: consume the shared deterministic sample/window manifest produced by Data work, not ad hoc per-backend sampling
- candidate scope: run only for candidates already classified runnable by the Data/Compute path
- output root: task-local governed output under `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
- side-effect boundary: telemetry/log/manifest outputs only; no long checkpoint series, no external sync, no endpoint/robot

The run should be real in the sense that it passes through a true bounded loader plus telemetry runner path on compute, but dry in the sense that it does not become a multi-epoch or checkpoint-producing training campaign.

## Minimal Loader Interface

Training does not need a full production dataloader API for this tranche. The minimal interface needed by the telemetry runner is:

- deterministic iterator over manifest-selected windows
- stable batch object compatible with current `CollatedBatch -> ModelInput` expectations
- explicit action/state/mask shapes carried through unchanged
- source/backend identifier in metadata so metrics can be attributed per candidate
- dataset, transform, and statistics fingerprints carried into runner manifests
- fail-closed behavior when a candidate cannot provide required fields for the telemetry runner

The loader interface should stay narrow:

- `iter_batches()` or equivalent bounded batch stream
- batch count/step budget awareness
- metadata hooks for backend candidate, manifest fingerprint, and source mix provenance

It should not introduce:

- distributed dataloader semantics
- long-horizon checkpoint orchestration
- mixed precision policy complexity
- tokenizer/model-family special cases inside the loader

## How To Keep It Dry While Still Real

The safest line is:

- real compute-node execution
- real candidate-specific store reads
- real bounded batch assembly
- real forward/telemetry collection
- no long training loop semantics beyond 200 steps

Concretely, Training recommends:

- one fixed 200-step budget per runnable candidate
- no claim of convergence, quality, or fine-tune viability
- at most bounded manifest/resume metadata sufficient for auditability
- avoid periodic checkpoint cadence; if a checkpoint manifest is needed, keep it single/bounded and document it as telemetry evidence only
- preserve existing fail-closed config validation patterns from `LocalRunnerConfig` and CLI config loaders

## Stable Metrics And Output Schema

The output schema should be stable enough to feed docs/README benchmark tables and future comparison logic. Minimum required fields:

- `schema_version`
- `candidate_id`
- `run_id`
- `mode`
- `model_registry_key`
- `dataset_fingerprint`
- `transform_fingerprint`
- `statistics_fingerprint`
- `manifest_fingerprint`
- `max_steps`
- `completed_steps`
- `completion_ratio`
- `status`
- `external_effects` all false except the governed local compute execution itself
- throughput metrics:
  - `steps_per_second`
  - `samples_per_second`
  - `batch_time_ms_p50`
  - `batch_time_ms_p95`
- loader/data wait proxies:
  - `data_time_ms`
  - `gpu_wait_for_data_ms` when observable, else explicit missing value
  - `decode_time_ms` when observable, else explicit missing value
  - `collate_time_ms` when observable, else explicit missing value
- memory/utilization fields only if reliably available from the governed run, otherwise explicit `missing`
- classification fields for:
  - `completed`
  - `cancelled_partial`
  - `failed_runtime`
  - `blocked_candidate`

For doc table feed, the JSON should remain canonical and the CSV/Markdown exports should be derived mechanically from that JSON rather than maintaining separate reporting logic.

## README And Docs Feed

Training wants docs/README consumption to stay table-driven and explicit:

- one per-candidate telemetry summary table
- one missing-telemetry table
- one environment/config table
- one interpretation note that says telemetry is bounded decision-support evidence, not training readiness

This avoids the common drift where README prose starts making stronger claims than the run artifacts justify.

## Checkpoint Decision

No immediate blocker requires `READY_FOR_USER_DECISION_MODEL_CHECKPOINT` at planning time.

The current runner surfaces already separate checkpoint manifest metadata from real model/checkpoint loading. Training approval assumes the telemetry tranche keeps checkpoint use to one of these two safe shapes:

- no checkpoint artifact at all
- one bounded telemetry manifest/checkpoint metadata record without checkpoint download/load semantics

If implementation later requires a real GR00T checkpoint compatibility decision beyond governed read-only local manifest usage, escalate to `READY_FOR_USER_DECISION_MODEL_CHECKPOINT`.

## Risks And Guardrails

- main risk: a “telemetry” runner quietly grows into an early fine-tune loop
- main guardrail: keep the step budget fixed at 200 and keep outputs framed as telemetry-only evidence
- main integration risk: backend candidate loaders exposing inconsistent action/state/mask fields
- main contract guardrail: shared deterministic sample/window manifest plus fail-closed loader validation
- main reporting risk: README/docs overclaiming a backend winner as training readiness

## Recommendation

Training recommends proceeding with planning under these constraints:

- build the telemetry runner as a bounded compute-only path under `autovla/training/telemetry/**`
- consume only the shared manifest-selected windows
- preserve current dry-run/local-runner config rigor
- emit one stable machine-readable telemetry summary that feeds docs tables
- keep model/checkpoint handling metadata-only unless a later explicit gate authorizes more

## Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

APPROVE
