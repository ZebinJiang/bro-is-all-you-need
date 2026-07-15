# GPU and distributed runtime gate

M10 uses a serial correctness gate. Official asset provenance and typed receipt
must pass before checkpoint assembly; strict single-A100 checkpoint loading must
pass before a real batch; forward, backward, one optimizer update, prediction,
and save/resume must pass before DDP, DeepSpeed, cross-node, throughput, scaling,
or profiling. A source architecture or upstream capability is not local runtime
evidence.

## Accepted N1.6 checkpoint gate

GR00T N1.6.1 is pinned to Isaac-GR00T source
`5dc80c4afd726b34faad1d8f7e007a13b34e4c88` and checkpoint
`d0814e7ecb19202e7c8468b46098b0b7ef3a6d61`. Its official typed asset receipt
passed, and the W1/W2 checkpoint repairs were source-reviewed.

The final checkpoint gate ran at exact canonical HEAD
`ad0fe7074c2a4bd281f6e7ca87caec59a12898f3`. Slurm job `3408` used one
NVIDIA A100-SXM4-80GB and completed with exit `0:0`. The strict load mapped
1,010 tensors containing 3,286,608,832 elements, with zero missing keys, zero
unexpected keys, and zero shape mismatches. The observed loaded state was
`torch.float32` on `cuda:0`; checkpoint load time was `24.47898` seconds. Peak
CUDA allocation was 18,556,289,024 bytes and peak reservation was
18,834,522,112 bytes. This is a checkpoint-load result, not a training or model
quality result. See the [C2R7 handoff](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/agents/m10-cuda-n1d6-c2r7/handoff.yaml)
and [C2R7 receipt](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/compute/m10-cuda-n1d6-c2r7/assembly_load_receipt.json).

The progression records the first cause at each step:

- `3374`: typed asset receipt passed.
- `3382`: failed because the selected environment had no Torch module.
- `3391`: failed on a temporary receipt-field bug (`total_size`).
- `3397`: exposed the checkpoint key-mapping defect.
- `3401`: mapping keys were repaired, but the remaining FFN projection shapes
  were wrong.
- `3404`: strict checkpoint load passed, but the receipt omitted observed model
  state dtype evidence.
- `3408`: the complete checkpoint gate passed with dtype and device accounting.

## Current stop

The next N1.6 gate is `BLOCKED_C3_DATA`. The available black-rubber-bellows
candidate is LeRobot v2.1 `demo_bot` with state/action dimensions `72/98`. It
lacks the production reader metadata/index, has no evidenced mapping from
`demo_bot` to N1.6 `gr1`, and conflicts with the checkpoint-backed GR1 physical
dimensions `58/29`. No C3 job was submitted. See the
[C3 read-only plan](../../runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/compute/m10-cuda-n1d6-c3-ro/execution-plan.md).

Therefore no official real-batch forward, loss, backward, optimizer update,
prediction/decode, save, or fresh-process resume has passed. DDP, DeepSpeed
ZeRO-1/2/3, cross-node execution, backend throughput, scaling, and profiler
cells were not run because single-GPU real-batch correctness was not reached.
The architecture may describe those routes, but the runtime state is partial.
`NO_BACKEND_WINNER`.
