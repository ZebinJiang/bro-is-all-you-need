# AutoVLA DataLoader Performance Harness

## Purpose

The DataLoader Performance Harness makes dataset/input-pipeline cost
measurable before real finetune. It turns suspected GPU wait into bounded,
local evidence with explicit missing telemetry.

## Public contracts

- CLI: `python -m autovla.dataloader.perf benchmark`.
- Config: `PerfBenchmarkConfig`.
- Metrics: `PerfMetrics`.
- Reports: `perf_report.json`, `perf_report.md`, `metrics_timeseries.jsonl`,
  `environment.json`, `dataset_probe_summary.json`, and `recommendations.md`.

## Directory structure

- Runtime code lives under `autovla/dataloader/perf/`.
- Focused tests live under `tests/dataloader/test_perf_harness.py`.
- Task evidence belongs under `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/`.

## Naming conventions

Use stable metric names from the M3.2 gate: `samples_per_second`,
`episodes_per_second`, `batch_latency_ms_p50`, `batch_latency_ms_p95`,
`data_wait_time_ms`, `compute_placeholder_time_ms`, and `data_to_compute_ratio`.

## Extension points

Future tasks may add real decode backends, GPU telemetry commands, or optimized
training-store probes. Those additions must keep parsers fixture-testable and
must not add runtime dependency drift silently.

## Modify vs extend rule

Extend the perf package for new probes. Modify adapter contracts only when a
new invariant applies to every dataset adapter.

## Invariants

- No full dataset conversion.
- No model/checkpoint/tokenizer loading.
- No W&B/HF network.
- No hidden generated dataset artifact in git.
- Bounded-decode runs only on compute nodes.

## Performance requirements

The harness must separate inspect, index, decode, transform, tokenization,
collate, data wait, and compute placeholder time. Missing GPU telemetry is a
classification input, not a reason to fabricate utilization.

## Tests/gates

Focused tests verify config, metrics, report classification, CLI behavior,
output safety, no source dataset writes, baseline comparison, GPU telemetry
missing paths, and Fast Training View schema.

## Agent workflow

Agents run metadata-only validation locally, then compute-node bounded probes
only after the task authorizes compute resources. Publication requires scans
and no dependency diff.

## Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.
