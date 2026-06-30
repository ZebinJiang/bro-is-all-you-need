# AutoVLA Fast Training View

## Purpose

Fast Training View is the optimized AutoVLA-native data surface for future real
training. The current M3 correction materializes only a bounded PFS-backed
Training Store v0 under ignored evidence so the project can compare raw decode
against deterministic prepacked shard reads before any real finetune.

This is not a compute-node local disk or local NVMe staging design. The current
cluster workflow uses shared PFS for both source data and optimized Training
Store evidence.

## Public contracts

- Shard manifest.
- Sample-to-shard index.
- Episode-to-sample index.
- Predecoded frame/cache policy.
- Pretokenized language policy.
- Precomputed action normalization policy.
- PFS Training Store manifest.
- PFS storage backend and local-stage policy.
- Deterministic sampler state.
- DataLoader worker/prefetch policy.
- Performance counters schema.

## Directory structure

This task keeps schema documentation in `docs/architecture/FAST_TRAINING_VIEW.md`,
the reportable schema in `autovla.dataloader.perf.report`, and the bounded PFS
Training Store v0 implementation in `autovla.dataloader.perf.training_store`.

## Naming conventions

Schema keys use lower snake case and describe training-hot-path intent, for
example `sample_to_shard_index` and `pretokenized_language_policy`.

## Extension points

Future tasks can evolve the PFS Training Store into a persistent derived
dataset store after compute, storage, source-format ownership, and retention
policy are approved. WebDataset, Arrow, Parquet, and Megatron-style indexed
backends should be compared against the v0 manifest/index/shard contract only
when there is enough evidence that the simple PFS shard layout is the next
bottleneck.

The current persistent ZJH builder writes source-derived store artifacts under
`datasets/derived/autovla_training_store/<dataset_id>/<dataset_fingerprint>/`.
That path is shared-PFS backed, ignored by git, and separate from the immutable
`datasets/readonly` source. Agents should extend the store by adding new
manifest fields, shard backends, or statistics plans only when the new field is
deterministic, checksum-covered, and validated by focused tests.

## Modify vs extend rule

Extend schema fields when new counters or cache layers are needed. Do not
modify Dataset Artifact v1 fingerprints unless artifact consumers also receive
migration tests.

## Invariants

- No media payload is committed.
- Generated Training Store artifacts stay under ignored `runs/tmp` evidence.
- Persistent Training Store artifacts stay under ignored `datasets/derived`
  and must not be committed.
- No source dataset path is modified.
- No statistics fitting occurs in the training hot path.
- Sampler state must be deterministic and reportable.

## Performance requirements

The view must remove repeated long video decode, repeated tokenization,
unbounded object assembly, and per-step statistics fitting from the real
training path. For M3 PFS evidence, the immediate proof point is replacing the
media-decode-dominated raw bounded-decode path with prepacked PFS shard reads,
sample index lookup, checksum verification, and explicit missing telemetry.

Fine-tune dry-run planning may proceed only from a `FULL_STORE_READY` persistent
store. Partial stores remain useful for format review and backend migration
decisions, but they are not training-ready.

## Tests/gates

The current gate verifies that the schema contains the required cache, shard,
index, sampler, and performance counter sections.

## Agent workflow

Agents may update the schema only with Data and Architecture approval. Runtime
materialization beyond bounded task evidence requires a separate task and
compute/storage evidence. Any extension must keep the no-local-NVMe assumption
visible unless a future compute inventory proves local staging exists.

## Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.
