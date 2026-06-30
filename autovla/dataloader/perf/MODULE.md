# autovla.dataloader.perf Module Guide

## Purpose

`autovla.dataloader.perf` owns bounded DataLoader performance probes and the
PFS-backed AutoVLA Training Store v0 evidence path. It measures metadata
inspection, raw bounded-decode latency, training-store build/read metrics,
missing GPU telemetry, and PFS shard/index behavior without starting real
training.

## Public contracts

- `PerfBenchmarkConfig` validates adapter, dataset, output directory,
  `training_store_dir`, mode, and bounded sample limits.
- `PerfMetrics` publishes stable JSON metrics including latency, wait, decode,
  transform, tokenization, collate, throughput, GPU telemetry, and
  `missing_metrics`.
- `run_benchmark()` writes `perf_report.json`, `perf_report.md`,
  `metrics_timeseries.jsonl`, `environment.json`, `dataset_probe_summary.json`,
  and `recommendations.md`.
- Training Store modes write `training_store_manifest.json`,
  `sample_index.jsonl`, `episode_index.jsonl`, `shards/*.npz`,
  `stats/action_statistics.json`, `checksums.json`, `build_report.json`, and
  `read_benchmark_report.json` under the caller-provided PFS store directory.
- Persistent ZJH modes are thin extensions of the same contract:
  `pfs-training-store-build` writes a fingerprinted store under
  `datasets/derived/autovla_training_store/<dataset_id>/<dataset_fingerprint>/`
  and emits `resolved_store_path.txt` in the report output directory;
  `pfs-training-store-read` reads that resolved store and writes
  `reports/read_benchmark_report.json`.
- Raw/store reports preserve raw batch latency and raw media decode as separate
  fields. `speedup_vs_raw_decode` uses an explicit effective raw comparator,
  choosing the media-decode bottleneck when it dominates raw batch latency.
- `classify_perf_report()` returns `PASS`, `WARN`, `FAIL`, or
  `INSUFFICIENT_TELEMETRY`.
- `classify_training_store_comparison()` classifies raw-vs-store comparison
  telemetry for merge gating.

## Directory structure

- `config.py`: benchmark config validation and JSON roundtrip.
- `metrics.py`: metrics schema and percentile helpers.
- `profiler.py`: telemetry parsers that do not invoke external commands.
- `benchmark.py`: bounded benchmark execution and report file writing.
- `training_store.py`: PFS Training Store v0 manifest, index, shard, checksum,
  build, and read-benchmark helpers.
- `report.py`: report classification, Markdown rendering, baseline comparison,
  and PFS Training Store schema draft.
- `cli.py` and `__main__.py`: `python -m autovla.dataloader.perf benchmark`.

## Naming conventions

- Modes use kebab-case: `metadata-only`, `bounded-decode`, `training-view`,
  `store-plan`, `store-build-bounded`, `store-read-benchmark`,
  `pfs-training-store-build`, and `pfs-training-store-read`.
- Report files use stable lower snake case names.
- Metrics names match the task gate vocabulary, for example
  `data_wait_time_ms`, `batch_latency_ms_p95`, and `gpu_util_pct`.

## Extension points

- Add adapter-specific probes by calling the existing dataset adapter registry.
- Add real media decode only in a future task that authorizes a decode backend
  and compute-node validation.
- Add GPU telemetry collection by shelling out only from governed compute jobs;
  keep parser functions pure and fixture-testable.
- Add future Training Store backends behind the manifest/index/shard contract
  after dependency and storage-format review.

## Modify vs extend rule

Extend this package for new probe modes or metrics. Modify shared dataloader
contracts only if the new metric changes every adapter contract and has tests.

## Invariants

- Metadata-only mode reads only metadata, info, and tasks files.
- Bounded-decode mode must run on a compute node context.
- Outputs must never be written under the dataset root.
- Training Store outputs must use `storage_backend: pfs_shared` and
  `local_stage_used: false`.
- Training Store modes must never write into `datasets/readonly`.
- Persistent Training Store artifacts belong only under ignored
  `datasets/derived/autovla_training_store/**`; they are generated data and
  must never be staged or committed.
- Missing telemetry must be explicit and must not be fabricated.
- The harness must not invoke real training, model load, checkpoint read, W&B,
  Hugging Face, endpoint, or robot behavior.

## Performance requirements

- Probe defaults stay bounded: four episodes and 512 samples.
- The first Training Store implementation is deterministic and emits PFS-backed
  JSON/JSONL/NPZ evidence before real finetune is considered.
- `FULL_STORE_READY` requires source-derived rows, checksums, a read benchmark,
  and full intended coverage. `PARTIAL_STORE_READY_FOR_FORMAT_REVIEW` is useful
  only for schema/layout review and does not authorize a fine-tune dry-run.
- Data wait, decode, tokenization, transform, collate, and cache metrics are
  separate fields so bottlenecks are visible.
- Raw bounded-decode evidence must remain preserved when store-read comparison
  evidence is generated.

## Tests/gates

- Focused tests live in `tests/dataloader/test_perf_harness.py`.
- Required gates are focused pytest, Black, Ruff, strict Pyright,
  `make autovla-check`, build verification, scans, and compute-node bounded
  probe evidence when available.

## Agent workflow

1. Verify the task worktree is the perf harness branch.
2. Run metadata-only tests before compute-node probes.
3. Run bounded-decode only from an authorized compute context.
4. Store task evidence under `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/`.
5. Do not publish a PR if scans find secrets, large artifacts, dataset copies,
   or dependency changes.

## Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.
- writing report outputs inside `datasets/readonly`.
- describing the PFS Training Store as node-local storage or local staging.
