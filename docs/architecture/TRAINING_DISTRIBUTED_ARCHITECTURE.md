# Training 与分布式架构

## 组合边界

`autovla-train` 是唯一生产组合根。它先关闭 family、资产、数据、license 和
realized runtime profile gate，再创建一个策略并在模型分配前绑定本地 CUDA 设备。
family factory 返回的单个 `ModelRuntimeBundle` 是 processor、model、checkpoint
adapter、checkpoint evidence、tuning/freeze evidence、资产身份和 runtime profile
身份的唯一来源。

组合根不创建 family trainer、第二个 optimizer 或第二个 scheduler。模型构造完成后，
`TrainingEngine.setup()` 只调用一次 `strategy.prepare()`，并只接收一个
`PreparedTrainingSession`。

## 唯一训练所有权

`TrainingEngine` 负责：

- loader 迭代、processor 调用和 callback 顺序；
- loss finite 判定、stop decision 和 checkpoint cadence；
- 训练状态、telemetry 和异常传播。

`PreparedTrainingSession` 负责：

- prepared model、optimizer 和 scheduler；
- accumulation、backward、step 和 committed-step 计数；
- collective、梯度处理和策略 checkpoint backend；
- 策略创建的 engine 与 process group 的回收。

DDP 在非 accumulation boundary 使用 `no_sync`。DeepSpeed engine 是 backward、
step、gradient clipping、scheduler movement 和 ZeRO sharded checkpoint 的唯一权威。
`TrainingEngine` 中没有 DeepSpeed 分支，也不会直接调用 optimizer 或 scheduler step。

## ZeRO-3 构造与官方 checkpoint

ZeRO-3 只允许一次 `deepspeed.zero.Init`。family factory 在该上下文中完成全部参数
分配，策略记录上下文是否创建并拥有 process group。ZeRO-1/2 继续直接调用 family
严格 checkpoint loader。

ZeRO-3 的 official checkpoint 路径遵循以下协议：

1. family 仍负责 checkpoint 路径、格式、键映射、shape audit、严格性和 provenance；
2. 策略要求一次性 `zero.Init` 事务已经完成；
3. 三个 active family 都通过共享 `PartitionedCheckpointLoadSink` 交付 family-owned
   张量审计、写入和结果恢复，不允许 family-specific strategy 旁路；
4. 策略先用 checkpoint metadata 和 ZeRO 参数逻辑 full-shape 完成全模型键与 shape
   审计，再开始 mutation；审计不 gather 参数。mutation 时每次只把一个参数放入
   DeepSpeed 公共 `zero.GatheredParameters((parameter,), modifier_rank=0)`，组上界固定
   为一且必须严格小于模型参数总数；
5. 只有 rank 0 调用 sink 写参数。退出 `GatheredParameters` 后，DeepSpeed 负责重新分片
   和同步该参数；
6. buffer 不属于 ZeRO 参数分片。rank 0 写入已审计 buffer 后，策略通过公共 distributed
   broadcast 显式保持复制 buffer 的跨 rank 一致性；
7. 缺少 partition-aware sink、初始化事务未完成、rank inventory 漂移、单参数模型或
   collective 不可用时均 fail closed；
8. 策略不构造第二个非分区模型，不物化 GPU consolidated state dict，也没有异常后的
   普通 whole-model fallback。ZeRO-1/2、本地和 DDP 继续调用原有严格 family loader。

三个 family sink 都只用 `safe_open` 建立不含 tensor 的 metadata/index plan，并按目标
参数打开一个来源 tensor 或 N1.6 Q/K/V 有界来源组。来源数据按固定字节上限切片复制，
不会在 host 或 GPU 构造完整 checkpoint state dict。非 safetensors 或无法证明安全映射、
shape 和切片上界的格式直接 fail closed。

这是 source contract，不是 GPU load receipt。参数峰值、各 family 对 DeepSpeed
协调参数的真实兼容性和 ZeRO-3 初始化成功仍必须由后续受控 GPU run 证明。

## 对称资源回收

DeepSpeed prepare 失败和成功 session close 使用相同原则：

- 尽力调用 engine 暴露的 `destroy()`；
- 无论 destroy 是否失败都清除 engine、optimizer、scheduler 和 device 引用；
- 只销毁当前策略创建并拥有的 process group；
- 已存在的外部 process group 必须保留；
- close 幂等；
- 多个清理失败时抛出首个异常，后续异常只作为附注；
- 生成绑定策略、rank、拓扑和配置指纹的 teardown receipt。

`TrainingEngine.close()` 与异常关闭路径继续保留最先出现的业务或清理异常。静态测试只
验证状态机和失败注入，不代表 NCCL 或 DeepSpeed runtime 已成功回收。

## 分布式计划与样本唯一性收据

`autovla.training.distributed_receipts` 提供版本化、确定性、严格字段的两组载荷：

- rank-local plan receipt：运行身份、source SHA、family、strategy、world size、
  topology/training-plan 指纹、访问模式、partition policy、batch 和 accumulation；
- rank-local committed-sample receipt：同一身份、rank、epoch、optimizer-step 窗口和
  稳定样本键序列。

DDP 和 DeepSpeed session 只提供按 rank 排序的 `all_gather_object` 传输边界。聚合器
要求完整 rank 覆盖、完全一致的 plan 字段，并拒绝 rank 内或 rank 间重复样本键。
所有当前结构化结果固定标记为 `DECLARED_PAYLOADS_ONLY`，不能写成
`runtime_verified`。后续 GPU harness 必须同时保存 source、配置、日志、进程退出和
collective 调用证据后，才能把这些载荷作为真实运行材料。

checkpoint 身份继续由既有 production checkpoint manifest 负责；profiler identity
继续由未来 GPU harness 绑定同一 run identity。这里不新增重复 readiness source。

## 明确不支持

- 无 FSDP 或 FSDP2；
- 无 CPU model runtime；
- 无隐式下载或远程 checkpoint；
- 无 backend winner 选择；
- 无静态结果替代 single GPU、DDP、ZeRO 1/2/3 或 cross-node receipt。

字面结论保持 `NO_BACKEND_WINNER`。
