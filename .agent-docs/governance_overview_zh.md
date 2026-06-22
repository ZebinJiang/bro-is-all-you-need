# GenesisVLA / StarVLA 工程治理说明

## 项目身份

本仓库的当前工程底座是 **StarVLA**，目标项目是 **GenesisVLA**。

治理目标不是维护另一个独立项目名，而是把 StarVLA 作为可工作的工程母体，在本地监督机制下逐步演进到 `.agent-docs/GenesisVLA_Blueprint_Roadmap.html` 描述的 GenesisVLA 架构。

统一口径：

- 当前工程底座：StarVLA
- 目标项目：GenesisVLA
- 目标蓝图：`.agent-docs/GenesisVLA_Blueprint_Roadmap.html`
- 本地监督协议：`.agent-docs/teamwork/teamwork_supervisor_protocol.md`
- 本地进度状态：`.agent-docs/teamwork/roadmap_progress.md`

## 三层结构

### StarVLA 工程底座

StarVLA 提供当前可见的真实工程代码、训练/评测示例、配置、模型框架、部署入口和文档。

典型路径包括：

```text
starVLA/
examples/
deployment/
docs/
assets/
tests/
```

这些路径代表当前工程现实。任何新增模型、数据、训练、评测、推理、部署、迁移或兼容工作，都必须先检查真实 StarVLA 布局，再选择自然集成点。

### GenesisVLA 目标蓝图

GenesisVLA 是未来目标工程形态。

当前蓝图定义了：

- 项目命名和包路径迁移；
- core / config / data / model / runner / deployment / acceleration 七层架构；
- M0-M7 里程碑；
- 每个 milestone 的 features、TDD 和 Definition of Done；
- 团队职责、风险矩阵和第一批 issues。

GenesisVLA 名称可以进入未来新包、新 CLI、新文档和新配置，但不能在没有实现和验证证据时暗示能力已经存在。

### 本地治理和监督层

本地治理层负责让 agent 工作可控、可审阅、可回滚。

本地治理状态放在 `.agent-docs/`，默认被 git 忽略。除非用户明确改变策略，不发布、不推送、不写入 StarVLA 基础历史。

关键入口：

```text
AGENTS.md                                      # Codex / Manager / subagent 规则入口
CLAUDE.md                                      # Claude Code supervisor 本地私有入口
boundaries.txt                                 # 硬边界摘要
.agent-docs/teamwork/teamwork_supervisor_protocol.md
.agent-docs/teamwork/roadmap_progress.md
.agent-docs/feature_list.json
.agent-docs/progress.txt
.agent-docs/review.txt
```

## Claude / Codex 分工

Claude Code 是 supervisor。

Claude 负责：

- 读取完整 GenesisVLA 蓝图和本地进度；
- 选择当前 milestone；
- 决定当前阶段是 `DISCUSS`、`PLAN`、`EXECUTE`、`VERIFY` 还是 `REVIEW`；
- 通过 Teamwork 派发 Codex Manager；
- 决定 Codex worker plan：worker 数量、类型、串行/并行方式、读写路径和停止条件；
- 审阅 Codex 报告；
- 决定是否进入下一阶段；
- 必要时向用户提出窄问题。

Codex CLI 是受监管的 Manager，不是一次性叶子 worker。

Codex 负责：

- 执行当前被派发的一个 GSD stage；
- 保留当前 stage 的仓库上下文、worker 输出、验证证据和风险状态；
- 在需要 subagent 时，只启动 Claude 批准过的 Codex workers；
- 汇总并复核 worker 输出；
- 在不确定时通过 Teamwork consult 问 Claude；
- 输出 stage report 和 structured handoff；
- 遵守 `AGENTS.md`、`boundaries.txt` 和相关 `.agent-docs/` 政策；
- 在 Claude gate 前停下。

Codex 不能自己从 `DISCUSS` 跳到 `PLAN`，不能自己从 `PLAN` 跳到 `EXECUTE`，不能把自己的计划当成已批准，也不能绕过 Manager-worker 链路直接散派未受控实现 worker。

## 本地 Teamwork 状态

项目级 Teamwork 状态必须放在：

```text
.agent-docs/teamwork/
  roadmap_progress.md
  messages.jsonl
  claude-inbox.md
  next-actor.json
  workspace/task-board.md
  reports/<milestone-id>/<stage>.md
```

全局 `~/.claude/skills/teammate/` 可以作为脚本提供方，但不应该成为 GenesisVLA 项目进度事实源。

## 数据、运行和输出位置

原始数据必须放在：

```text
datasets/readonly/
```

派生数据、转换结果、索引、缓存和修补副本必须放在：

```text
datasets/working/
datasets/cache/
```

运行输出、日志、checkpoint、Slurm 输出、验证证据和临时运行产物必须放在：

```text
runs/
```

如果 StarVLA 原生配置或脚本默认写入 `playground/`、`results/` 等路径，agent 任务必须在该任务内改成受治理路径，不能直接沿用上游默认输出根。

## 基线保护

StarVLA 是当前工程底座，受保护。

直接修改 StarVLA 基线路径必须有：

- 明确任务范围；
- 修改理由；
- 验证证据；
- 回滚说明。

优先使用：

- 新 GenesisVLA-native 模块；
- config overlay；
- adapter；
- registry entry；
- subclass；
- migration loader。

## GSD 与 milestone

一个 GenesisVLA 小 milestone 对应一个本地 Teamwork task。

典型阶段：

```text
DISCUSS -> PLAN -> EXECUTE -> VERIFY -> REVIEW
```

`DISCUSS` 是 Claude/Codex 的交互过程，不是 Codex 单向报告。

`PLAN` 后必须停给 Claude 审阅。

`EXECUTE` 前必须有 Claude 明确批准。

涉及结构性代码、脚本、配置契约、模型路径、数据执行、Slurm wrapper 或调试修复时，必须遵守 `AGENTS.md` 的 Manager-worker 规则：Claude 批准 worker plan，Codex Manager 负责启动、复核、收口和汇报。

## 远端和同步

StarVLA upstream 不自动同步。

只有用户明确要求同步时，才允许 fetch / merge / rebase / sync，并且必须记录：

- 命令；
- 冲突；
- 解决方式；
- 验证证据。

GitHub 网络操作需要使用用户提供的代理。

## 外部服务

Hugging Face 下载允许，但必须落到受治理路径。

Hugging Face 上传禁止。

W&B logging/upload 允许，但只能使用统一 project：

```text
zjh-flywheel
```

任何 token、API key、凭据、私有 endpoint 都不能写入 repo 文件、提交、日志或待发布配置。

## 当前未完成事项

- `AGENTS.md` 和 `CLAUDE.md` 已切到 GenesisVLA / StarVLA 口径后，需要由用户审阅。
- 未来如需把物理目录从当前路径迁移到 `GenesisVLA`，应单独执行 workspace path migration。
