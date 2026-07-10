# PR31 Core Contract And Capability Repair

## Scope

This repair keeps PR31 local, deterministic, metadata-only, and dependency-free. It changes no
backend builder or reader algorithm, model asset, dependency surface, runtime environment, or
PR30 benchmark result.

## Ownership And Import Direction

`autovla.core.reporting` owns the pure report table, stable JSON, CSV, and Markdown objects.
`autovla.training.performance_tables` and `autovla.training.metrics.stable_json_dumps` are identity
compatibility exports. Data performance code imports the neutral Core owner directly.

The Data, Data performance, format-pipeline, Training, and model package roots use explicit lazy
export maps. A cold `autovla.dataloader.backends` import does not initialize Training, performance
implementations, format-pipeline implementations, physical stores, or optional WebDataset code.

## Canonical Training Contracts

The executable contracts live only in `autovla.training.contracts`:

- `BatchAdapter.to_model_input(TrainingBatch) -> ModelInput`
- `ActionPolicy.setup() -> None`
- `ActionPolicy.predict_actions(ModelInput) -> NumericArray`
- `LossAdapter.compute(prediction, target, action_mask) -> MaskedActionLoss`
- `CheckpointAdapter.write_manifest(Path, TrainingCheckpointManifest) -> Path`
- `CheckpointAdapter.validate_resume(TrainingCheckpointManifest, CheckpointCompatibilitySpec) -> int`

`TrainablePolicy` is the same object as `ActionPolicy`; there is no `forward_loss` contract.
`DeterministicCpuPolicy` and `NumpyMaskedLossAdapter` remain identity aliases to the canonical test
implementations. Registry-local `PolicyFactoryProduct`, `LossFactoryProduct`, and
`CheckpointFactoryProduct` were removed. Factories are typed to and checked against the canonical
runtime-checkable protocols before use.

`autovla.training.test_components` contains the single M4 implementation set. The runner only
coordinates capability authorization, factories, source reads, adaptation, prediction, external
loss, telemetry, and metadata-only checkpoint write/read/resume. The separate M3 checkpoint schema
and local-runner compatibility paths remain intact.

## Structured Model Capabilities

`ModelFamilySpec.capabilities` is the sole capability source. Frozen dataclasses and closed enums
describe processor, backbone, action head, image/language/state inputs, action representation and
shape, mask policy, normalization/statistics, execution support, and side-effect permissions.
Legacy summary properties are derived from this record.

The executable `test_double` profile requires exactly `camera.rgb_0`, `camera.rgb_1`, and
`camera.rgb_2`; non-empty language; state; configured numeric `[B,H,D]` actions; a strict bool
same-shape mask; identity normalization; and no external statistics or runtime side-effect
permission. Its adapter copies `logical_batch_fingerprint` only when present. Backend parity is the
only path that requires that field and raises `ValueError("backend parity requires
logical_batch_fingerprint")` when absent.

`gr00t_n1d6_metadata`, `pi0_metadata`, and `pi05_metadata` have distinct unverified component
identities and expose exactly `ExecutionMode.METADATA_ONLY` in the canonical capability record.
Roadmap and dry-run-adapter wording is descriptive legacy metadata only and never an execution
capability. The profiles grant no runtime import, network, asset,
checkpoint, tokenizer, or real-training permission and fail before output inspection, component
factory invocation, source preparation, or writes.

## Backend And Compatibility Boundary

The canonical backend keys remain `webdataset_tar` and `robodm_container_v1`; `robodm_style`
remains an explicit alias. The RoboDM-style path remains prototype-only and non-native-compatible.
Both two-step presets use the same orchestration and parity fields. The evidence conclusion remains
`PASS_EQUIVALENT_CANONICAL_BATCHES` with literal `NO_BACKEND_WINNER`.

Only after PR31 approval may a next task run a controlled real-run WebDataset versus RoboDM-style
efficiency comparison. This repair selects no backend and authorizes no such runtime; all current
evidence remains synthetic-only, and PR31 remains draft and must not merge.

## Reference Reuse Decision

- References considered: FluxVLA, Dexbotic, Isaac GR00T, OpenPI, LeRobot, StarVLA, and VLA Foundry
  at the task intake pins.
- Reuse: design inspiration and metadata boundaries only; no source was copied, adapted, or
  vendored.
- License status: inspected MIT or Apache-2.0 code metadata is informational for this repair;
  model and weight terms remain separate. Metadata-only execution support, not ordinary open-code
  attribution, is the runtime blocker.
- Copyright and notices: no new header or notice is required because no upstream code was copied.
- Dependency impact: none.
- Native implementation reason: the repair is a small typed, numpy-only contract boundary; the
  upstream runtime, distributed, model, and checkpoint stacks are broader and dependency-heavy.
- Tests: focused import identity, protocol conformance, capability validation, fail-closed ordering,
  exact test-double input, checkpoint roundtrip, dual backend, preset, and parity checks.
- Residual risk: metadata does not establish real GR00T or Pi runtime compatibility.

## Rollback

Revert this bounded Core reporting, lazy export, Training contract/component, model capability,
runner, focused test, and architecture-document set together. No dataset, model asset, generated
artifact, dependency, environment, checkpoint payload migration, or backend algorithm requires
rollback.
