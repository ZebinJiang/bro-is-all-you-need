# AutoVLA Production Training Framework

## Status

The production source implementation is complete for the M5 contract. Runtime,
numerical, checkpoint, DDP, and FSDP2 validation is deferred. This document does
not claim training quality or production readiness.

## Composition

`autovla.cli.train` is the sole production composition root:

```text
ExperimentConfig -> lazy registries -> DataModule -> TrainingBatch
  -> ModelProcessor -> model -> strategy -> optimizer/scheduler
  -> callbacks/checkpoint/logger -> TrainingContext -> TrainingEngine
```

Package imports, family listing, and `autovla-inspect-config` do not construct a
model, open data, initialize distributed state, or start training. Selected
factories check optional extras before importing their runtime modules and emit
one actionable `OptionalDependencyError`.

Checkpoint cadence is owned by `TrainingEngine`; integration does not install
`CheckpointCallback`, avoiding duplicate scheduled saves. Logging and progress
callbacks remain observational. Production checkpoint v2 retains rank-local
Data/RNG state and the repaired next-unread resume ordering.
Clean final checkpoint saving is explicitly enabled by default through the
same engine authority; it does not introduce a second cadence callback.

## Registries And Compatibility

Model, data, strategy, optimizer, scheduler, and callback registries hold
lightweight import strings. `gr00t_n1d6` has a real local-only factory;
`gr00t-n1d6` and `gr00t_n1d6_metadata` are deprecated aliases to that same
registration. `pi0` and `pi0_5` contain specifications without runtime factories.

`autovla.data` owns Data contracts. `autovla.dataloader` delegates canonical
keys and preserves `TrainingBatch` identity. RoboDM-container remains
`prototype_only=True` and `native_compatible=False`. No default is selected:
`NO_BACKEND_WINNER`.

Deterministic policies, dry-run runners, microloops, and manifest-only adapters
live under `autovla.testing`. Historical modules are identity aliases only and
are absent from production registries and defaults. Some deprecated package-root
exports remain solely to preserve compatibility and canonical object identity;
they are not alternate production registrations or composition paths.

## Dependencies

The optional groups are bounded to `training`, `model-gr00t-n1d6`,
`data-lerobot`, and `data-webdataset`; `perf` remains a compatibility alias.
The GR00T group admits the pinned N1.6.1 Transformers 4.51.3 API range, while
the local LeRobot group declares a bounded PyArrow range. There is no Git
dependency, universal model-zoo environment, hidden resolver action, upstream
runtime import, or automatic installation.

## Publication Posture

The M5 change remains a stacked open draft. It must not be marked ready or
merged from static source evidence. Runtime, numerical, checkpoint, DataLoader,
DDP, and FSDP2 validation remains deferred.
