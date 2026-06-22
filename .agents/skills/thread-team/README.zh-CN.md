# codex-thread-team

`codex-thread-team` 是一个 Codex skill，用来让一个 leader thread 协调多个真实的 Codex worker thread。

它把大型、可并行的编码任务变成一个“小团队”流程：当前线程担任 leader，创建隔离的 worker 线程，为每个 worker 分配清晰的任务边界和分支，轮询进度，收集已提交的完成报告，按顺序合并 worker 分支，最后由 leader 做整体复查。

## 适用场景

当任务足够大，而且可以安全拆成多个低冲突工作流时，使用这个 skill。

适合的任务包括：

- 后端、前端、迁移、文档、测试等相互独立的工作流；
- 文件重叠少、可以用分支和 worktree 隔离的改动；
- leader 能在 worker 开始前定义稳定契约的任务；
- 需要串行 merge 和逐步验证来降低集成风险的任务。

不适合的任务包括：

- 很小的单人编辑；
- 需求还模糊、无法负责任拆分的任务；
- 多个 worker 都要改同一批核心文件的紧耦合重构；
- 连续上下文比并行吞吐更重要的工作。

这个 skill 故意偏保守：它会先评估 thread-team 是否真的值得。如果并行只会增加协调成本，它应该建议直接单线程完成。

## 协作模型

这个 skill 把 Codex threads 当作一个小型工程团队，而不是一组可以随便并行的 agent。

leader thread 对整体结果负责。它分析任务，判断并行是否值得，定义任务边界，创建 worker thread，分配分支和 worktree，做团队级决策，协调 blocker，按顺序集成 worker 分支，并执行最终复查。leader 不会在派发任务后消失；最终结果仍然由 leader 兜底。

每个 worker thread 只负责一个边界清晰的任务。worker 拥有一个 task boundary、一个 branch、一个隔离工作目录。它可以为了接口细节或依赖问题和其他 worker 协作，但共享契约变更、跨责任边界问题、无法解决的 blocker，以及完成报告，都必须回到 leader。

这个协作模型是有意不对称的：

- **leader 决策并集成**：架构、公开 API、数据模型变化、merge 顺序、冲突处理和最终正确性都由 leader 负责。
- **worker 执行边界内任务**：worker 在自己的范围内实现、自查、验证、提交并报告。
- **peer 可以协作，但不能治理团队**：worker 可以互相沟通，但 peer agreement 不能替代 leader 对团队级决策的批准。
- **并行需要被证明值得**：只有当任务边界、分支隔离和验收标准足够清晰时，workflow 才应该创建 worker。

它的目标不是简单地“多开几个 Codex”。真正目标是让并行 Codex 工作更像有纪律的工程协作：明确 ownership、显式 contract、隔离工作区、结构化报告、串行集成，以及最终责任归属。

## 运行要求

这个 skill 依赖 Codex app 的 thread 管理能力：

- `create_thread`
- `send_message_to_thread`
- `read_thread`
- 可选：`list_threads`、`set_thread_title`、`set_thread_archived`、`fork_thread` 和 heartbeat automation

对于仓库内任务，每个 worker 都必须有独占工作目录，最好通过 Codex project worktree 创建。只有分支不够；两个 worker 不能共享同一个 checkout。

worker 创建遵循当前 Codex 工具 schema。skill 不强制指定某个 worker model；除非用户明确要求覆盖模型，否则使用用户配置的默认模型。

## 安装

把仓库克隆到 Codex skills 目录，并命名为 `thread-team`：

```bash
mkdir -p "${CODEX_HOME:-$HOME/.codex}/skills"
git clone https://github.com/itmada/codex-thread-team.git "${CODEX_HOME:-$HOME/.codex}/skills/thread-team"
```

更新已有安装：

```bash
cd "${CODEX_HOME:-$HOME/.codex}/skills/thread-team"
git pull
```

## 使用方式

可以明确要求 Codex 使用这个 skill：

```text
Use $thread-team to split this task across a leader thread and collaborating worker threads.
```

也可以描述一个明显很大、可并行、可分支隔离的任务。此时 skill 应该先提议使用 thread-team 模式，而不是直接创建 worker。

示例：

```text
Use $thread-team to implement the new billing settings page. Split backend API work, frontend UI work, and tests across workers.
```

```text
Use $thread-team to parallelize this migration: one worker handles schema changes, one updates the data access layer, and one updates tests/docs.
```

## 工作流

该 skill 强制 leader 按六个阶段执行：

1. **Deep task analysis and parallel split**
   leader 先分析任务，判断并行是否值得，定义边界，并记录初始状态。

2. **Worker thread initialization**
   leader 创建真实 worker thread，分配 worker branch，并确保每个 worker 都有隔离的工作目录。

3. **Per-worker deep task design and dispatch**
   leader 为每个 worker 编写自包含的派发说明，包括任务范围、非目标、共享契约、验证方式、提交要求和报告格式。

4. **Progress polling and collaboration decisions**
   leader 先执行 startup gate，确认每个 worker 已启动，并验证实际 `pwd`、branch 和 HEAD；之后在适合时使用 heartbeat 轮询。

5. **Report collection and merge orchestration**
   worker 自查、验证、提交并报告。leader 按顺序逐个合并 worker 分支，并在每次合并后验证。

6. **Final leader review and repair**
   leader 做整体复查；如果发现集成问题，直接修复并重新验证；最后确认清理完成。

## 安全机制

这个 skill 的核心是防止多线程协作里最常见的翻车点：

- **并行可行性评估**：只有当并行收益大于协调成本时，才创建 worker thread。
- **工作目录隔离**：每个 worker 必须在自己的工作目录中操作；两个 worker 绝不能共享同一个 checkout。
- **确定性分支命名**：worker 分支使用 `worker-<short-task>-<worker-role>`。
- **启动验证**：正式派发后，worker 必须先确认实际 `pwd`、branch 和 HEAD，leader 才能把隔离状态标记为 verified。
- **leader 状态落盘**：leader 把 roster、分支、worktree、决策、报告、merge 顺序、heartbeat 和清理状态记录到 `.thread-team/state.md`。
- **结构化完成报告**：worker 必须自查、修复发现的问题、验证、提交，并发送完成报告，才算完成。
- **串行集成**：leader 一次只合并一个 worker 分支，并在每次合并后验证。
- **heartbeat 清理**：workflow 创建的 heartbeat automation 必须在结束或提前退出前删除。

## 仓库结构

```text
thread-team/
├── SKILL.md
├── agents/
│   └── openai.yaml
└── references/
    ├── final-report-template.md
    ├── leader-state-template.md
    ├── status-template.md
    ├── worker-dispatch-template.md
    ├── worker-registration-template.md
    └── worker-report-template.md
```

## 模板说明

- `references/worker-registration-template.md`：在完整任务派发前注册 worker。
- `references/worker-dispatch-template.md`：给 worker 完整任务边界、验证计划和完成要求。
- `references/worker-report-template.md`：规范 worker 完成报告。
- `references/leader-state-template.md`：定义 leader 的持久化协调记录。
- `references/status-template.md`：规范面向用户的进度更新。
- `references/final-report-template.md`：规范集成和最终复查后的 leader 总结。

## 维护建议

- `SKILL.md` 只放 Codex 执行 workflow 时真正需要的指令。
- 可复用的 prompt、报告、状态格式放到 `references/`。
- 当真实 Codex thread 工具可用时，不要用临时 subagent 假装 worker thread。
- 更新 thread 工具行为时，遵循当前 Codex tool schema，不要硬编码模型或运行时默认值。
- 维护时尽量使用小 diff 修改已有文件，不要删除再重建，方便 review 模板历史。
