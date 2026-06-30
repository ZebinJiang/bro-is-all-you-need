# AutoVLA AI-Native VLA Infrastructure

## Objective

AutoVLA is evolving from a narrow training-script surface into AI-native VLA
infrastructure. The active direction is to keep model, data, training,
evaluation, deployment-adjacent validation, and Agent-readable module ownership
separable while making every boundary auditable through registries, manifests,
and task evidence.

## Current M3.1 Readiness Tranche

This tranche installs the first dataset/model readiness boundary:

- ZJH/LeRobot-v2-compatible metadata adapter.
- AutoVLA Dataset Artifact v1 metadata contract.
- GR00T N1.6/N1.6.1 model-zoo metadata skeleton.
- Read-only local baseline metrics parser.
- Module docs and finetune-readiness report.

It does not authorize finetune, real model loading, tokenizer loading,
checkpoint download, full dataset conversion, W&B/HF network actions, GPU,
Slurm jobs, endpoint calls, or robot actions.

## Infrastructure Pillars

- Model zoo and native adapters: preserve native GR00T/PI/StarVLA functional
  chains conceptually while routing entrypoints through AutoVLA registry and
  adapter contracts.
- Data architecture: treat LeRobot/GR00T/RLDS/Dexdata/HDF5 as import formats,
  not the hot training path.
- Fast training view: future training consumes optimized AutoVLA artifacts with
  precomputed indexes, statistics, tokens, cache metadata, and measurable
  data-to-compute timing.
- Governance evidence: every milestone keeps reportable Owner decisions,
  validation evidence, and publication status.

## M3.2 DataLoader Performance Harness

### Purpose

The M3.2 harness measures whether interchange-format data paths would starve
future GPU training before any real finetune is authorized.

### Public contracts

- `autovla.dataloader.perf.PerfBenchmarkConfig`
- `autovla.dataloader.perf.PerfMetrics`
- `python -m autovla.dataloader.perf benchmark`
- Local JSON/Markdown reports under governed output directories.

### Directory structure

Implementation lives under `autovla/dataloader/perf/`; architecture docs live
under `docs/architecture/`; task evidence lives under `runs/tmp/`.

### Naming conventions

Metrics use explicit latency and throughput names such as
`data_wait_time_ms`, `media_decode_time_ms`, and `data_to_compute_ratio`.

### Extension points

Future compute tasks can add real media-decode probes, GPU telemetry commands,
and Fast Training View cache prototypes without changing the current
metadata-only public surface.

### Modify vs extend rule

Extend perf modes and report fields when new probes are authorized. Do not
turn LeRobot/GR00T import loaders into the AutoVLA training hot path.

### Invariants

No real training, model loading, checkpoint reading, dataset conversion,
W&B/HF network, endpoint, or robot action is performed by the harness.

### Performance requirements

The harness must report missing telemetry, data wait, decode time,
tokenization time, collate time, and data-to-compute ratio separately.

### Tests/gates

Focused tests and project gates must pass before publication. Compute-node
bounded probes are evidence for real ZJH dataset performance, not unit tests.

### Agent workflow

Agents keep metadata-only local checks separate from compute-node probes and
record all generated evidence under `runs/tmp`.

### Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.

## Non-Goals

- No compatibility shim for `genesisvla`.
- No external repository vendoring without license review.
- No hidden dependency expansion.
- No generated dataset/media/checkpoint artifacts in PRs.
- No runtime claim without focused tests and governed source/checkpoint evidence.

## Next Planning Questions

- Which DataLoader Perf Harness counters become M3.2 gate warnings versus hard
  failures?
- Which GR00T source/license/checkpoint evidence is sufficient for a later dry-run
  finetune plan?
- Which optimized training-store format should back the first real AutoVLA fast
  training view?
