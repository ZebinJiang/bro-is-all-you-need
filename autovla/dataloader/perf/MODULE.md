# autovla.dataloader.perf Module Guide

## Purpose

`autovla.dataloader.perf` owns bounded, local-first DataLoader performance probes for
AutoVLA Dataset Artifact and adapter paths. It measures metadata inspection,
latency, data-wait proxy metrics, missing GPU telemetry, and future Fast
Training View recommendations without starting real training.

## Public contracts

- `PerfBenchmarkConfig` validates adapter, dataset, output directory, mode, and
  bounded sample limits.
- `PerfMetrics` publishes stable JSON metrics including latency, wait, decode,
  transform, tokenization, collate, throughput, GPU telemetry, and
  `missing_metrics`.
- `run_benchmark()` writes `perf_report.json`, `perf_report.md`,
  `metrics_timeseries.jsonl`, `environment.json`, `dataset_probe_summary.json`,
  and `recommendations.md`.
- `classify_perf_report()` returns `PASS`, `WARN`, `FAIL`, or
  `INSUFFICIENT_TELEMETRY`.

## Directory structure

- `config.py`: benchmark config validation and JSON roundtrip.
- `metrics.py`: metrics schema and percentile helpers.
- `profiler.py`: telemetry parsers that do not invoke external commands.
- `benchmark.py`: bounded benchmark execution and report file writing.
- `report.py`: report classification, Markdown rendering, baseline comparison,
  and Fast Training View schema draft.
- `cli.py` and `__main__.py`: `python -m autovla.dataloader.perf benchmark`.

## Naming conventions

- Modes use kebab-case: `metadata-only`, `bounded-decode`, and `training-view`.
- Report files use stable lower snake case names.
- Metrics names match the task gate vocabulary, for example
  `data_wait_time_ms`, `batch_latency_ms_p95`, and `gpu_util_pct`.

## Extension points

- Add adapter-specific probes by calling the existing dataset adapter registry.
- Add real media decode only in a future task that authorizes a decode backend
  and compute-node validation.
- Add GPU telemetry collection by shelling out only from governed compute jobs;
  keep parser functions pure and fixture-testable.

## Modify vs extend rule

Extend this package for new probe modes or metrics. Modify shared dataloader
contracts only if the new metric changes every adapter contract and has tests.

## Invariants

- Metadata-only mode reads only metadata, info, and tasks files.
- Bounded-decode mode must run on a compute node context.
- Outputs must never be written under the dataset root.
- Missing telemetry must be explicit and must not be fabricated.
- The harness must not invoke real training, model load, checkpoint read, W&B,
  Hugging Face, endpoint, or robot behavior.

## Performance requirements

- Probe defaults stay bounded: four episodes and 512 samples.
- The first implementation is deterministic and emits local JSON/Markdown
  evidence before real finetune is considered.
- Data wait, decode, tokenization, transform, collate, and cache metrics are
  separate fields so bottlenecks are visible.

## Tests/gates

- Focused tests live in `tests/dataloader/test_perf_harness.py`.
- Required gates are focused pytest, Black, Ruff, strict Pyright,
  `make autovla-check`, build verification, scans, and compute-node bounded
  probe evidence when available.

## Agent workflow

1. Verify the task worktree is the perf harness branch.
2. Run metadata-only tests before compute-node probes.
3. Run bounded-decode only from an authorized compute context.
4. Store evidence under `runs/tmp/AUTOVLA-M3-DATALOADER-PERF-HARNESS-001/`.
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
