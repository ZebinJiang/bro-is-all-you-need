# M11 GPU runtime matrix

This matrix records current evidence, not intended capability.

| Family | Source architecture | Assets/license | Data gate | Runtime profile | CUDA training evidence |
|---|---|---|---|---|---|
| `gr00t_n1d6` | executable family source | `PASS_ASSET_READY`, restrictive non-commercial terms | `BLOCKED_C3_DATA` | contract requires Torch 2.7.1 + DeepSpeed 0.19.2; preserved lock has Torch 2.6.0 and no DeepSpeed, so it is rejected | unvalidated |
| `gr00t_n1d7` | executable family source | `BLOCKED_LICENSE` | not eligible | exact versions and lock unresolved | prohibited and unvalidated |
| `pi0_5` | executable family source | `BLOCKED_LICENSE` | not eligible | exact versions and lock unresolved | prohibited and unvalidated |

`autovla-train` fails before Torch import and CUDA/model/data side effects while
any controlling gate is unresolved. Asset availability alone is not training
readiness. A source-complete factory is not checkpoint, construction, forward,
backward, update, resume, distributed, performance, or quality evidence.

Supported source topology contracts are single GPU, DDP, and typed DeepSpeed
ZeRO 1/2/3 where declared by the family. FSDP/FSDP2 and CPU model runtime are
absent. No topology is validated by Wave 5, and `NO_BACKEND_WINNER` is unchanged.

本矩阵中的依赖修复仅消除声明层面的互斥 Torch 约束；没有生成 lock，也没有执行环境创建、
模型、CUDA、GPU 或 Slurm 验证。
