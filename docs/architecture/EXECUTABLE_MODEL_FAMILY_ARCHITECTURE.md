# Executable Model Family Architecture

M11 keeps one active lazy registry and one generic assembly spine:

`ModelFamilyDefinition -> ModelAssemblyRequest -> ModelAssemblyResult -> ModelRuntimeBundle`

The active family set is exactly `gr00t_n1d6`, `gr00t_n1d7`, and `pi0_5`.
`pi0` and `pi0_fast` remain deferred. Catalog listing imports no family-private module and no
Torch, Transformers, DeepSpeed, JAX, Flax, or Orbax runtime.

Each registration exposes the family factory, checkpoint adapter, typed asset-bundle factory,
canonical `ModelRuntimeBundle` constructor, and runtime-profile identity. These are import-string
references to existing generic contracts; they are not a second construction stack.

## Evidence levels

| Family | Accepted source evidence | Asset/checkpoint evidence | Current gate |
|---|---|---|---|
| GR00T N1.6 | executable source accepted | exact dual bundle and prior strict A100 load accepted | `BLOCKED_C3_DATA` |
| GR00T N1.7 | executable source accepted | local files present, license/access receipts unresolved | `BLOCKED_LICENSE` |
| Pi0.5 | executable source accepted | checkpoint/tokenizer identities, terms, conversion and normalization unresolved | `BLOCKED_LICENSE` |

Source-executable, checkpoint-validated, forward-validated, training-validated, and distributed-
validated are distinct states. A source or asset receipt cannot promote a later runtime axis.
`NO_BACKEND_WINNER` remains mandatory.
