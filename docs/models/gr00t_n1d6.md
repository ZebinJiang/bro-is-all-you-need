# GR00T N1.6.1

- Source: `NVIDIA/Isaac-GR00T` at `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`.
- Checkpoint: `nvidia/GR00T-N1.6-3B` at `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61`.
- License: restrictive NVIDIA non-commercial research/evaluation terms; source support and weight
  terms remain separate.
- Evidence: executable source, verified dual asset receipts, and prior strict one-A100 checkpoint
  load with zero missing, unexpected, or shape-mismatched keys.
- Blocker: `BLOCKED_C3_DATA`; asset readiness does not prove exact dataset semantics or runtime
  readiness.
- Runtime profile: `gr00t_n1d6_runtime`; Torch `2.7.1` required, accepted lock absent.
