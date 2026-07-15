# Model Asset Management

Canonical local model assets live under
`/home/cz-jzb/workspace/vla-flywheel/base_model`. This root is ignored,
excluded from Pyright/package discovery, forbidden from staged paths, and never
packaged. Checkpoints, Hugging Face caches, weights, and tokenizer blobs are
also rejected by the path/size-aware staged scan.

Asset acquisition and training are separate operations:

- `autovla-assets` uses the manual `asset-acquisition` optional profile with
  `huggingface_hub==0.30.2` only after explicit authorization.
- production training sets `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
  `AUTOVLA_MODEL_HOME` to the canonical root, and uses local files only.
- core, config, and model import surfaces do not import `huggingface_hub`.

Official Isaac-GR00T source is pinned to
`5dc80c4afd726b34faad1d8f7e007a13b34e4c88` on `n1.6.1-release`. Its NVIDIA
License limits the Work and derivatives to non-commercial research and excludes
the listed military, surveillance, nuclear, and biometric purposes. Although
Section 3.1 defines conditional redistribution requirements, AutoVLA policy is
stricter: no official model weights, checkpoints, tokenizer assets, or fetched
GR00T asset bundle is redistributed or staged.

The Eagle source responsibility map is recorded, but an authorized official
Eagle/tokenizer/checkpoint asset bundle remains unresolved. Eagle therefore
stays local-only and runtime/parity claims remain deferred.
