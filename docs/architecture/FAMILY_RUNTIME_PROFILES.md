# Family Runtime Profiles

## Scope

M12 把家族环境拆成四个不可互相提升的身份层：

1. `RuntimeProfileSpec`：源码声明的 Python、平台、resolver、精确已知包与禁止包约束。
2. `ResolvedRuntimeLock`：一次独立解析产生的精确包、可用制品 SHA256、resolver 版本、平台意图和上游 revision。
3. `RuntimeEnvironmentReceipt`：从精确 lock 实现出的解释器、完整 distribution 清单及 Torch/CUDA/cuDNN/NCCL/GPU 观测。
4. `RuntimeExecutionReceipt`：把源码、profile、lock、环境、资产、命令、拓扑、操作和证据路径绑定为一次执行事实。

前一层只提供后一层的输入条件，不证明后一层存在。声明不会证明 lock，lock
不会证明环境，环境不会证明家族代码执行。每一层都使用不可变值、严格动态解析、
完整摘要和确定性 JSON fingerprint。

## Compatibility Surface

`RuntimeProfileSpec` 是唯一规范声明类型。旧名称 `FamilyRuntimeProfile` 是同一个
类型的直接别名，因此 M1-M11 调用者可以继续访问 `profile_id`、`kind`、
`exact_packages`、`lock_accepted`、`blockers` 和 `is_training_runtime`。

旧 lock 字段只保留为兼容读取信息。它们不会构造 `ResolvedRuntimeLock`，也不会被
环境或执行收据接受为解析证据。`to_spec_dict()` 与 `fingerprint` 只描述声明层，
排除旧 lock 实现状态。

## Strict Identity

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
平台意图、显式精确包及禁止包全部匹配。
`RuntimeEnvironmentReceipt.validate_lock()` 要求已安装清单与 lock 完全相等。
`RuntimeExecutionReceipt.from_command()` 只接受通过验证的环境收据。

## Safe Publication Plan

`EnvironmentPublicationPlan` 是无副作用计划，不创建目录、不运行 uv、不写 marker。
它只描述：

- canonical root `.autovla_envs`；
- canonical target `.autovla_envs/<profile-id>`；
- 同级 `.materializing-<profile-id>-<nonce>` staging；
- canonical cache `.autovla_cache/uv`；
- `uv sync --offline --locked` 的未来授权命令形状；
- staging 检查、marker 与目录 fsync、`os.replace` 和父目录 fsync 顺序。

计划拒绝 repository/environment/target/staging 符号链接、已有 canonical target、
已有 staging 和非规范 nonce。合法计划不得写入任何主机绝对路径。

本 Wave 仅允许 tiny temporary fixtures 和显式注入的 fake command runner 验证历史
事务边界。`RuntimeEnvironmentManager` 没有默认命令 runner；`create`、环境 probe
和 `exec` 在真实命令启动前以 `FAKE_COMMAND_RUNNER_REQUIRED` 关闭。正式 resolver、
安装、环境实现和家族执行属于后续授权 Wave。

## Redaction

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
- `create`：本 Wave 只允许显式 fake runner 的事务 fixture；
- `verify`：缺失环境时只读失败；已有环境 probe 只允许显式 fake runner；
- `exec`：要求通过验证且只允许显式 fake runner。

`create`、`verify` 和 `exec` 不调用 `resolve`，也不更新 lock。

## Independent Profiles

注册表固定为四个独立声明：

- `gr00t_n1d6_runtime`
- `gr00t_n1d7_runtime`
- `pi0_5_runtime`
- `pi0_5_conversion`

N1D6、N1D7、Pi0.5 runtime 和 Pi0.5 conversion 不共享 lock。Pi0.5 runtime
继续禁止 JAX、Flax 和 Orbax；conversion 不能冒充训练 runtime。本 Wave 不制造
任何未审查精确版本、resolver 版本、上游 revision 或接受状态。

## Deferred Evidence

以下内容明确不由本接口提交证明：

- 真实依赖解析、网络/cache fill、lock 接受；
- 环境创建、包安装、build isolation 或 CUDA extension 构建；
- Torch/CUDA/cuDNN/NCCL/GPU compatibility；
- DeepSpeed 运行兼容；
- 资产、terms、checkpoint 或数据绑定授权；
- 模型构造、forward、backward、optimizer、prediction、resume 或 profiling；
- GPU、Slurm、跨节点或 backend winner 结论。

`NO_BACKEND_WINNER` 保持不变。
