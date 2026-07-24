# GR00T N1.6.1 Integration

## Boundary

The canonical family key is `gr00t_n1d6`. The implementation composes an Eagle
vision-language backbone, embodiment conditioner, masked flow-matching action
head, processor, model, checkpoint adapter, and local factory behind AutoVLA
interfaces. `official_n1d6` retains pinned dimensions and authorized-local-asset
requirements. `reduced_runtime` uses the same production classes with a
deterministic AutoVLA-authored fixture and is not official-checkpoint compatible.

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

This lower-level family factory contract is used by the sole production
composition root, `autovla.cli.train`. `official_n1d6` requires an explicit
existing local checkpoint bundle containing or resolving its required Eagle
assets; there is no random-init or reduced fallback. `reduced_runtime` instead
requires an explicit generated local Eagle/tokenizer fixture, forbids
`checkpoint_path`, and uses random initialization through the same production
class graph. Neither path selects or downloads an asset by default.

The processor owns camera ordering, tokenization boundary, normalization,
padding, embodiment IDs, and physical-action decode. Visual-token cardinality
is derived from the validated Eagle `vision_config.patch_size` and
`downsample_ratio`; incompatible image/patch/shuffle geometry fails during
factory validation. The model owns only the backbone/action-head composition.
Training owns optimizer, strategy, callbacks, checkpoint lifecycle, and
telemetry. Deployment is limited to small
`InferencePolicy` and `DeploymentHook` protocols with no server, endpoint, or
robot behavior.

## M10 Truthful Status

The official checkpoint and Eagle support inventory are present at the pinned
revisions. Existing bounded metadata hashes match the verified v2 manifests;
multi-GiB shard hashes were not recomputed on the login node. The first blocker
is `FULL_SHARD_REVERIFICATION_AND_RECEIPT_ISSUANCE_DEFERRED`. N1.6 is eligible
for compute-side full local verification, but official load, CUDA,
forward/backward/update, DDP, ZeRO, cross-node, inference and model quality are
not yet M10 acceptance evidence.
