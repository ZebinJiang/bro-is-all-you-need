# GR00T N1.7 M11 运行时发布状态

## 当前结论

GR00T N1.7 当前状态为 `BLOCKED_LICENSE`，不得构造或运行模型。

Wave 4 确认了固定版本的公开源码及本地 checkpoint/Cosmos 资产清单，但这些事实没有解除
许可门禁：checkpoint 随附许可与模型卡对使用范围的表述存在未解决冲突，且本地存在
Cosmos 资产不能证明用户已经接受其 gated 条款，当前也没有对应的接受收据。

此外，`gr00t_n1d7_runtime` 尚无已接受的精确 lock 或已实现环境指纹。当前证据不支持
checkpoint 加载、CUDA 执行、训练、推理或任何 runtime/train ready 声明。许可门禁解除前，
不得尝试模型构造或运行。

后端决策保持：`NO_BACKEND_WINNER`。
