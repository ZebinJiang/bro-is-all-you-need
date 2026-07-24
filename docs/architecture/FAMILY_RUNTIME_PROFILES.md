# 家族运行时画像

## 范围

M12 把家族环境拆成四个不可互相提升的身份层：

1. `RuntimeProfileSpec`：源码声明的 Python、平台、resolver、精确已知包与禁止包约束。
2. `ResolvedRuntimeLock`：一次独立解析产生的精确包、可用制品 SHA256、resolver
   版本、平台意图、上游 revision 和显式 CUDA 兼容意图。
3. `RuntimeEnvironmentReceipt`：从精确 lock 实现出的解释器、完整 distribution 清单及
   Torch/CUDA/cuDNN/NCCL/GPU 观测。
4. `RuntimeExecutionReceipt`：把源码、profile、lock、环境、资产、命令、拓扑、操作和
   证据路径绑定为一次执行事实。

前一层只提供后一层的输入条件，不证明后一层存在。声明不会证明 lock，lock 不会证明
环境，环境不会证明家族代码执行。每一层都使用不可变值、严格动态解析、完整摘要和
确定性 JSON fingerprint。

## 兼容表面

`RuntimeProfileSpec` 是唯一规范声明类型。旧名称 `FamilyRuntimeProfile` 是同一个类型的
直接别名，因此 M1-M11 调用者可以继续访问 `profile_id`、`kind`、
`exact_packages`、`lock_accepted`、`blockers` 和 `is_training_runtime`。

旧 lock 字段只保留为兼容读取信息。它们不会构造 `ResolvedRuntimeLock`，也不会被环境或
执行收据接受为解析证据。旧兼容报告只能通过 `LegacyRuntimeProfileAdapter` 显式请求；
该适配器拒绝 create/exec，不能把 M11 画像状态提升为 M12 lock 或执行授权。
`to_spec_dict()` 与 `fingerprint` 只描述声明层，排除旧 lock 实现状态。

## 严格身份

所有动态记录拒绝：

- 未知或缺失字段；
- 整数冒充布尔值；
- 部分 SHA、大小写不规范摘要和空身份；
- 重复或未排序的精确包；
- 版本范围冒充解析版本；
- profile、Python、平台、lock、环境清单或源码身份漂移；
- 绝对路径、`..`、非规范仓库相对路径和非 canonical 环境路径；
- 通过状态携带失败诊断。

`ResolvedRuntimeLock.validate_profile()` 要求声明 fingerprint、Python 实现/版本、
平台意图、显式精确包、禁止包及 CUDA required 意图全部匹配。CUDA lock 还必须记录
Torch 编译 CUDA、runtime、driver、cuDNN、NCCL 和允许的 compute capability；
非 CUDA lock 不得夹带这些字段。
`RuntimeEnvironmentReceipt.validate_lock()` 要求已安装清单与 lock 完全相等。
`RuntimeExecutionReceipt.from_command()` 只接受通过验证的环境收据，要求执行
`source_sha` 与环境收据一致，并同时绑定证据相对路径和证据内容完整 SHA256。

## 安全发布计划

`EnvironmentPublicationPlan` 是 create 的权威输入计划。规划本身不创建目录、不运行
uv、不写 marker；执行前会在画像互斥锁内再次验证计划身份和文件摘要。它描述：

- project、`pyproject.toml` 与精确 `uv.lock` 的规范相对路径和完整摘要；
- canonical root `.autovla_envs`；
- canonical target `.autovla_envs/<profile-id>`；
- 同级 `.materializing-<profile-id>-<nonce>` staging；
- canonical cache `.autovla_cache/uv`；
- `uv sync --offline --locked` 的未来授权命令形状；
- staging 检查、marker 与目录 fsync、`os.replace` 和父目录 fsync 顺序。

marker 直接来自计划，包含 profile fingerprint、lock fingerprint、lock SHA256、
source SHA、descriptor/pyproject SHA256、lock path 和 canonical environment path。
计划拒绝 repository/environment/target/staging 符号链接、已有 canonical target、
已有 staging 和非规范 nonce。create 只运行计划中的 `uv sync --offline --locked`
命令，前后复核同一个 lock 内容，不解析、不生成、不更新 lock。合法计划不得写入任何
主机绝对路径。

测试只注入 fake command runner。`RuntimeEnvironmentManager` 默认提供
`OfflineSubprocessRunner`，使后续明确授权的操作具有可用真实 subprocess 路径；
默认 runner 不改变 create 的 `--allow-create` 授权门，也不提供网络回退。本次投影
没有运行 resolver、安装、环境实现或家族命令。

## 脱敏

子进程环境通过 `redact_environment()` 删除：

- 名称包含 proxy、token、secret、credential、auth、access key 或 API key 的变量；
- `PYTHONHOME`；
- `PYTHONPATH`。

环境与执行收据只记录仓库相对路径。执行收据保存命令 basename 和完整 argv 的
SHA256，不保存 argv 内容，因此 token、参数路径和凭据不会进入 tracked receipt。

## CLI

公共命令保持：

- `list`：读取四个 packaged 声明；
- `inspect`：读取声明，并在显式 checkout 下静态检查项目/lock 文件；
- `resolve`：输出 `blocked_static_planning_only` 的确定性解析计划，不访问网络；
- `create`：要求 `--lock-receipt`、`--nonce` 和显式 `--allow-create`；
- `verify`：要求 `--lock-receipt`，只读检查计划 marker 并生成环境收据；
- `exec`：要求精确 lock、通过环境收据、资产/拓扑 fingerprint、操作 token 和证据路径。

`create`、`verify` 和 `exec` 不调用 `resolve`，也不生成、替换或更新 lock。`exec`
消费传入的环境收据，不隐式调用 `verify`；命令结束后从 `runs/` 下证据文件计算完整
SHA256 并生成 `RuntimeExecutionReceipt`。

## Wave 4 deterministic locks

四个 lock 均由 `uv==0.11.7` 解析，且互不共享：

| Profile | Python | Upstream pin | Lock SHA256 | 关键有效包 |
| --- | --- | --- | --- | --- |
| `gr00t_n1d6_runtime` | 3.10 | `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | `5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2` | Torch 2.7.1+cu128、TorchVision 0.22.1+cu128、Transformers 4.51.3、FlashAttention 2.7.4.post1、DeepSpeed 0.19.2 |
| `gr00t_n1d7_runtime` | 3.12 | `9c7e746b2cd37a810070a98ef41d290a07e806c2` | `919a9e6256a58f801676d1913f536904d7aba47b41b3386920ac3b952e3d63c6` | Torch 2.9.0+cu128、TorchVision 0.24.0+cu128、Transformers 4.57.3、FlashAttention 2.8.3、DeepSpeed 0.17.6 |
| `pi0_5_runtime` | 3.12 | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | `289d82b1d894e2aa62851258ebab4b2ecc3111965d1f202bdbf621d220cd4825` | Torch 2.7.1、Transformers 4.53.2、DeepSpeed 0.19.2；禁止 JAX/Flax/Orbax |
| `pi0_5_conversion` | 3.12 | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | `17ec3257ec9800a1ab8b22e6f7ba17846911ea60726b6fbf601454083ff33f88` | JAX/JAXlib 0.5.3、Flax 0.10.2、Orbax-checkpoint 0.11.13、NumPy 1.26.4、Torch 2.7.1、Transformers 4.53.2 |

`runtime_lock_accepted: false` 保持不变：它表示候选 lock 尚未通过目标环境和运行时收据被
packaged runtime 接受，不表示 lock 仍未解析。画像中的 `runtime_lock_status`、完整
SHA256 和 blocker 共同保存这一区分。

## Wave 5 外部门禁

| Profile | Lock | Environment | Asset / terms / data | Runtime acceptance |
| --- | --- | --- | --- | --- |
| N1D6 | 源码审计与 check 通过 | 未 materialize、未验证 | 资产物理存在，但 access/terms 收据缺失；large-shard 当前 rehash 需 compute | 未接受 |
| N1D7 | 源码审计通过 | 未 materialize、未验证 | checkpoint 许可冲突；Cosmos gated terms 收据缺失 | 未接受 |
| Pi0.5 runtime | 源码审计通过 | 未 materialize、未验证 | checkpoint/Gemma terms 与 dataset-model binding 缺失 | 未接受 |
| Pi0.5 conversion | 源码审计通过 | 未 materialize、未验证 | 输入 payload、Gemma terms 与 conversion/output receipt 缺失 | 仅转换，未接受 |

Pi0.5 runtime 继续禁止 `jax`、`jaxlib`、`flax`、`orbax` 和
`orbax-checkpoint`。这些依赖只允许出现在独立 conversion profile；conversion profile
不得冒充训练或生产 runtime。

## Zoo 边界

active zoo 只包含：

- `gr00t_n1d6`
- `gr00t_n1d7`
- `pi0_5`

`pi0` 与 `pi0_fast` 保持 deferred。`pi0_5_conversion` 是 Pi0.5 的隔离工具画像，不是
第四个 active family。

## 延后证据

以下内容明确不由本投影证明：

- 环境创建、包安装、build isolation 或 CUDA extension 构建；
- Torch/CUDA/cuDNN/NCCL/GPU compatibility；
- DeepSpeed 运行兼容；
- 资产 access/terms、checkpoint 或数据绑定授权；
- conversion payload、执行或输出收据；
- 模型构造、forward、backward、optimizer、prediction、resume 或 profiling；
- GPU、Slurm、跨节点或 backend winner 结论。

所有外部门禁继续 fail closed，后端决策保持 literal `NO_BACKEND_WINNER`。
