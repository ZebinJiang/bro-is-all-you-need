# Training Spine Design

## Objective

The AutoVLA training spine provides small, typed contracts between data backends, model-family adapters, trainable policies, loss adapters, checkpoint manifests, runtime gates, and efficiency telemetry. It is not a production trainer and does not activate real model loading in this task.

## Adopted Architecture

The spine uses `TrainingBatch` as the model-family-neutral handoff from Data. Family-specific code must live behind `BatchAdapter` implementations. The runner side consumes `ModelInput`, `TrainablePolicy`, `LossAdapter`, `CheckpointAdapter`, `RuntimePlan`, `EnvProfile`, and `EfficiencyTelemetry`.

Data flow:

1. Data backend emits an already-collated `TrainingBatch`.
2. A model-family `BatchAdapter` converts it to `ModelInput`.
3. A test-double or future `TrainablePolicy` computes `FrameworkOutput`.
4. A loss adapter computes strict masked action loss.
5. A checkpoint adapter writes JSON manifest metadata only.
6. `EfficiencyTelemetry` records data wait, adapter, forward, loss, and checkpoint-manifest timing separately.

## Stable Contracts

- `TrainingBatch`: batch-major image/language/state/action tensors plus fingerprints.
- `BatchAdapter`: no-IO conversion from `TrainingBatch` to `ModelInput`.
- `RuntimePlan`: fail-closed runtime feature declaration.
- `EnvProfile`: required/forbidden environment gates.
- `EfficiencyTelemetry`: deterministic JSON telemetry for throughput and latency.
- `TrainingCheckpointManifest`: JSON-only resume compatibility manifest.

## Runtime Boundaries

Registry lookup, metadata inspection, and adapter construction must not import torch, transformers, GR00T, OpenPI, JAX, Flax, checkpoint readers, tokenizers, dataset clients, or network clients. CUDA, Slurm, FSDP, DeepSpeed, compilation, W&B, Hugging Face, endpoints, and robots remain inactive.

## Extension Path

Future families should add a metadata spec, optional dry-run adapter, env profile, and focused tests before any runtime adapter. Runtime activation requires a separate task with dependency, license, checkpoint, and compute evidence.
