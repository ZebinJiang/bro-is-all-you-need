# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Training Diagnose Wave 7

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`: active worktree contains prior approved bakeoff WIP surfaces; this wave performed read-only diagnosis and writes only this report.

## 2. Bridge-Contract Diagnosis

### Conclusion

当前 `bridge-run -> --dataset-path candidate_store_root` 仍然是正确的公共 surface。

### Evidence

Training bridge 当前职责是：

- 接受一个候选 datastore root；
- 接受显式 provenance/config/fingerprint；
- 生成 offline/local-only Isaac argv；
- 把 `--dataset-path` 交给 Isaac runtime；
- 记录 AutoVLA-owned manifest / logs / tables。

Isaac 侧对 dataset root 的要求不是 “任意目录”，而是 **LeRobot-compatible dataset root**。证据很直接：

- `gr00t/data/dataset/lerobot_episode_loader.py` 明确读取：
  - `meta/info.json`
  - `meta/episodes.jsonl`
  - `meta/tasks.jsonl`
  - `meta/modality.json`
  - `meta/stats.json`
- `gr00t/configs/finetune_with_val_config.py:186` 对 split root 也要求标准 `meta/` 文件集合。
- `gr00t/data/stats.py` 会先读取：
  - `meta/info.json`
  - `meta/stats.json`
  - `meta/modality.json`

这说明 `candidate_store_root` 作为公共输入是对的；错的不是 Training 的 public contract，而是当前某些 candidate root 还没有满足 Isaac runtime 预期的 LeRobot metadata surface。

因此，不建议把 public contract 改成别的抽象名词来掩盖事实。更合适的做法是：

- 保持 `candidate_store_root` 作为桥接输入；
- 明确规定它要么本身就是 Isaac-acceptable dataset root，要么后续允许一个 task-local compatibility proxy 把它包装成 כזה root。

## 3. Raw-Baseline Training Diagnosis

### Observed failure

Wave 6 raw baseline compute logs显示：

- stdout:
  - `Generating stats for /home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- stderr:
  - `FileNotFoundError ... meta/modality.json`

进一步本波只读检查显示 raw root 当前只有：

- `meta/info.json`
- `meta/stats.json`
- `meta/tasks.jsonl`

没有：

- `meta/modality.json`
- `meta/episodes.jsonl`

并且 root-level `metadata.json` 基本只是 `info.json` 的镜像，不能自动替代 LeRobot-required `modality.json` / `episodes.jsonl`。

### Diagnosis

对 raw baseline 来说，**task-local compatibility proxy 在原则上是可接受的**，但前提必须非常窄：

1. raw source 是受保护的只读路径；
2. Training 不能直接修改 `datasets/readonly/**`；
3. 如果要让 raw baseline 继续参与 Isaac bounded run，必须在 `runs/tmp/**` 下构造一个 compatibility root；
4. 这个 proxy 只能做路径包装、目录拼接、manifest引用、必要的只读 metadata 落盘；
5. 它不能偷偷发明 dataset 语义、重排样本、改写 action/state 定义、改写统计值。

### Important boundary

虽然 proxy 方向在 raw baseline 上是合理的，但 **Training 不应独自发明 `modality.json` 和 `episodes.jsonl` 的语义**。这些文件描述的是数据契约，而不是训练控制逻辑。

因此，raw baseline 的最小诚实路线是：

- Data 提供 authoritative metadata payload 或生成逻辑；
- Training 仅把这些 metadata 以 task-local proxy 方式组合到一个 Isaac-acceptable compatibility root；
- `bridge-run` 仍只接收最终要传给 Isaac 的 dataset root。

## 4. `zjh_lerobot_v3_local` Training Diagnosis

### Observed failure

Wave 6 `zjh_lerobot_v3_local` compute logs显示：

- stdout:
  - `Generating stats for .../working/zjh_lerobot_v3_local`
- stderr:
  - `FileNotFoundError .../working/zjh_lerobot_v3_local/meta/info.json`

本波只读检查显示这个 candidate root 当前结构是：

- root
- `records/`
- `candidate_manifest.json`
- `episode_index.jsonl`

没有 `meta/` 目录。

### Diagnosis

这里和 raw baseline 不一样。`zjh_lerobot_v3_local` 不是受保护的原始数据源，而是 AutoVLA Data wave 生成出来、准备拿来比较和运行的 candidate artifact。它自己缺失 `meta/info.json`，说明它还 **没有被导出成 Isaac/LeRobot 可接受的数据集根**。

因此：

- 这个 candidate 不应该由 Training 用 proxy 去“遮羞”；
- 它首先需要 **Data-side structural repair**；
- 至少要补出标准 `meta/` 面：
  - `info.json`
  - `episodes.jsonl`
  - `tasks.jsonl`
  - `modality.json`
  - `stats.json`
  - 如果 runtime 继续要求，相应 `relative_stats.json` 也应明确策略。

换句话说，`zjh_lerobot_v3_local` 目前的问题不是“桥需要小适配”，而是 candidate 本身还不是一个 LeRobot-compatible root。

## 5. Recommended Minimal Training Repair Scope, If Any

### Recommended scope

若后续要给 Training 一个跟进修复波，最窄可接受范围应是：

1. **保持 `candidate_store_root` 为公共 config 字段**
2. 新增一个 **可选、task-local、raw-only compatibility staging layer**
   - 落在 `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
   - 只针对 raw baseline 这种只读原始数据源
3. 由 Training bridge 在 compute 前：
   - 读取 Data 提供的 metadata inputs；
   - 组装 compatibility root；
   - 将 `--dataset-path` 指向 compatibility root，而不是直接指向 raw root。
4. 产出一个 AutoVLA-owned compatibility manifest，记录：
   - source root
   - generated compatibility root
   - copied/symlinked metadata files
   - claim boundary

### Not recommended

不建议的 Training scope：

- 不要让 Training 为 `zjh_lerobot_v3_local` 生成完整 LeRobot `meta/` 语义
- 不要让 Training 直接解析 records 再推断 `episodes.jsonl`
- 不要让 Training 自己定义 `modality.json` 内容
- 不要把 raw 和 generated candidates 都统一塞进一个“万能 proxy”，这样会把 Data contract defect 隐藏掉

## 6. Recommended Data-vs-Training Boundary

### Data-owned fixes

以下修复必须保持 Data-owned：

- `zjh_lerobot_v3_local` 生成物本身的 LeRobot structural completeness
- `meta/info.json`
- `meta/episodes.jsonl`
- `meta/tasks.jsonl`
- `meta/modality.json`
- `meta/stats.json`
- candidate 对 action/state/video schema 的 authoritative 定义
- raw baseline 若要导出到兼容 metadata，metadata 内容本身的 authoritative generation

### Training-owned fixes

Training 只应拥有以下职责：

- 保持 `bridge-run` / wrapper / plan / manifest surface 稳定
- 在 raw baseline 场景下，若 Data 已提供 authoritative metadata inputs，则在 `runs/tmp/**` 下做 task-local compatibility staging
- 把最终可运行的 dataset root 交给 Isaac
- 记录 compatibility root provenance 和 bounded claim boundary

### Why this split is important

如果 Training 开始替 Data 发明 `info.json` / `episodes.jsonl` / `modality.json`，那后面任何“训练跑通”都无法区分：

- 是 Data candidate 真正确实可用；
- 还是 Training 在本地偷偷修了另一个 dataset surface。

这会直接破坏 bakeoff 的可解释性。

## 7. Whether A Task-Local Compatibility Proxy Is Acceptable

### Raw baseline

可接受，但要满足全部条件：

- 仅限 `runs/tmp/**`
- 仅限 raw baseline 这类 immutable source root
- 只做 compatibility staging，不改源数据
- 只使用 Data-authoritative metadata
- report/manifest 明确记录 proxy 是 compatibility layer，不是 candidate 自身结构修复

### `zjh_lerobot_v3_local`

当前不接受作为主要修复路径。

原因很简单：这个 candidate 本来就是 Data 生成的比较对象。如果它缺少 `meta/info.json`，那问题在 candidate artifact 本身，而不是在 Training bridge。Training proxy 会把一个 Data structural defect 伪装成 bridge adaptation，后续结果不干净。

## 8. Final Recommendation

1. **保持当前 public surface**
   - `bridge-run -> --dataset-path candidate_store_root` 仍然正确
2. **raw baseline**
   - 允许后续一个很窄的 Training task-local compatibility proxy
   - 但前提是 Data 提供 authoritative metadata payload/contract
3. **`zjh_lerobot_v3_local`**
   - 先做 Data-side structural repair
   - 让 candidate 自己成为 Isaac-acceptable root
4. **不要把 Data defects 隐藏进万能 Training proxy**

## 9. DevSpace MCP Compliance

- DevSpace MCP used: no

## 10. Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

`PASS_PLAN`
