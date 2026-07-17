# GR00T N1.6 M11 运行时发布状态

## 当前结论

GR00T N1.6 的源码与 checkpoint 证据已经通过资产阶段验收。现有证据包括固定版本的
Isaac-GR00T 支持源码、固定版本的 GR00T N1.6 checkpoint、不可变资产收据，以及此前
已接受的一次 A100 严格 checkpoint 加载结果。Wave 4 未重新执行模型或 GPU 验证。

该家族目前仍然不能声明为 runtime ready 或 train ready，原因如下：

- `gr00t_n1d6_runtime` 的 M11 精确合同要求 Torch `2.7.1`；现存 `uv.lock` 实际解析为
  Torch `2.6.0`，因此 `runtime_lock_accepted: false`。接受的新 lock 与对应 compute-node
  runtime fingerprint 均不存在。
- 生命周期状态仍为 `BLOCKED_C3_DATA`。真实数据的物理语义、embodiment 绑定和可接受的
  数据证据尚未闭合。
- 资产可用性和历史严格加载证据不等价于 M11 模型构造、前向、反向、参数更新、预测、
  恢复、DDP 或 DeepSpeed 运行证据。

在运行时 lock 和 C3_DATA 同时闭合前，不得构造新的 runtime/train ready 声明。

后端决策保持：`NO_BACKEND_WINNER`。
