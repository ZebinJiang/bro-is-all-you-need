# AutoVLA DataLoader Performance Harness

## Purpose

The DataLoader Performance Harness makes dataset/input-pipeline cost
measurable before real finetune. It turns suspected GPU wait into bounded
evidence with explicit missing telemetry, then compares the raw bounded-decode
path with the PFS-backed AutoVLA Training Store v0 read path.

There is no usable compute-node local disk or local NVMe staging surface for
this workflow. The optimization target is therefore a shared-PFS Training Store,
not node-local cache materialization.

## Public contracts

- CLI: `python -m autovla.dataloader.perf benchmark`.
- Config: `PerfBenchmarkConfig`.
- Metrics: `PerfMetrics`.
- Reports: `perf_report.json`, `perf_report.md`, `metrics_timeseries.jsonl`,
  `environment.json`, `dataset_probe_summary.json`, and `recommendations.md`.
- PFS Training Store v0: `training_store_manifest.json`, `sample_index.jsonl`,
  `episode_index.jsonl`, bounded `.npz` shards, statistics, checksums, build
  report, and read benchmark report under governed task evidence.

## Directory structure

- Runtime code lives under `autovla/dataloader/perf/`.
- Focused tests live under `tests/dataloader/test_perf_harness.py`.
- Initial harness evidence belongs under
  `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/`.
- PFS Training Store builder evidence belongs under
  `runs/tmp/AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001/`.

## Naming conventions

Use stable metric names from the M3.2 gate: `samples_per_second`,
`episodes_per_second`, `batch_latency_ms_p50`, `batch_latency_ms_p95`,
`data_wait_time_ms`, `compute_placeholder_time_ms`, and `data_to_compute_ratio`.

## Extension points

Future tasks may add real decode backends, richer GPU telemetry commands, or
new Training Store backends. WebDataset, Arrow, Parquet, and Megatron-style
indexed backends should be revisited only after the PFS v0 manifest/index/shard
contract has enough compute evidence to justify a format migration.

## Modify vs extend rule

Extend the perf package for new probes. Modify adapter contracts only when a
new invariant applies to every dataset adapter.

## Invariants

- No full dataset conversion.
- No model/checkpoint/tokenizer loading.
- No W&B/HF network.
- No hidden generated dataset artifact in git.
- Bounded-decode runs only on compute nodes.
- Training Store builder outputs stay under ignored `runs/tmp` evidence.
- The source dataset path under `datasets/readonly` is never modified.
- The PFS Training Store must not be described as local NVMe staging.

## Performance requirements

The harness must separate inspect, index, decode, transform, tokenization,
collate, data wait, and compute placeholder time. Missing GPU telemetry is a
classification input, not a reason to fabricate utilization.

The raw bounded-decode probe failed because measured media decode dominated the
per-batch proxy. The PFS Training Store reduces that bottleneck by replacing
per-step media decode and repeated metadata assembly with deterministic
prepacked shard reads plus sample/episode index lookup.

## Tests/gates

Focused tests verify config, metrics, report classification, CLI behavior,
output safety, no source dataset writes, baseline comparison, GPU telemetry
missing paths, and Fast Training View schema.

## Agent workflow

Agents run metadata-only validation locally, then compute-node bounded probes
only after the task authorizes compute resources. Training Store build/read
evidence must use shared-PFS output directories, record checksums and missing
telemetry, and keep generated artifacts out of git. Publication requires scans
and no dependency diff.

## Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.
