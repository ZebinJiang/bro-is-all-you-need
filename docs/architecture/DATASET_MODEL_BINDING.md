# Dataset-Model Binding Architecture

## M12 Semantic Manifest Boundary

M12 adds one canonical schema, `autovla.semantic_manifest.v1`. The parser accepts an
in-memory mapping and rejects unknown fields at every level. It binds:

- immutable dataset, backend, source revision, and store revision identities;
- source fields to physical feature keys, dimensions, units, coordinate/reference frames,
  representations, component order, source indices, modality, validity range, and masks;
- embodiment identity/version, joint and EEF order, camera mounts, and coordinate
  conventions;
- ordered cameras, language semantics, sample rate, state/action offsets, history, horizon,
  action mode, episode-boundary policy, padding, and mask closure;
- normalization method, statistics fingerprint, axes, feature coverage, owner, scope,
  constant-feature policy, and padding identity;
- an identity or named explicit projector with a version and implementation fingerprint.

The manifest always builds `DatasetSchema.row_validation_status="declared_only"`. A schema
declaration cannot state that rows were observed. `SemanticManifestReceipt` binds the
manifest, `DatasetSchema`, `EmbodimentSchema`, dataset content, projector, normalization,
backend, source, and store fingerprints, but it remains declaration-only.

Unknown units, frames, representation, order, action mode, temporal anchor/boundary policy,
language semantics, normalization policy, or required masks fail closed. There is no
implicit zero padding, index selection, coordinate conversion, temporal resampling, or
normalization fallback.

## Boundary

The M12 receipt-gated path is:

`semantic manifest -> manifest receipt -> backend reader receipt -> canonical records or TrainingBatch -> DatasetModelRuntime -> BoundBatchProvenance -> existing family processor`

`TrainingBatch` remains the only physical batch. Canonical records still reuse
`TrainingSample` and `PaddedBatchCollator`; direct batches and records converge on the same
validation path. `DatasetModelRuntime` owns no loader, backend implementation, dataset file,
model, tokenizer, optimizer, or device runtime. Its semantic/receipt modules import none of
those implementations.

The three backends remain separate first-class identities. Every manifest, row receipt,
reader receipt, context, and bound-batch provenance preserves literal `NO_BACKEND_WINNER`.
This layer neither ranks nor selects a backend.

## Compatibility Levels

- `exact`: the physical batch must match the declared dataset and model-side physical
  camera order, dimensions, history, horizon, normalization receipt, and embodiment. No
  projector or projection receipt may exist. The manifest projector mode must be
  `identity`.
- `explicit_projection`: a caller-supplied physical projector is mandatory. Its output is
  revalidated and must stamp the `DatasetModelBinding` fingerprint. The M12 bridge also
  requires `PhysicalProjectionReceipt`, which binds the named projector ID, version,
  implementation fingerprint, binding fingerprint, semantic-manifest receipt, and backend
  reader receipt.
- `contract_fixture_only`: only `ContractBatchFactory` may consume this level. Its output
  remains synthetic and records the model input source revision plus provenance schema.
  `ReaderEvidenceClass.CONTRACT_FIXTURE_ONLY` requires zero observed rows and cannot
  construct `BackendReaderReceipt`.
- `incompatible`: cannot enter the physical runtime or a family processor.

Missing required fields are rejected before record conversion. Missing units, coordinate or
reference frames, component order, dimensions, history, horizon, normalization identity, or
embodiment are incompatibilities. Required state/action values are never zero-filled to
manufacture compatibility. Model-owned padding remains downstream of a valid physical
binding and retains strict masks.

## Reader And Row Receipts

`RowValidationReceipt` is the only M12 object that records bounded row observation. A
real-data receipt requires at least one ordered record-provenance fingerprint and an exact
count. Its dataset schema, manifest receipt, dataset, backend, source revision, and store
revision must match. A fixture receipt remains `contract_fixture_only`, carries zero rows,
and cannot be promoted by changing a boolean.

`BackendReaderReceipt` binds the reader ID/version, dataset-config fingerprint, semantic
manifest receipt, row-validation receipt, cursor, resume state, and resume mode. It is
backend-neutral and converts to the existing `BackendBatchContext` without importing a
backend implementation. Any source/store/schema/projector/statistics drift fails before
physical binding.

`bind_with_reader_receipt` accepts a canonical `TrainingBatch`.
`bind_records_with_reader_receipt` accepts tiny canonical record mappings and reuses the
existing record converter and collator. Both emit `BoundTrainingBatch.provenance` as
`autovla.bound_batch_provenance.v1`, binding:

- binding and compatibility-report fingerprints;
- semantic-manifest, backend-reader, and row-validation receipt fingerprints;
- backend-context provenance and ordered record provenance;
- exact versus explicit-projection level and optional projection receipt;
- real-data evidence and literal `NO_BACKEND_WINNER`.

The older direct `BackendBatchContext` methods remain an M11 compatibility surface. M12
production integration must use the reader-receipt methods.

## Cursor And Provenance

`BackendBatchContext` binds the backend key, dataset identity and dataset-config
fingerprint, manifest fingerprint, schema fingerprint, source revision, store revision, and
ordered per-record provenance fingerprints. Cursor, resume state, and resume mode describe
consumption position but cannot redefine that receipt. Its provenance fingerprint is
derived rather than accepted as caller-provided text.

`bind`, `bind_records`, the M12 reader-receipt methods, and `prepare_for_family` all converge
on the same context validator. Direct physical batches must already carry the receipt's
manifest, schema, source/store revision, dataset/config identity, and ordered record
provenance. Record conversion checks each record envelope before array materialization and
then verifies that conversion preserved the same identity. Backend-specific cursor values
remain opaque key/value items.

## Family Handoff

`prepare_for_family` calls the existing family-owned `prepare_batch` only after binding,
compatibility, provenance, and model-side physical shape checks. GR00T N1.6, GR00T N1.7, and
Pi0.5 continue to own image processing, tokenization, physical projector implementation,
family normalization, padding, device movement, and inverse action decoding. This shared
module adds no family-private import.

## Current Dataset Surface

`configs/data/m11_black_rubber_bellows_72x98.yaml` exposes a bounded metadata observation:
72 state values, 98 action values, three cameras, and 30 Hz. It records no row or media
read. Units, frames, ordering, history, horizon, normalization, and embodiment remain
unknown, so the result remains `incompatible` for every active family.

M12 does not create a semantic manifest for that dataset, read a dataset file, or mint a
real-data receipt. Its units, frames, physical order, action semantics, temporal alignment,
normalization ownership, masks, and embodiment mapping remain unresolved.

## Reference Reuse Decision

Existing AutoVLA production readers, `TrainingSample`, `PaddedBatchCollator`, `TrainingBatch`,
M11 binding contracts, and family processor entry points are reused directly. StarVLA,
LeRobot, WebDataset, RoboDM-style stores, VLA Foundry, Dexbotic, and FluxVLA were considered
as architecture references; no external code was copied or adapted, no new dependency was
introduced, and no notice change is required. A native sidecar is necessary because this
repository already owns the canonical fingerprints, resume state, and physical binding
semantics.

## Deferred Integration

Production backends do not yet mint `BackendReaderReceipt`, and `DataModule`/training do not
yet require the receipt-gated runtime bridge. Family-owned `ModelInputSchema` and versioned
physical projectors remain separate family work. Data-config manifest selection, real source
indexing, bounded row consumption, readiness receipt integration, and checkpoint/resume
binding identity are deferred to their authorized integration waves.

Residual validation requires authoritative dataset semantics, production reader receipt
minting, complete family schemas/projectors, accepted family assets/licenses, and separately
authorized CUDA runtime evidence. This document makes no robot, model-quality, throughput,
distributed, real-dataset compatibility, or backend-winner claim. `NO_BACKEND_WINNER`
remains literal.
