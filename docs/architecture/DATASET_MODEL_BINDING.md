# Dataset-Model Binding Architecture

## Boundary

The canonical path is:

`LeRobot/WebDataset/RoboDM record -> TrainingSample -> PaddedBatchCollator -> TrainingBatch -> DatasetModelRuntime -> existing family processor`

`TrainingBatch` remains the only physical batch. `DatasetModelRuntime` is an import-light
validation and handoff boundary; it does not own a loader, model, tokenizer, optimizer, or
device runtime. The three backends remain first-class inputs and the runtime records
`NO_BACKEND_WINNER`.

## Compatibility Levels

- `exact`: the physical batch must match the declared dataset and model-side physical
  camera order, dimensions, history, horizon, normalization receipt, and embodiment. No
  projector may run.
- `explicit_projection`: a caller-supplied physical projector is mandatory. Its output is
  revalidated and must stamp the `DatasetModelBinding` fingerprint. The generic runtime
  never guesses a unit, frame, ordering, normalization, temporal, or embodiment transform.
- `contract_fixture_only`: only `ContractBatchFactory` may consume this level. Its output
  remains synthetic and records the model input source revision plus provenance schema.
- `incompatible`: cannot enter the physical runtime or a family processor.

Missing required fields are rejected before record conversion. Missing units, coordinate or
reference frames, component order, dimensions, history, horizon, normalization identity, or
embodiment are incompatibilities. Required state/action values are never zero-filled to
manufacture compatibility. Model-owned padding remains downstream of a valid physical
binding and retains strict masks.

## Cursor And Provenance

`BackendBatchContext` is the frozen, immutable provenance receipt for one physical batch. It
binds the backend key, dataset identity and dataset-config fingerprint, manifest fingerprint,
schema fingerprint, source revision, store revision, and the ordered per-record provenance
fingerprints. Cursor, resume state, and resume mode describe consumption position but are not
allowed to redefine that receipt. Its deterministic provenance fingerprint is derived from
the complete receipt rather than accepted as caller-provided provenance text.

`bind`, `bind_records`, and `prepare_for_family` all converge on the same receipt validator.
Direct physical batches must already carry the receipt's manifest, schema, source/store
revision, dataset/config identity, and ordered record provenance. Record conversion first
checks each record envelope against the batch receipt and then checks that conversion
preserved the same identity. Replacement fields may not launder a mismatched record or batch:
any drift is rejected before family preparation. `BoundTrainingBatch` links the validated
receipt to the binding and compatibility-report fingerprints without copying batch arrays.
Backend-specific cursor values remain opaque key/value items; no backend is ranked or selected
by this layer.

## Family Handoff

`prepare_for_family` calls the existing family-owned `prepare_batch` only after both binding
fingerprints are rechecked. GR00T N1.6, GR00T N1.7, and Pi0.5 continue to own image
processing, tokenization, normalization/projector implementation, padding, device movement,
and inverse action decoding. This module adds no family-private imports and keeps imports
lazy for record conversion.

GR00T N1.7 and Pi0.5 remain `BLOCKED_LICENSE`. GR00T N1.6 asset readiness does not remove
`BLOCKED_C3_DATA`; this source boundary contains no runtime-readiness promotion.

## Current Dataset Surface

`configs/data/m11_black_rubber_bellows_72x98.yaml` exposes the bounded metadata observation
for the current immutable LeRobot v2.1 dataset: 72 state values, 98 action values, three
cameras, and 30 Hz. It records no row or media read. Units, frames, ordering, history,
horizon, normalization, and embodiment remain unknown, so the report is `incompatible` and
does not claim compatibility with any family. `inspect_bounded_dataset_surface` can compare
those observed shapes with a family `ModelInputSchema`, but it always remains a non-claim
until a complete `DatasetModelBinding` and real physical validation exist.

## Reference Reuse Decision

Existing AutoVLA production readers, `TrainingSample`, `PaddedBatchCollator`, `TrainingBatch`,
Wave 2 binding contracts, and Wave 3 family processor entry points are reused directly.
StarVLA, LeRobot, WebDataset, RoboDM-style stores, VLA Foundry, Dexbotic, and FluxVLA were
considered as architecture references; no external code was copied or adapted, no new
dependency was introduced, and no notice change is required. A native sidecar is necessary
because the repository already owns the canonical fingerprints, resume state, and physical
binding semantics.

Residual validation requires complete dataset semantics, accepted family assets/licenses,
and separately authorized A100 runtime evidence. This document makes no robot, quality,
throughput, distributed, or backend-winner claim. M11 remains Draft-only and
`NO_BACKEND_WINNER` remains literal.
