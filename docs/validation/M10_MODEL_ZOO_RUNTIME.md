# M10 model-zoo runtime status

The maximum eventual publication conclusion supported by current evidence is
`PARTIAL_PRODUCTION_MODEL_ZOO_GPU_RUNTIME_DRAFT_PUBLISHED`. This describes the
ceiling for a future Draft publication; no Draft PR is claimed to exist yet.

## GR00T N1.6.1

Source revision `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` and official
checkpoint revision `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61` are pinned.
The official typed asset receipt passed, and source-reviewed W1/W2 repairs
closed checkpoint namespace and FFN-shape defects. Exact-HEAD job `3408` passed
the strict one-A100 checkpoint load as `COMPLETED 0:0` with 1,010 tensors,
3,286,608,832 elements,
zero missing/unexpected/shape mismatches, observed `torch.float32` state on
`cuda:0`, load time `24.47898` seconds, 18,556,289,024 peak allocated bytes,
and 18,834,522,112 peak reserved bytes. Evidence is in the
[C2R7 handoff](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-cuda-n1d6-c2r7/handoff.yaml).

Real-batch mechanics remain `BLOCKED_C3_DATA`. The inspected real candidate is
`demo_bot` with dimensions `72/98`, without required production reader
metadata/index, without an evidenced `gr1` mapping, and incompatible with the
GR1 processor dimensions `58/29`. No C3 job was submitted; forward/backward,
optimizer, prediction, save, and resume did not run. See the
[C3 decision](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-cuda-n1d6-c3-ro/handoff.yaml).

## GR00T N1.7

The source architecture exists at Isaac-GR00T GA revision
`9c7e746b2cd37a810070a98ef41d290a07e806c2`; checkpoint metadata is pinned at
`2fc962b973bccdd5d8ce4f67cc63b264d6886495`. Runtime is
`BLOCKED_ASSET_LICENSE`. Apache-2.0 covers the source code, not the checkpoint
weights. The checkpoint's packaged NVIDIA License limits use to non-commercial
research/evaluation, while accompanying publication text claims NVIDIA Open
Model License terms. The required Cosmos-Reason2-2B asset is gated; although a
convenience tree was inventoried at
`9ce19a195e423419c349abfc86fd07178b230561`, no gated-access acceptance receipt
or standalone license receipt is bound to it. No canonical checkpoint/Cosmos
bundle exists and no N1.7 runtime was executed. See the
[Wave 4 asset synthesis](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/manager/wave4-asset-synthesis.md).

## Pi0.5

The source architecture exists at OpenPI revision
`15a9616a00943ada6c20a0f158e3adb39df2ccac`. Runtime is
`BLOCKED_ASSET_LICENSE`. Apache-2.0 covers OpenPI source only; Gemma terms are
separate, and no accepted local receipt establishes checkpoint, embedded Gemma,
tokenizer, or derived-weight rights. The official Orbax checkpoint and
tokenizer are absent locally; no deterministic conversion manifest,
safetensors output, complete key/shape/dtype/hash accounting, or selected
embodiment normalization asset exists. No Pi0.5 runtime was executed. See the
[Pi0.5 asset handoff](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-asset-pi05-w1/handoff.yaml).

## Explicit non-claims

M10 makes no model-quality claim; no N1.7 or Pi0.5 checkpoint load claim; no
official real-batch, training-step, prediction, save, or resume claim; no DDP,
DeepSpeed ZeRO-1/2/3, cross-node, throughput, scaling, or profiler result; and
no backend winner claim. `NO_BACKEND_WINNER`.
