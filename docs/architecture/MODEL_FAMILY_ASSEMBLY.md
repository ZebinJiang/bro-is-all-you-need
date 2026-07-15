# Model Family Assembly

`ModelFamilyDefinition` is the immutable source of truth for a production model
family. `ModelFamilySpec` is the same class object and remains only as a source
compatibility name. The M10 active registry exposes exactly `gr00t_n1d6`,
`gr00t_n1d7`, and `pi0_5`. `pi0` and `pi0_fast` are hidden from the default
listing and appear only with explicit deferred inspection as
`DEFERRED_BY_USER_PRIORITY`; compatibility aliases warn and return the same
canonical definition object.

Runtime support is closed over five values:

- `executable`
- `architecture_defined_runtime_deferred`
- `asset_required`
- `optional_dependency_required`
- `unsupported`

Registry listing stores definition and component import strings and never
resolves family or component modules.
It therefore does not import Torch, Transformers, JAX, or Flax. Assembly first
checks runtime support, precision, topology, local-only policy, and required
asset identities. Only an executable, completely resolved plan can expose lazy
processor, backbone, action-head, model, and checkpoint factories. Pi family
definitions are architecture-complete but runtime-deferred; resolving execution
fails before dataset access, dependency import, network access, or model
allocation. A family being active means its source path is in the M10 target;
it does not mean its official assets or any CUDA/distributed cell passed.

The generic path is `ModelFamilyCatalogEntry -> ModelFamilyDefinition ->
ModelAssemblyPlan -> ModelFactory`. Dependencies, assets, transforms, precision,
topology and component factory paths are owned by each definition. Generic code
contains no family-prefix dispatch and accepts only the shared verified asset
bundle protocol.

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
