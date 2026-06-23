# M1-lite Core Contract

## Scope

M1 is a minimal, numpy-only, torch-free contract layer for GenesisVLA. It defines
stable sample, action, framework-output, protocol, registry, and typed-config
surfaces that later milestones can build on, but it does not implement training,
model execution, tensor backends, GPU behavior, datasets, Slurm jobs, or robot
runtime behavior.

## Numpy-only Surface

M1 public numeric aliases use numpy arrays through `NumericArray`, `ImageLike`,
and `ActionMask`. `RawSample`, `BatchSample`, `ModelInput`, `FrameworkOutput`,
`ActionChunk`, and `ActionSpace` are intentionally small dataclass contracts.
They validate shape and field presence only where M1 has accepted evidence.

`FrameworkOutput.loss` is currently `float | NumericArray`. This is deliberate:
M1 records a minimal scalar/array result contract without importing torch or
declaring a training tensor type.

## Torch-free Boundary

M1 must not import torch, require torch, or expose torch/Tensor as a public
training contract. Torch-backed losses, model tensors, gradient behavior,
distributed execution, and policy-framework integration belong to later runner
and model milestones.

The expected M3/M4 milestone split is:

- M3: runner lifecycle, checkpoint manager, and training/evaluation orchestration.
- M4: model framework, action head, masked loss, tensor processor, and
  policy-facing model contract.

Until those milestones add reviewed contracts, M1 examples and tests should
remain CPU-local, numpy-based, and free of torch runtime assumptions.
