# AutoVLA Production Training Framework

## Status

The M6 candidate extends M5 with production DataLoader, checkpoint
identity/rollback, and DDP/FSDP2 source paths. Runtime classifications must
follow observed AC7/AC8 evidence. This document does not claim training quality
or production readiness.

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
callbacks remain observational. Production checkpoint schema v3 retains rank-local
Data/RNG state and the repaired next-unread resume ordering. Its canonical
compatibility fingerprint excludes only checkpoint output directory,
`resume_from`, and JSONL log location. Full resolved configuration remains
provenance, while model/data/schema/topology/optimization/precision/strategy and
version identities remain fail-closed.
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

The M6 candidate remains a stacked open draft. Bounded CPU/GPU evidence exists;
the frozen DDP/FSDP2 runs failed at rank RNG gathering, the original workers=2
run failed at spawn/cleanup, and the original fresh resume failed semantic
identity. The integrated repair adds primitive RNG state, spawn-safe immutable
data reconstruction, semantic resume identity, focused worker lifecycle, and
fresh-process next-sample tests. DDP/FSDP2 and the three-backend workers=2/full
CLI resume runtime reruns remain deferred. The draft must not be marked ready or
merged, and it carries no long-training, quality, deployment, production, or
backend-winner claim. `NO_BACKEND_WINNER`.
