# GR00T N1.6.1 Integration

## Boundary

The canonical family key is `gr00t_n1d6`. The implementation composes an Eagle
vision-language backbone, embodiment conditioner, masked flow-matching action
head, processor, model, checkpoint adapter, and local factory behind AutoVLA
interfaces. Source implementation is complete; runtime validation is deferred.

The source contract is NVIDIA Isaac-GR00T `n1.6.1-release` at
`5dc80c4afd726b34faad1d8f7e007a13b34e4c88`. Direct derivatives are isolated
under `autovla/models/families/gr00t_n1d6/_nvidia/`; immediate notices and the
NVIDIA License are preserved by the Model writer in `THIRD_PARTY_NOTICES.md`
and `licenses/`. Integration does not alter those files.

## Construction

The lazy registration records the optional extra and import string without
importing torch or Transformers. Construction requires explicit existing local
Eagle assets through `eagle_asset_path`. Checkpoint loading is optional and
occurs only when an explicit local `checkpoint_path` is configured. The factory
builds owned components from the local assets and invokes the checkpoint adapter
only for that configured checkpoint; no Hub lookup, download,
`trust_remote_code`, upstream runtime import, or fallback asset is allowed.

This lower-level family factory contract is distinct from the sole M5
production composition root, `autovla.cli.train`. The production CLI requires
an explicit existing local checkpoint bundle, then uses its checkpoint adapter
to derive the family configuration and required local Eagle asset path from
that bundle before invoking the factory. The CLI does not expose the factory's
asset-only, no-checkpoint construction path and does not select or download a
checkpoint by default.

The processor owns camera ordering, tokenization boundary, normalization,
padding, embodiment IDs, and physical-action decode. The model owns only the
backbone/action-head composition. Training owns optimizer, strategy, callbacks,
checkpoint lifecycle, and telemetry. Deployment is limited to small
`InferencePolicy` and `DeploymentHook` protocols with no server, endpoint, or
robot behavior.

## Truthful Status

No checkpoint or tokenizer was loaded, no model was instantiated, no forward or
backward pass ran, and no training, GPU, Slurm, HF, W&B, endpoint, or robot
action occurred during integration. Model quality, checkpoint parity,
throughput, and deployment readiness remain unproven.
