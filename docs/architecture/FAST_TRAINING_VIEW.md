# AutoVLA Fast Training View

## Purpose

Fast Training View is the future optimized AutoVLA-native data surface for real
training. It is a schema and policy target in this task, not a materialized
cache or dataset conversion.

## Public contracts

- Shard manifest.
- Sample-to-shard index.
- Episode-to-sample index.
- Predecoded frame/cache policy.
- Pretokenized language policy.
- Precomputed action normalization policy.
- Local NVMe staging manifest.
- Deterministic sampler state.
- DataLoader worker/prefetch policy.
- Performance counters schema.

## Directory structure

This task keeps schema documentation in `docs/architecture/FAST_TRAINING_VIEW.md`
and the reportable draft schema in `autovla.dataloader.perf.report`.

## Naming conventions

Schema keys use lower snake case and describe training-hot-path intent, for
example `sample_to_shard_index` and `pretokenized_language_policy`.

## Extension points

Future tasks can bind this schema to an actual cache writer after compute,
storage, and source-format ownership are approved.

## Modify vs extend rule

Extend schema fields when new counters or cache layers are needed. Do not
modify Dataset Artifact v1 fingerprints unless artifact consumers also receive
migration tests.

## Invariants

- No media payload is committed.
- No cache is materialized in this task.
- No statistics fitting occurs in the training hot path.
- Sampler state must be deterministic and reportable.

## Performance requirements

The view must remove repeated long video decode, repeated tokenization,
unbounded object assembly, and per-step statistics fitting from the real
training path.

## Tests/gates

The current gate verifies that the schema contains the required cache, shard,
index, sampler, and performance counter sections.

## Agent workflow

Agents may update the schema only with Data and Architecture approval. Runtime
materialization requires a separate task and compute/storage evidence.

## Anti-patterns

- training directly from slow interchange loader.
- fitting statistics in training hot path.
- long video decode per training step.
- repeated tokenization per step.
- unbounded Python object assembly per batch.
- hiding missing GPU/data-wait metrics.
- running perf probes on login node.
