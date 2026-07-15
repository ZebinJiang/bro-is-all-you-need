# Model Asset And Checkpoint Lifecycle

The canonical external root is `/home/cz-jzb/workspace/vla-flywheel/base_model`
and both `/base_model/` and `base_model/` are ignored. Source, license and model
weight terms are separate records. No asset, checkpoint, tokenizer, conversion
output or receipt is committed.

`autovla-assets list` preserves the exact registered-asset inventory, while
`families` and `status` expose metadata-only family gates. `inspect`, `verify`
and `path` operate on an exact registered asset specification. `fetch` is the
only network-capable command: it requires an immutable revision, exact
allow-listed files, SHA-256/size verification, a license file, staging
containment and atomic publication. Training and inference never call it.

N1.7 and Pi0.5 intentionally have no fetchable `ModelAssetSpec`: unresolved
legal/access/conversion receipts place both at `BLOCKED_ASSET_LICENSE`, so an
attempted asset-key lookup fails before provider construction. Pi0.5 also uses
`runtime_support=asset_required`; caller-supplied components and evidence cannot
bypass the shared lifecycle gate.

N1.6 accepted the C1 local-asset receipt and C2R7 one-A100 strict load of 1010
tensors with zero missing, unexpected, or shape-mismatched keys. That makes it
assembly-eligible, not runtime-ready. It remains `BLOCKED_C3_DATA`; real batch,
forward/backward/optimizer, prediction/resume, DDP, DeepSpeed, cross-node,
scaling, and quality evidence remain absent.

Production construction is local-only (`HF_HUB_OFFLINE=1`,
`TRANSFORMERS_OFFLINE=1`, `local_files_only=True`), forbids `trust_remote_code`,
and accepts safetensors through family checkpoint adapters. Arbitrary pickle
execution and convenience files such as `scheduler.pt`, `training_args.bin` or
`zero_to_fp32.py` are not accepted asset evidence and are never opened or run.
