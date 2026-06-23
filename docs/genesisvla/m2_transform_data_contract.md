# M2 Transform Data Contract

## Scope

M2 Tranche A introduces a minimal GenesisVLA data transform contract around the
accepted M1 `RawSample` type. It does not change M1 sample, action, model-input,
framework-output, runner, policy, or registry contracts.

## RawSample Flow

```text
legacy payload or tiny fixture
  -> RawSample
  -> TransformProtocol
  -> ComposeTransform
  -> transformed RawSample
  -> BatchSample
  -> ModelInput
```

Transforms are sample-to-sample functions. They must not produce batches,
model inputs, action chunks, datasets, tensors, framework outputs, or runtime
artifacts in Tranche A.

## TransformProtocol

`TransformProtocol` is a plain structural protocol:

```python
class TransformProtocol(Protocol):
    def __call__(self, sample: RawSample) -> RawSample:
        ...
```

It is exported from `genesisvla.core.protocols` for cross-layer typing. Runtime
protocol checks are intentionally not part of the contract.

## ComposeTransform

`ComposeTransform` stores transforms as an immutable tuple and executes them
left-to-right. An empty sequence is an identity transform. Inputs and step
outputs must be `RawSample`; invalid values raise clear `TypeError` messages
with step context when applicable.

## State And Action Normalization

`StateActionNormalize` and `StateActionUnnormalize` use `DatasetStatistics`:

```text
normalized = (value - mean) / std
unnormalized = value * std + mean
```

State statistics apply to 1-D `RawSample.state`. Action statistics apply to the
last dimension of 2-D `RawSample.actions`. Changed arrays are newly allocated;
unchanged fields may be reused.

## Action Modes

- `abs`: require actions and return them unchanged.
- `delta`: preserve the first row, then compute adjacent row differences.
- `relative`: subtract `state[:action_dim]` from every action row and reject
  missing, non-1-D, or too-short state.

The modes do not define robot frames, gripper conventions, control rates, or
pose representations. Those semantics need a later task.

## DatasetStatistics And Cache

`FeatureStatistics` stores 1-D `mean`, 1-D `std`, and optional feature names.
`DatasetStatistics` stores schema version, positive sample count, optional state
statistics, optional action statistics, and small metadata. At least one of
state or action statistics must be present.

Cache helpers read and write JSON only at caller-provided paths. They do not
infer repository-root caches, global user caches, system `/tmp`, dataset roots,
or run directories. Tests use pytest `tmp_path`.

## Out Of Scope

Tranche A does not implement real LeRobot or Parquet adapters, dataset
conversion, streaming datasets, large fixtures, dependency-heavy image backends,
Slurm behavior, model behavior, deployment behavior, or milestone completion.
