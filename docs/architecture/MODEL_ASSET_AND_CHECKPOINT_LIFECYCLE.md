# Model Asset And Checkpoint Lifecycle

The canonical external root is `/home/cz-jzb/workspace/vla-flywheel/base_model`
and both `/base_model/` and `base_model/` are ignored. Source, license and model
weight terms are separate records. No asset, checkpoint, tokenizer, conversion
output or receipt is committed.

`autovla-assets list` and `status` are metadata-only. `inspect`, `verify` and
`path` operate on an exact registered asset specification. `fetch` is the only
network-capable command: it requires an immutable revision, exact allow-listed
files, SHA-256/size verification, a license file, staging containment and atomic
publication. Training and inference never call it.

N1.7 and Pi0.5 intentionally have no fetchable `ModelAssetSpec`: their Wave 4
legal/access/conversion gates are unresolved, so an attempted asset-key lookup
fails before provider construction. N1.6 has exact registered files but its
status remains `inventory_ready_compute_verification_required`; this does not
authorize checkpoint load.

Production construction is local-only (`HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, `local_files_only=True`), forbids `trust_remote_code`,
and accepts safetensors through family checkpoint adapters. Arbitrary pickle
execution and convenience files such as `scheduler.pt`, `training_args.bin` or
`zero_to_fp32.py` are not accepted asset evidence and are never opened or run.
