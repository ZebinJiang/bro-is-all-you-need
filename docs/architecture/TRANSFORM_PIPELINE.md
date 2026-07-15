# Transform Pipeline

## Canonical plan

`autovla.data.transforms.TransformPlan` is the ordered transform source of truth.
Dataset backends emit physical-unit canonical features; data-side stages then apply
temporal alignment, relative actions, normalization, padding, mask composition, and
feature rename. Model-family processors may consume the result or run explicitly
declared family-processor stages. Legacy `autovla.dataloader.transforms` names are
bounded RawSample adapters and do not own another semantics implementation.

Forward execution follows declaration order. Inverse execution follows exact reverse
order. A typical reversible path is:

```text
physical feature
  -> temporal alignment
  -> relative action
  -> normalization
  -> padding and independent masks
  -> optional feature rename

inverse:
  rename -> unpad -> denormalize -> absolute action -> temporal restore
```

Temporal selection is reversible only when its indices form a complete permutation;
otherwise its descriptor declares `reversible=false` and inverse execution fails.
Previous-action delta keeps the first action absolute. State-relative action uses an
explicit action-dimension to state-index mapping and one fixed state reference for the
whole chunk.

## Shared stage descriptor

Every serialized stage contains the same compact `StageDescriptor`:

- required input features, layouts, and layout rule;
- produced output features, layouts, and layout rule;
- reversibility;
- state dependencies;
- statistics dependencies by content fingerprint;
- mask production/composition behavior;
- execution side: `data` or `family_processor`.

The descriptor is part of plan JSON and therefore part of the deterministic plan
fingerprint. Stage type, implementation version, parameters, order, complete
statistics content, and alignment policy are also fingerprinted. Callable-only names
cannot represent the canonical production plan.

## Stage behavior

`TemporalAlignmentStage` uses explicit indices and emits a `[T]` temporal mask.
`RelativeActionStage` supports fixed-state relative action and reversible
previous-action delta. `NormalizeStage` delegates to the one statistics implementation.
`PaddingStage` records source/target shapes and emits a padding mask matching the padded
layout. `MaskCompositionStage` requires identical source mask layout, shape, and truth
semantics; it never mutates or relabels source masks. `FeatureRenameStage` rejects
overwrites and reverses by restoring the original key.

All NumPy stages copy only the feature they modify and preserve other top-level values.
For an array with `N` elements, normalization, relative action, temporal copy, and
padding are `O(N)` time and `O(N)` output space. Plan metadata and fingerprints are
`O(S + P)`, where `S` is stage count and `P` is serialized parameter/statistics size.
There is no implicit device transfer, tokenizer step, remote decoding, or distributed
collective in this layer. GPU utilization and rank partitioning remain downstream
training/data-loader concerns.

This architecture does not rank storage or execution backends: `NO_BACKEND_WINNER`.
