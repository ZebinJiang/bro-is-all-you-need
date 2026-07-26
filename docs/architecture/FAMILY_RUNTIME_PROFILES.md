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
`source_sha` 与环境收据一致，并同时绑定非 editable 安装包源码 SHA256、证据相对路径和
证据内容完整 SHA256。materialize 的计划、marker 与环境收据绑定同一个
`package_source_sha256`；verify 会确认 `autovla` 从 realized `.venv` 内导入且安装字节与
checkout 计划摘要一致。

## 安全发布计划

`EnvironmentPublicationPlan` 是 create 的权威输入计划。规划本身不创建目录、不运行
uv、不写 marker；执行前会在画像互斥锁内再次验证计划身份和文件摘要。它描述：

- project、`pyproject.toml` 与精确 `uv.lock` 的规范相对路径和完整摘要；
- canonical environment root `.autovla_envs`；
- profile root `.autovla_envs/<profile-id>`，它不是 Python 环境；
- lock publication `.autovla_envs/<profile-id>/<lock-fingerprint>`；
- realized environment `.autovla_envs/<profile-id>/<lock-fingerprint>/.venv`；
- profile root 下同级
  `.materializing-<lock-fingerprint>-<nonce>` staging；
- canonical cache `.autovla_cache/uv`；
- `uv sync --offline --locked` 的未来授权命令形状；
- staging 检查、marker 与目录 fsync、`os.replace` 和父目录 fsync 顺序。

marker 直接来自计划，包含 profile fingerprint、lock fingerprint、lock SHA256、
source SHA、package source SHA256、descriptor/pyproject SHA256、lock path 和
lock-scoped canonical environment path。
计划拒绝 repository/environment/target/staging 符号链接、已有 canonical target、
已有 staging 和非规范 nonce。create 只运行计划中的 `uv sync --offline --locked`
命令，前后复核同一个 lock 内容，不解析、不生成、不更新 lock。合法计划不得写入任何
主机绝对路径。

测试只注入 fake command runner。`RuntimeEnvironmentManager` 默认提供
`OfflineSubprocessRunner`，使后续明确授权的操作具有可用真实 subprocess 路径；
默认 runner 不改变 create 的 `--allow-create` 授权门，也不提供网络回退。M12 历史投影
没有运行 resolver、安装、环境实现或家族命令；该历史非声明不覆盖下述 M13 已完成的
N1D6 environment materialization/verification 证据。

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
- `inspect`：读取声明，并在显式 checkout 下静态检查项目/lock 文件；输出分别命名
  `profile_root` 与 `realized_environment_path_template`；
- `resolve`：要求显式 checkout 和 CUDA intent 收据，离线解析提交内现有
  `pyproject.toml`/`uv.lock`，返回严格 `ResolvedRuntimeLock`，不创建或改写 lock；
- `cache`：仅在显式 `--allow-network` 时联网填充 workspace `.autovla_cache/uv`，随后
  必须以 `--offline --locked --dry-run` 验证 cache 完整性；
- `create`：要求 `--lock-receipt`、`--nonce` 和显式 `--allow-create`；
- `verify`：要求 `--lock-receipt`，只读检查计划 marker 并生成环境收据；
- `exec`：要求精确 lock、通过环境收据、资产/拓扑 fingerprint、操作 token 和证据路径。

`create`、`verify` 和 `exec` 不调用 `resolve`，也不生成、替换或更新 lock。`exec`
消费传入的环境收据，不隐式调用 `verify`；它在 runner 前验证全部收据字段及 canonical、
无符号链接的 `runs/` 证据路径，并在非 checkout 工作目录执行。命令结束后只接受本次
新建或内容发生变化的普通证据文件，计算完整 SHA256 并生成
`RuntimeExecutionReceipt`。CLI 只消费 child argv 前的第一个 `--`，后续 `--` 原样保留。
M13 N1D6 harness 的 `--output` 只接受
`runs/tmp/AUTOVLA-M13-ARCHITECTURE-FIRST-OFFICIAL-FAMILY-RUNTIME-REALIZATION-001/**`
规范相对路径；它以同目录临时文件和无覆盖原子发布写入，相同内容可幂等复用，不同既有
内容必须失败。

## Wave 4 deterministic locks

四个 lock 均由 `uv==0.11.7` 解析，且互不共享：

| Profile | Python | Upstream pin | Lock SHA256 | 关键有效包 |
| --- | --- | --- | --- | --- |
| `gr00t_n1d6_runtime` | 3.10 | `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` | `5daf8f2f83957fae82123c3e1510f57343c231c956939890bc5e803b170dd4e2` | Torch 2.7.1+cu128、TorchVision 0.22.1+cu128、Transformers 4.51.3、FlashAttention 2.7.4.post1、DeepSpeed 0.19.2 |
| `gr00t_n1d7_runtime` | 3.12 | `9c7e746b2cd37a810070a98ef41d290a07e806c2` | `919a9e6256a58f801676d1913f536904d7aba47b41b3386920ac3b952e3d63c6` | Torch 2.9.0+cu128、TorchVision 0.24.0+cu128、Transformers 4.57.3、FlashAttention 2.8.3、DeepSpeed 0.17.6 |
| `pi0_5_runtime` | 3.12 | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | `b1338785b2de1c52c318f369987248ea7a0708cf83ed81e64a8bd5b86221fc4e` | Torch 2.7.1、Transformers 4.53.2、DeepSpeed 0.19.2；禁止 JAX/Flax/Orbax |
| `pi0_5_conversion` | 3.12 | `15a9616a00943ada6c20a0f158e3adb39df2ccac` | `e8bb0ced26973bd9a4858133ca7f24426966e4358648e3dbe510e9c23090dbcb` | JAX/JAXlib 0.5.3、Flax 0.10.2、Orbax-checkpoint 0.11.13、NumPy 1.26.4、Torch 2.7.1、Transformers 4.53.2 |

`runtime_lock_accepted: false` 保持不变：它表示候选 lock 尚未通过目标环境和运行时收据被
packaged runtime 接受，不表示 lock 仍未解析。画像中的 `runtime_lock_status`、完整
SHA256 和 blocker 共同保存这一区分。

共享 DeepSpeed 策略仅支持画像精确选择的 `0.17.6` 和 `0.19.2`。N1D7 选择
`0.17.6`，N1D6/Pi0.5 选择 `0.19.2`；运行时诊断必须同时报告 selected/installed
exact 版本并验证两版共同公共 API。该 source/API 合同不改变任何
`runtime_lock_accepted: false`，也不声明 CUDA、NCCL 或 ZeRO runtime 已通过。

## Wave 5 外部门禁（M12 历史快照）

| Profile | Lock | Environment | Asset / terms / data | Runtime acceptance |
| --- | --- | --- | --- | --- |
| N1D6 | 源码审计与 check 通过 | 未 materialize、未验证 | 资产物理存在，但 access/terms 收据缺失；large-shard 当前 rehash 需 compute | 未接受 |
| N1D7 | 源码审计通过 | 未 materialize、未验证 | checkpoint 许可冲突；Cosmos gated terms 收据缺失 | 未接受 |
| Pi0.5 runtime | 源码审计通过 | 未 materialize、未验证 | checkpoint/Gemma terms 与 dataset-model binding 缺失 | 未接受 |
| Pi0.5 conversion | 源码审计通过 | 未 materialize、未验证 | 输入 payload、Gemma terms 与 conversion/output receipt 缺失 | 仅转换，未接受 |

Pi0.5 runtime 继续禁止 `jax`、`jaxlib`、`flax`、`orbax` 和
`orbax-checkpoint`。这些依赖只允许出现在独立 conversion profile；conversion profile
不得冒充训练或生产 runtime。

## M13 N1D6 外部执行证据

上表是 M12 packaged profile 的历史快照，不能改写为 M12 已执行环境。M13 canonical E9
外部收据在 source SHA
`89a28b90a9a5fd70ce8ed08256275c073bd33bb7` 上新增了 N1D6 精确环境证据：

| Evidence | Exact identity |
| --- | --- |
| Slurm | materialize `4849`、verify `4850`，均为 `COMPLETED / 0:0` |
| Lock fingerprint | `c8b7de93de054ceec4e492b69782191312ca7ef8a6bd611d50c89d02ac6ba0c0` |
| Environment fingerprint | `93a33948eabffa60ae4f7afa23f43116f09a5f9f8beb8669a775388c4bc1e8f3` |
| Installed inventory fingerprint | `e7e41dd7a350bb317b995d6a7654e4ee0a816594538e892312eb2a171252f103` |
| Realized runtime | CPython `3.10.12`；Torch `2.7.1+cu128`；compiled/loaded CUDA `12.8`；driver `570.195.03`；cuDNN `9.7.1`；NCCL `2.26.2`；A100-SXM4-80GB，capability `8.0` |

该 receipt 证明 environment materialization/verification，不提升 packaged profile 的冻结
源码声明；literal `runtime_lock_accepted: false` 保持不变。它也不证明 asset terms、
checkpoint/model mechanics、DDP、DeepSpeed ZeRO、dataset-model binding 或 runtime
acceptance。后端决策继续是 `NO_BACKEND_WINNER`。

## Zoo 边界

active zoo 只包含：

- `gr00t_n1d6`
- `gr00t_n1d7`
- `pi0_5`

`pi0` 与 `pi0_fast` 保持 deferred。`pi0_5_conversion` 是 Pi0.5 的隔离工具画像，不是
第四个 active family。

## 延后证据

M12 本投影明确不证明：

- 环境创建、包安装、build isolation 或 CUDA extension 构建；
- Torch/CUDA/cuDNN/NCCL/GPU compatibility；
- DeepSpeed 运行兼容；
- 资产 access/terms、checkpoint 或数据绑定授权；
- conversion payload、执行或输出收据；
- 模型构造、forward、backward、optimizer、prediction、resume 或 profiling；
- GPU、Slurm、跨节点或 backend winner 结论。

M13 E9 只关闭上述 N1D6 environment materialization/verification 缺口；其余外部门禁继续
fail closed，后端决策保持 literal `NO_BACKEND_WINNER`。
