# Model Family Assembly

`ModelFamilyDefinition` is the immutable source of truth for a production model
family. `ModelFamilySpec` is the same class object and remains only as a source
compatibility name. The production registry exposes exactly `gr00t_n1d6`,
`pi0`, `pi0_fast`, and `pi0_5`; deprecated metadata and roadmap keys warn and
return the same canonical definition object.

Runtime support is closed over five values:

- `executable`
- `architecture_defined_runtime_deferred`
- `asset_required`
- `optional_dependency_required`
- `unsupported`

Registry inspection stores import strings and never resolves component modules.
It therefore does not import Torch, Transformers, JAX, or Flax. Assembly first
checks runtime support, precision, topology, local-only policy, and required
asset identities. Only an executable, completely resolved plan can expose lazy
processor, backbone, action-head, model, and checkpoint factories. Pi family
definitions are architecture-complete but runtime-deferred; resolving execution
fails before dataset access, dependency import, network access, or model
allocation.

`ModelAssemblyPlan` binds the canonical definition and config, asset bundle,
component factory identities, the R3 `TransformPlan`, precision, topology, and
a deterministic provenance fingerprint. The fingerprint describes the plan;
it is not runtime, numerical, checkpoint, or model-quality parity evidence.

GR00T N1.6.1 has four distinct dimensional/runtime contracts:

- the official model envelope is `(horizon, max state, max action) =
  (50, 128, 128)`;
- the verified physical GR1 action input is `[16,29]` before padding into the
  official envelope;
- the historical bounded reduced runtime is `(16, 8, 8)` and is not the
  official model;
- flow inference performs exactly four Euler steps, which is an integration
  count rather than an action horizon.

Generic normalization, joint-relative conversion, padding, and mask composition
are executed by the shared R3 plan. The family processor retains camera,
language, tokenizer, embodiment, model-input, end-effector conversion, and
inverse-decode orchestration. Eagle metadata may directly declare
`num_patches=256` without `image_size`; the GR00T family boundary projects its
verified `image_size=448` and checks `448/14`, downsample ratio `0.5`, and the
declared patch count before any neural module allocation.

`NO_BACKEND_WINNER` remains literal: model-family registration does not choose
a data, training, inference, or distributed backend.
