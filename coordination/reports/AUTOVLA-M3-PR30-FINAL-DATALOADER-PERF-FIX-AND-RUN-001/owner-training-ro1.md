# AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001 Owner Training-RO1

Role: 20-OWNER - Training
Wave: 1 read-only Training hot-path relevance and fairness planning
Runtime override: model=`gpt-5.5`, thinking=`high`; xhigh not used; max not used.

## Workspace verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `882b24af518fe1676fdb5430e52d3877d018084a`
- `git status --short --branch`: branch matches origin; only task/report paths were untracked at review time.

Workspace check: PASS.

## Evidence reviewed

- Active task card for `AUTOVLA-M3-PR30-FINAL-DATALOADER-PERF-FIX-AND-RUN-001`
- Prior PR30 Manager summary and Data-W2 / Quality-R2 / Compute-W1R / Quality-W1 evidence
- Current README and benchmark docs
- `autovla/dataloader/perf/actual_dataloader_worker_bakeoff.py`
- `tests/dataloader/test_actual_dataloader_worker_bakeoff.py`

## Training relevance assessment

The actual-worker dataloader benchmark is relevant to future training ingestion after Data fixes. It moves PR30 away from configured-worker/proof-only timing and toward materialized payloads, measured process workers, per-worker sample counts, and explicit missing telemetry. That is the right foundation for local training data readiness without starting a trainer.

Training does not approve the current surface as final training readiness. It is only a dataloader-performance evidence path. The final compute run should remain bounded to dataloader I/O/materialization and should not load a model, checkpoint, tokenizer, optimizer, Hugging Face asset, W&B service, endpoint, robot, or GPU200 training path.

## Required Data-W1 fixes before compute

- Ensure RUN rows expose the full training-consumption payload contract: action, language, three materialized RGB payloads, state or state-not-available reason, bool action_mask or action-mask-not-available reason, sample_ids, episode_ids, and deterministic payload_hash.
- Preserve the current rejection of camera_refs-only/proof-only/preloaded `SourceSample` evidence.
- Make `worker_count=8` and `batch_size=8` the primary final comparison row, with actual worker count, worker ids/process ids, per-worker sample counts, sample count, and batch count.
- Resolve D1 comparability before final ranking, either by safe materialized native route or by explicit scope narrowing that prevents all-backend ranking claims.
- Keep D6 optional unless separately implemented; do not claim its absence proves training readiness.
- Replace default-zero timing placeholders with measured values or explicit blocking missing telemetry for p50/p95/p99, first batch latency, samples/sec, worker queue wait, collate, decode/materialization, bytes/read throughput, file opens, RSS, and CPU metrics.
- Provide enough warmup/measured/repeat evidence for percentile metrics, and either implement or explicitly block persistent-worker/prefetch-factor matrix coverage.

## Documentation wording constraints

Docs may say final dataloader performance comparison/ranking only after scoped benchmark gates pass. Docs must not claim training readiness, fine-tune readiness, model quality, selected training format, production backend winner, GPU200 training pass, or ready-to-train GR00T status. Existing request-changes/draft posture should remain until Data/Compute/Quality close the final benchmark blockers.

## No-real-training compliance

- Training-RO1 ran no training.
- No model, checkpoint, tokenizer, HF/W&B network, GPU200 training, endpoint, or robot behavior was activated.
- Source/tests/docs/config were not modified by Training-RO1.
- Only the two allowed reports were written.
- DevSpace MCP: no.
- Git/PR mutation: no.
- Subagents: none used; retired yes.

## Conclusion

APPROVE_TRAINING_RELEVANCE_AFTER_DATA_FIXES
