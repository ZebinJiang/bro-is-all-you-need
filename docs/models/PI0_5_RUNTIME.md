# Pi0.5 M11 运行时发布状态

## 当前结论

Pi0.5 当前状态为 `BLOCKED_LICENSE`，不得构造或运行模型。

Wave 4 接受了固定 OpenPI 源码版本及其源码许可收据，但这不构成权重或运行时授权。
下列门禁仍未闭合：

- Gemma 派生权重所需条款尚未由用户授权接受。
- checkpoint 与 tokenizer 缺少不可变 generation、digest 或等价身份收据。
- embodiment 对应的 normalization 资产身份尚未确定。
- 隔离的 JAX/Flax/Orbax 转换流程尚无严格、完整且可复现的转换收据；这些依赖也不得进入
  `pi0_5_runtime` 训练环境。
- 真实数据的物理语义、embodiment 和 dataset-model binding 尚未闭合。

因此当前证据不支持 checkpoint 转换、模型构造、CUDA 执行、训练、推理或任何
runtime/train ready 声明。

后端决策保持：`NO_BACKEND_WINNER`。
