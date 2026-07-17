# M11 GPU runtime matrix

This matrix records current evidence, not intended capability.

| Family | Source architecture | Assets/license | Data gate | Runtime profile | CUDA training evidence |
|---|---|---|---|---|---|
| `gr00t_n1d6` | executable family source | `PASS_ASSET_READY`, restrictive non-commercial terms | `BLOCKED_C3_DATA` | exact lock described; realized-node compatibility not accepted for M11 | unvalidated |
| `gr00t_n1d7` | executable family source | `BLOCKED_LICENSE` | not eligible | exact versions and lock unresolved | prohibited and unvalidated |
| `pi0_5` | executable family source | `BLOCKED_LICENSE` | not eligible | exact versions and lock unresolved | prohibited and unvalidated |

`autovla-train` fails before Torch import and CUDA/model/data side effects while
any controlling gate is unresolved. Asset availability alone is not training
readiness. A source-complete factory is not checkpoint, construction, forward,
backward, update, resume, distributed, performance, or quality evidence.

Supported source topology contracts are single GPU, DDP, and typed DeepSpeed
ZeRO 1/2/3 where declared by the family. FSDP/FSDP2 and CPU model runtime are
absent. No topology is validated by Wave 5, and `NO_BACKEND_WINNER` is unchanged.
