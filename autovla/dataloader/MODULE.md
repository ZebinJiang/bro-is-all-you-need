# autovla.dataloader Module Guide

## Purpose

`autovla.dataloader` owns lightweight data contracts, transform metadata, dataset statistics records, and metadata-only dataset readiness artifacts. It must keep external dataset formats out of the hot training path until a task explicitly authorizes conversion or runtime loading.

## Public contracts

- `CollatedBatch`, `TransformSpec`, `ComposeConfig`, and `TransformContext` define numpy-only batch and transform contracts.
- `DatasetArtifactV1` defines the Layer 2 AutoVLA dataset artifact preview schema.
- `StatisticsScope` is exactly `action_only`, `vision_language_only`, or `mixed`.
- `write_dataset_artifact_preview` writes small JSON previews under caller output directories only.

## Directory structure

- `contracts.py`: shared dataloader JSON, transform, and batch contracts.
- `dataset_artifact.py`: metadata-only Dataset Artifact v1 schema and fingerprint helpers.
- `adapters/`: external-format metadata adapters such as `zjh-adapter`.
- `perf/`: bounded DataLoader performance harness, metrics, CLI, and report contracts.
- `perf/` also owns the persistent shared-PFS Training Store builder used to
  promote ZJH-derived action/state shards into
  `datasets/derived/autovla_training_store/**` without touching
  `datasets/readonly/**`.
- `statistics/`: fitted statistics schema/cache code.
- `transforms/`: transform implementations and registries.
- `datasets/`: dataset composition surfaces that are not specific external import formats.
- `ingestion/`: future conversion and ingestion plans; no runtime conversion in this tranche.

## Naming conventions

- Adapter names use lowercase kebab-case, for example `zjh-adapter`.
- Artifact schema versions use full dotted names such as `autovla.dataset_artifact.v1`.
- Fingerprints are named by purpose: `dataset_fingerprint`, `transform_fingerprint`, and `statistics_fingerprint`.
- Statistics scopes must use the exact public strings above.

## Extension points

- Add a new external metadata adapter under `adapters/` when an external format must be inspected without conversion.
- Add new Artifact v1 fields only when they are JSON-safe, deterministic, and covered by focused tests.
- Add real conversion under `ingestion/` only after a future task authorizes dataset reads/writes.

## Modify vs extend rule

Extend with a new adapter or artifact field when supporting a new external source. Modify shared contracts only when the existing public contract is wrong or incomplete for all adapters, and add migration tests for existing callers.

## Invariants

- `datasets/readonly/**` is immutable.
- Metadata preview must not decode media, read parquet rows, fit statistics, or copy dataset payloads.
- VLM/dialogue-only data must not contribute to action normalization statistics.
- Mixed datasets must explicitly declare the action-statistics subset.
- Action-only statistics require declared action data.
- Canonical fingerprints must not include mtimes, inodes, user ids, temporary output paths, or host-specific absolute paths.

## Performance requirements

- Metadata adapters may read only small metadata files during preview.
- Preview writers emit bounded JSON and must avoid full dataset scans.
- Hot training views should consume normalized artifacts, not external import formats.
- Persistent training stores are generated artifacts: source datasets remain
  immutable, store shards/indexes/manifests remain ignored by git, and only a
  `FULL_STORE_READY` store may support the next fine-tune dry-run contract.
- Perf probes must keep data wait, decode, tokenization, transform, collate, and
  compute placeholder timings separately reportable.

## Tests and gates

- Focused tests live under `tests/dataloader/`.
- Required local gates for this tranche are py_compile, focused pytest, ruff, black check, and `git diff --check`.
- Heavy validation, Slurm, GPU, model load, media decode, dataset conversion, and stats fitting are out of scope unless separately authorized.

## Agent workflow

1. Verify worktree, branch, HEAD, status, and tracked `genesisvla/**` count.
2. Read the task plan and current dataloader contracts.
3. Keep writes inside the assigned Data-owned paths.
4. Use tiny `tmp_path` metadata fixtures for tests.
5. Record evidence under `runs/tmp/<task-id>/data/`.

## Anti-patterns

- Writing previews inside `datasets/readonly` or the dataset root.
- Treating LeRobot/ZJH import files as the training hot path.
- Adding dependency, network, HF/W&B, GPU, Slurm, model, tokenizer, or checkpoint behavior to dataloader readiness.
- Adding compatibility shims or `genesisvla` paths.
- Running DataLoader performance probes on the login node.
- Hiding missing GPU/data-wait metrics instead of recording them in report output.
