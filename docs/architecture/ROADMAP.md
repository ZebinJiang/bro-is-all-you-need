# AutoVLA Roadmap

## M3.1 - ZJH Dataset And GR00T Pipeline Readiness

Define AutoVLA Dataset Artifact v1, install the `zjh-adapter`, add the
metadata-only `gr00t-n1d6` model-zoo skeleton, parse the local baseline run
read-only, and produce a draft PR for user review. No finetune is executed.

## M3.2 - DataLoader Perf Harness

Add local-first counters for batch latency, decode time, transform time,
tokenization time, collate time, data wait time, queue depth, cache hit rate,
local NVMe staging hit rate, future GPU wait time, and data-to-compute ratio.
This milestone should decide warning/fail thresholds before real finetune.

### Purpose

Make ZJH adapter and Dataset Artifact input-pipeline cost visible before real
GR00T finetune.

### Public contracts

The tranche publishes `autovla.dataloader.perf` config, metrics, CLI, and local
report contracts.

### Directory structure

Runtime code is under `autovla/dataloader/perf/`; tests are under
`tests/dataloader/`; reports are under `runs/tmp/`.

### Extension points

Future roadmap work may add real decode backends and Fast Training View cache
materialization after this gate records bounded measurements.

### Invariants

No real training, full dataset conversion, model/checkpoint load, W&B/HF
network, endpoint, or robot action.

### Performance requirements

Counters must keep data wait, decode, tokenization, transform, collate, and
compute placeholder timings separately reportable.

### Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.

## M3.3 - First GR00T N1.6 Finetune Dry-Run Plan

Plan a governed dry-run using the ZJH artifact, model-zoo skeleton, baseline
metrics, and compute policy. This remains a plan/dry-run step unless the user
explicitly authorizes real training resources and checkpoint/model assets.

## M3.4 - Optimized Training View Prototype

Prototype the AutoVLA fast training view over prepared artifacts. The hot path
must not fit statistics, decode long video per step when a precomputed view
exists, or repeatedly tokenize language when cache exists.

## M3.5 - Native Adapter Expansion

Expand model/data adapters after M3.1-M3.4 evidence. Candidate families include
GR00T-series, PI-series, Qwen-action/OpenVLA-style bridges, LeRobot variants,
RLDS, Dexdata, HDF5, and custom lab formats.

## M4 - Runtime Training And Evaluation Gate

Move from readiness into governed runtime validation. M4 should require explicit
compute authorization, source/checkpoint/license evidence, Slurm job evidence
when cluster behavior is involved, and no hidden external-service side effects.
