# GR00T N1.6 M12 运行时状态

## Lock 状态

`gr00t_n1d6_runtime` 固定到 Isaac-GR00T
`5dc80c4afd726b34faad1d8f7e007a13b34e4c88`，使用 CPython 3.10 与
`uv==0.11.7`。deterministic lock SHA256 为
`5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2`。

源码审计和 `uv lock --check` 已通过。Linux x86_64 有效关键包为：

- `torch==2.7.1+cu128`
- `torchvision==0.22.1+cu128`
- `transformers==4.51.3`
- `flash-attn==2.7.4.post1`
- `deepspeed==0.19.2`

这是 resolved candidate lock，不是已实现环境；`runtime_lock_accepted: false`。

## 环境状态

环境尚未 materialize，也没有解释器、完整 distribution 清单、CUDA、FlashAttention、
DeepSpeed 或目标 GPU 环境收据。不得从 lock 的存在推导 runtime compatibility。

## 资产与外部门禁

checkpoint 相关资产物理存在，但 access/terms receipt 缺失。large shard 的当前重哈希需要
compute，本次任务明确 deferred。资产存在不等于条款已接受，也不等于当前完整哈希已复核。
真实数据、embodiment 与 dataset-model binding 的接受证据仍是独立门禁。

## Runtime acceptance

没有新的模型构造、checkpoint 加载、forward、backward、参数更新、prediction、resume、
DDP、DeepSpeed 或生产运行收据。因此该家族不能声明 environment verified、runtime ready
或 train ready。

active zoo 身份为 `gr00t_n1d6`；后端决策保持 literal `NO_BACKEND_WINNER`。
