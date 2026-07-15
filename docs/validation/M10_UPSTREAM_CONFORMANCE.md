# M10 upstream conformance

Conformance is split into source architecture, asset/legal receipt, checkpoint
load, and runtime behavior. Passing one layer does not pass later layers.

## Immutable references and terms

- GR00T N1.6.1: Isaac-GR00T source
  `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`; checkpoint
  `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61`. Source/checkpoint use is governed
  by NVIDIA non-commercial research terms. The typed official asset receipt and
  strict local checkpoint load passed after source-reviewed W1/W2 repairs.
- GR00T N1.7 GA: Apache-2.0 source
  `9c7e746b2cd37a810070a98ef41d290a07e806c2`; checkpoint
  `2fc962b973bccdd5d8ce4f67cc63b264d6886495`. The code license does not resolve
  conflicting checkpoint terms. Required gated Cosmos-Reason2-2B access and
  standalone license receipts are absent. Status: `BLOCKED_ASSET_LICENSE`.
- Pi0.5: Apache-2.0 OpenPI source
  `15a9616a00943ada6c20a0f158e3adb39df2ccac`. The source license does not cover
  the official checkpoint, tokenizer, embedded Gemma weights, or derived
  safetensors. Accepted Gemma/checkpoint/tokenizer receipts, official local
  assets, deterministic conversion evidence, and normalization selection are
  absent. Status: `BLOCKED_ASSET_LICENSE`.

These identities are recorded in the [source synthesis](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/manager/wave1-source-synthesis.md),
[N1.7 source handoff](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-source-gr00t-n1d7-ro/handoff.yaml),
and [Pi0.5 source handoff](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-source-openpi-pi05-ro/handoff.yaml).

## Proven and deferred conformance

N1.6 proves exact local asset receipt and strict official checkpoint mapping at
canonical HEAD: 1,010 tensors and 3,286,608,832 elements loaded with zero
missing, unexpected, or shape-mismatched keys. It does not prove preprocessing,
real-data semantics, forward/loss, gradients, optimizer behavior, prediction,
save/resume, distributed behavior, numerical parity, or model quality.

N1.7 and Pi0.5 have source architecture mappings only. Neither has an accepted
official runtime asset bundle, checkpoint load, or runtime execution. Upstream
DDP or DeepSpeed descriptions are reference facts, not local conformance
results.

There is no model-quality result, N1.7/Pi0.5 load, real batch or training step,
resume proof, DDP/ZeRO/cross-node/scaling/profiler result, or backend winner.
`NO_BACKEND_WINNER`.
