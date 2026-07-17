# Training and distributed architecture

## Composition boundary

`autovla-train` is the sole production composition root. It resolves one active
family definition, requires its fail-closed asset/data gate to authorize
training, verifies one realized CUDA runtime profile, and then asks the family
factory for one `ModelRuntimeBundle`. The bundle is the only source of the
processor, model, checkpoint adapter, checkpoint evidence, tuning/freeze
evidence, asset identities, and runtime-profile identity.

The root rejects, before Torch import, CUDA binding, model construction, or data
opening:

- non-executable or assembly-ineligible definitions;
- `BLOCKED_C3_DATA`, `BLOCKED_LICENSE`, and any other non-authorized asset/data gate;
- missing, conversion-only, CPU, unrealized, blocked, or incompatible runtime profiles;
- profile/family/lock drift between the verified environment and runtime bundle;
- factories that return a raw assembly result instead of `ModelRuntimeBundle`.

N1.6 asset acceptance does not clear `BLOCKED_C3_DATA`. N1.7 and Pi0.5 remain
`BLOCKED_LICENSE`. None of these states is promoted by this source architecture.

## One lifecycle

`TrainingEngine` owns iteration, processor calls, callbacks, telemetry, stop
decisions, and checkpoint cadence. Exactly one `PreparedTrainingSession`,
created by exactly one strategy, owns the prepared model, optimizer, scheduler,
accumulation, backward, update, finite reduction, and strategy checkpoint
backend. There is no family trainer, FSDP path, or CPU model path.

DDP uses one process per CUDA device and suppresses gradient synchronization on
non-boundary microbatches. DeepSpeed uses typed ZeRO stage 1, 2, or 3 config;
its engine exclusively performs backward, update, clipping, scheduler movement,
and sharded checkpoint save/load. ZeRO-3 exposes one one-shot initialization
context, entered by the family factory for all parameter allocation.

M11 的 N1.6 环境元数据显式组合 family model extra 与 `training-deepspeed`：前者持有
`torch==2.7.1`，后者只持有既有 `deepspeed==0.19.2`。保留 lock 的 Torch 2.6.0 与
DeepSpeed 缺失仍使该画像不可接受；此处只描述依赖合同，不代表 DeepSpeed 可安装或可运行。

The engine checks scalar-loss finiteness before backward. Native/DDP sessions
also check gradient finiteness; distributed finite decisions use an all-rank
minimum reduction. DeepSpeed validates public global/skipped/micro-step counters
before and after every update and fails if exactly-one-step semantics cannot be
proved.

## Checkpoint identity

Every production checkpoint records the family definition, processor and model
types, checkpoint adapter and immutable checkpoint fingerprint, tuning strategy,
asset bundle and manifest fingerprints, runtime profile plus portable lock and
realized-environment fingerprints, complete training plan, topology, optimizer,
scheduler, accumulation, data identities, and resume topology. Native/DDP state
is owned by the prepared session and checkpoint manager. DeepSpeed model,
optimizer, and scheduler state is owned by `DeepSpeedEngine`; the public manager
must not restore those objects a second time.

## Validation boundary

This document describes source contracts only. M11 Wave 5 ran no model runtime,
CUDA forward/backward/update, checkpoint load/resume, DDP, DeepSpeed, cross-node,
throughput, or scaling validation. Those claims require separately accepted GPU
evidence. `NO_BACKEND_WINNER` remains in force.
