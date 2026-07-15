# GR00T N1.6.1 source map

- Source: `https://github.com/NVIDIA/Isaac-GR00T`, tag `n1.6.1-release`, commit
  `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`.
- Checkpoint metadata: `nvidia/GR00T-N1.6-3B`, repository commit
  `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61`.
- License: NVIDIA License, non-commercial research restrictions; checkpoint and
  Eagle support receipts remain separate. See repository notices and isolated
  `_nvidia/` file headers.
- Reuse: `config.py`, `processor.py`, `checkpoint.py`, `factory.py`, `model.py`,
  `backbone.py`, and `action_head.py` are AutoVLA contract reimplementations.
  `_nvidia/dit.py`, `_nvidia/embodiment.py`, and `_nvidia/eagle/**` are isolated,
  attributed NVIDIA-derived adaptations and are intentionally not shared core.
- Safety boundary: local verified assets and safetensors only; no network,
  `trust_remote_code`, arbitrary pickle, implicit download, or asset copying.
- Evidence boundary: architecture/source mapping is complete. Official checkpoint
  load, CUDA execution, DDP, DeepSpeed ZeRO, cross-node execution, inference, and
  resume compatibility remain unverified. `NO_BACKEND_WINNER`.
