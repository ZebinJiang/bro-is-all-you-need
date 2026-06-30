# AutoVLA Roadmap

## M3.1 - ZJH Dataset And GR00T Pipeline Readiness

Define AutoVLA Dataset Artifact v1, install the `zjh-adapter`, add the
metadata-only `gr00t-n1d6` model-zoo skeleton, parse the local baseline run
read-only, and produce a draft PR for user review. No finetune is executed.

## M3.2 - DataLoader Perf Harness

Add counters for batch latency, decode time, transform time, tokenization time,
collate time, data wait time, queue depth, PFS Training Store hit rate, future
GPU wait time, and data-to-compute ratio.
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

PR #14 showed that the raw bounded-decode path is media-decode dominated, then
added a bounded PFS-backed Training Store v0 builder/read benchmark. Current
roadmap work should treat shared-PFS prepacked shards as the optimization target;
do not assume compute-node local disk or local NVMe staging unless a later
compute inventory proves it exists.

Future roadmap work may add real decode backends and persistent Fast Training
View materialization after this gate records bounded measurements.

The immediate follow-on persistent builder writes ZJH source-derived shards,
sample/episode indexes, checksums, and `statistics_plan.json` under
`datasets/derived/autovla_training_store/<dataset_id>/<dataset_fingerprint>/`.
Only `FULL_STORE_READY` may unblock the next GR00T-N1.6 fine-tune dry-run
contract. `PARTIAL_STORE_READY_FOR_FORMAT_REVIEW` can be merged only as backend
format evidence and must not claim training readiness.

### Invariants

No real training, full dataset conversion, model/checkpoint load, W&B/HF
network, endpoint, or robot action.

### Performance requirements

Counters must keep data wait, decode, tokenization, transform, collate, and
compute placeholder timings separately reportable. Raw/store comparisons must
preserve raw batch p50/p95 and explicitly record any effective comparator such
as `media_decode_bottleneck`.

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
must not fit statistics, decode long video per step when a PFS Training Store
exists, or repeatedly tokenize language when a precomputed store exists. Revisit
WebDataset, Arrow, Parquet, or Megatron-style indexed backends only after the
simple PFS v0 contract has enough read-path evidence to justify migration.

## M3.5 - Native Adapter Expansion

Expand model/data adapters after M3.1-M3.4 evidence. Candidate families include
GR00T-series, PI-series, Qwen-action/OpenVLA-style bridges, LeRobot variants,
RLDS, Dexdata, HDF5, and custom lab formats.

## M4 - Runtime Training And Evaluation Gate

Move from readiness into governed runtime validation. M4 should require explicit
compute authorization, source/checkpoint/license evidence, Slurm job evidence
when cluster behavior is involved, and no hidden external-service side effects.
