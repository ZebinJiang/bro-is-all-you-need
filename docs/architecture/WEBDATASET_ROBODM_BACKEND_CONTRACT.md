# WebDataset And RoboDM-Style Backend Contract

## Keys And Capabilities

- `webdataset_tar`: lazy WebDataset 1.0.2 package route, sequential streaming,
  deterministic no-shuffle iteration, materialized cameras.
- `robodm_container_v1`: AutoVLA-owned stdlib tar/index route, persistent index,
  bounded persistent handles, grouped reads, `native_compatible=false`.
- `robodm_style`: explicit alias for `robodm_container_v1`, never a manifest key.

Aliases resolve before opening storage. Unknown keys and alias collisions fail
closed. No backend is selected by path, suffix, timing, or fastest-result logic.

## Shared Semantic Contract

Both stores encode one seed-11 logical fixture with two episodes, eight samples,
three RGB cameras per sample, deterministic language/state/action values, and a
strict bool action mask. The shared reader bridge emits canonical
`TrainingBatch` arrays with action and mask shape `[B,H,D]`.

Physical shard/container paths, package keys, handles, artifact checksums, and
backend names are excluded from logical sample and batch fingerprints. Backend
parity compares ordered IDs, images, language, state, action, mask, semantic
fingerprints, deterministic loss, and checkpoint compatibility.

## Interpretation

Parity is an integration result, not a performance or readiness result.
Decision: `NO_BACKEND_WINNER`. No real training, gradients, model/checkpoint/
tokenizer load, network/HF/W&B, GPU/Slurm, endpoint, robot, or production claim
is authorized by this contract.
