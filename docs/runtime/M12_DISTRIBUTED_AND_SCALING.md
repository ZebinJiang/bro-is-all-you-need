# M12 分布式与 scaling 状态

## 本 wave 已实现的 source contract

- 一套 `TrainingEngine` 与一套 strategy-created `PreparedTrainingSession` ownership。
- ZeRO-3 模型只在一次性 `deepspeed.zero.Init` 中分区构造。
- family adapter 继续拥有 official checkpoint 的格式、映射、严格性和 provenance。
- 三个 active family 都通过共享 partition sink 接入 ZeRO-3；缺 sink 时 fail closed。
- ZeRO-3 strategy 先用 metadata 与逻辑 full-shape 完成不 gather 的严格审计，再通过
  官方 `GatheredParameters` 逐次协调单参数组；每个参数只有一次 mutation gather。
- 只有 rank 0 写参数，退出上下文后同步分片；持久复制 buffer 由 rank 0 写入后显式广播。
- 三个 family 均用 `safe_open` metadata plan 和固定上限的按需来源切片；不在 host 或
  GPU 创建完整 checkpoint state dict，不构造非分区备用模型，不提供普通加载 fallback。
- local、DDP 和 ZeRO-1/2 继续使用原有严格 family loader。
- DeepSpeed 成功 close 与 prepare rollback 均尽力 destroy engine，并且只销毁自身拥有的
  process group。
- close 清除 engine、optimizer、scheduler 和 device 引用，保持幂等并保留首个异常。
- DDP/DeepSpeed 提供严格收据 collective 边界。
- plan 和 committed-sample receipts 具有版本、run/source/family/strategy/topology/
  training-plan 身份，聚合时要求完整 rank 覆盖并拒绝样本键重叠。
- receipts 的证据范围固定为 `DECLARED_PAYLOADS_ONLY`。
- 无 FSDP/FSDP2，保持 `NO_BACKEND_WINNER`。

## 本 wave 没有证明的事项

本 wave 未运行 GPU、Slurm、模型 materialization、checkpoint load、forward、
backward、optimizer step、NCCL collective、resume、teardown、profiler、吞吐或
scaling 测试。因此当前 source contract 不证明：

- 任一 official family checkpoint 可在 ZeRO-3 下成功加载；
- rank 参数值、committed samples 或 optimizer steps 在真实运行中一致；
- process group 或 DeepSpeed engine 在真实异常与成功路径中无泄漏；
- 单卡、DDP、ZeRO 1/2/3 或 cross-node 的性能与数值等价；
- 任一 backend 获胜或达到 production readiness。

## 后续 GPU receipt 最低字段

后续授权运行必须记录：

- 精确 source SHA、run id、family definition 和 strategy；
- verified asset/checkpoint、data binding 与 realized runtime profile 指纹；
- rank、local rank、world size、node、设备、precision、batch 和 accumulation；
- all-rank plan payload、committed-sample payload和聚合指纹；
- finite/overflow、committed optimizer steps、checkpoint 路径和 resume 身份；
- engine/process-group teardown receipt、进程退出状态和完整日志路径；
- profiler window 的 step 边界、指标单位和同一 run identity。

缺少真实 collective、进程退出或日志证据时，只能保留 source-level 状态。字面结论：
`NO_BACKEND_WINNER`。
