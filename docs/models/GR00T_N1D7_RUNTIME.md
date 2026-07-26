# GR00T N1.7 M12 运行时状态

## Lock 状态

`gr00t_n1d7_runtime` 固定到 Isaac-GR00T
`9c7e746b2cd37a810070a98ef41d290a07e806c2`，使用 CPython 3.12 与
`uv==0.11.7`。deterministic lock SHA256 为
`919a9e6256a58f801676d1913f536904d7aba47b41b3386920ac3b952e3d63c6`。

源码审计已通过。Linux x86_64 有效关键包为：

- `torch==2.9.0+cu128`
- `torchvision==0.24.0+cu128`
- `transformers==4.57.3`
- `flash-attn==2.8.3`
- `deepspeed==0.17.6`

这是 resolved candidate lock，不是已实现环境；`runtime_lock_accepted: false`。

## 环境状态

环境尚未 materialize 或验证。当前没有 Torch/CUDA、FlashAttention、DeepSpeed、processor、
模型构造或目标 GPU 环境收据。

## 资产与外部门禁

checkpoint 许可文本与模型卡使用范围仍存在未解决冲突。Cosmos-Reason2-2B 仍要求独立
gated access 与 terms receipt；本地资产存在不能替代用户接受收据。两个门禁均 fail
closed，禁止把 deterministic lock 提升为模型运行授权。

## Runtime acceptance

没有 checkpoint 加载、CUDA、训练、推理或生产运行收据。该家族不能声明 environment
verified、runtime ready 或 train ready。

active zoo 身份为 `gr00t_n1d7`；后端决策保持 literal `NO_BACKEND_WINNER`。
