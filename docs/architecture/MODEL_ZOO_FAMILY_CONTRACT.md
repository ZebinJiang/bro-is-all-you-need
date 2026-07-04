# Model Zoo Family Contract

## Family Registry

`autovla.models.registry.get()` returns `ModelFamilySpec` metadata without lazy-loading upstream runtimes. Unknown keys fail closed with `KeyError`.

Current native family keys:

- `gr00t-n1d6`
- `pi0-roadmap`
- `pi0-fast-roadmap`
- `pi05-roadmap`

The legacy `ModelZooEntry` interface remains available for existing readiness tests and documentation.

## Metadata Contract

Each `ModelFamilySpec` records:

- `family_key`
- display name
- license state
- upstream reference
- modality inputs
- action output
- action-head family
- embodiment metadata
- runtime status
- env profiles
- no-load/no-network flags
- open-source reuse decisions

## Adapter Lifecycle

Layer 1 is metadata-only. Layer 2 may provide a dry-run adapter that validates shapes and emits `ModelInput` without IO. Layer 3 runtime adapters require separate dependency, license, checkpoint, and compute authorization.

## Env Profile Gate

`EnvProfile` records required and forbidden environment variables. Future model-specific profiles such as `model-gr00t-n1d6` must fail closed when required local source/checkpoint variables are absent or forbidden network/service credentials are present.

## Adding A New Family

1. Add metadata-only `ModelFamilySpec`.
2. Add license and open-source reuse decisions.
3. Add dry-run adapter only if it can run without upstream runtime import.
4. Add no-heavy-import tests.
5. Add runtime profile but keep it inactive until a later authorized task.
