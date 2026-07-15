# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Training Bridge Plan Wave 2

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`: branch matched; worktree contained the active bakeoff write surfaces plus coordination state and untracked task artifacts.

## 2. Current Bridge Gap Summary

当前仓库已经具备两类相关但尚未连通的能力：

1. `autovla/training/telemetry/**` 已经提供了 metadata-only 的受控配置、遥测 schema、表格输出、Slurm 渲染面和显式缺失值语义，但它不会启动真实 GR00T 运行。
2. 外部 `Isaac-GR00T17` 已经具备真实 `GR00T-N1.6` 的本地 entrypoint、基座模型目录和真实 finetune 配置同步逻辑，但这些能力尚未通过 AutoVLA 受控边界接入。

当前缺口不是“能否定义更多 schema”，而是缺少一个最小而诚实的 AutoVLA-owned bridge，把以下三件事接起来：

- AutoVLA 侧受控 datastore candidate / 指纹 / 输出目录治理；
- Isaac-GR00T17 侧真实 200-step bounded runtime；
- AutoVLA 侧统一 run manifest / telemetry artifacts / README feed。

因此，后续写入波次不应继续把当前 telemetry package 伪装成“真实训练器”，也不应直接把 Isaac 代码 import 进 AutoVLA 训练主干。最小可信方案是一个受控的 wrapper/subprocess bridge。

## 3. Recommended Minimal Bridge Architecture

### Recommendation

最窄且可接受的桥接方案是：

- AutoVLA 新增一个 **distinct real-run bridge layer**；
- 该层由 AutoVLA 生成受控 config、manifest、wrapper argv、log 路径和 telemetry contract；
- 真实 200-step 运行通过 **generated governed wrapper/subprocess surface** 启动 `Isaac-GR00T17` 的 `launch_finetune_n1d6.py`；
- 不在 AutoVLA 内直接 import Isaac Python runtime 作为长期 contract。

### Why not direct import

不建议后续执行波次直接 import `Isaac-GR00T17` Python 的原因：

- Isaac 运行入口自带真实训练语义、分布式启动语义和 checkpoint-shape 同步语义，直接 import 会把 AutoVLA 训练 contract 和外部 repo 的实现细节强耦合。
- 直接 import 会模糊“AutoVLA 只是治理桥”和“AutoVLA 已原生支持 GR00T 训练”的边界。
- 受控 wrapper/subprocess 更容易记录 argv、env、log 路径、checkpoint/base-model provenance、退出状态和 bounded step envelope。

### Narrowest acceptable shape

后续最小桥建议分成三层：

1. **AutoVLA bridge config layer**
   - 验证 datastore candidate、fingerprints、base-model/checkpoint manifest、output root、step cap、offline policy。
2. **AutoVLA bridge launcher layer**
   - 只负责生成并调用 Isaac entrypoint 的 list-argv / wrapper；
   - 记录 Slurm command、Python executable、env guard、output/error paths；
   - 不在 login node 做 checkpoint/tokenizer/model load。
3. **AutoVLA bridge reporting layer**
   - 接收 Isaac bounded run 产生的 log / telemetry fragments；
   - 输出 AutoVLA 侧统一 JSON/CSV/Markdown/README-feed artifacts；
   - 对缺失指标继续显式标记 `missing` / `not_observed` / `not_parseable`。

## 4. Required Inputs From Data

后续真实 200-step 训练桥最少需要 Data/Compute 提供如下 candidate contract；没有这些输入，不应启动 real bounded run：

- `datastore_name`
  - 明确候选名称，例如 raw / lerobot_v3 / webdataset_native / robodm_style。
- `candidate_store_root`
  - 实际可运行的 candidate root path。
- `sample_window_manifest_path`
  - 共享 sample/window manifest 路径，保证各候选读到的是同一批 window。
- `sample_window_manifest_fingerprint`
  - manifest 指纹，用于 run manifest 和结果对比。
- `dataset_fingerprint`
- `transform_fingerprint`
- `statistics_fingerprint`
  - 三者必须显式独立携带，不能只塌缩成单一 config checksum。
- `window_count` / `episode_count` / `frame_count`
  - 供 README / dashboard 表格复用的基础计数。
- `action_horizon`
- `action_dim`
  - 必须与 GR00T runtime contract 对齐。
- `worker_count`
- `batch_size`
  - 必须是本次 200-step bounded run 的受控值，而不是历史 proxy 值。
- `dataloader_mode`
  - 说明该 candidate 是 map-style / iterable / streaming / shard-based 哪一类。
- `read_only_evidence_paths`
  - 供后续 report 引用的 local logs / metadata paths。

如果 Data 只能给出“候选名称”和“大致路径”，但不能给出共享 manifest 指纹与 shape 约束，Training 不应声称能做公平可比的 200-step run。

## 5. Required Inputs From Model

后续写入波次最少需要 Model 提供如下受控输入，且仍保持 fail-closed：

- `model_registry_key = "gr00t-n1d6"`
- `base_model_path`
  - 指向本地受控 `GR00T-N1.6-3B` 路径。
- `base_model_manifest_path`
  - 记录 `config.json`、`processor_config.json`、`statistics.json`、safetensors index 等元数据摘要。
- `base_model_license_notice`
  - 至少记录本地模型卡 / LICENSE 依据，避免后续结果报告隐含可再发布权利。
- `checkpoint_manifest_path`
  - 如果本波使用 base model only，也应显式写成 base-model manifest，而不是让桥层自动探测。
- `runtime_entrypoint_path`
  - 指向 `Isaac-GR00T17/gr00t/experiment/launch_finetune_n1d6.py` 或受控 wrapper。
- `runtime_python_executable`
  - 指向 Isaac 可运行环境，而不是裸 `python`。
- `embodiment_tag`
- `modality_config_path`
  - 若 runtime 需要。
- `shape_sync_policy`
  - 明确 checkpoint `config.json` 是否用于同步 `max_state_dim`、`max_action_dim`、`action_horizon` 等 shape-critical defaults。

若这些输入中任何一项需要通过“运行时自动发现”“从缓存猜测”或“远程下载”获得，则应 fail closed，并升级为后续用户/Manager 决策，不应在桥里偷偷补全。

## 6. Required Configuration Fields For The Later Write-Capable Training Wave

后续真实桥接写入波次应拥有一份独立 bridge config，至少包含：

- `run_id`
- `datastore_name`
- `candidate_store_root`
- `sample_window_manifest_path`
- `sample_window_manifest_fingerprint`
- `dataset_fingerprint`
- `transform_fingerprint`
- `statistics_fingerprint`
- `model_registry_key`
- `base_model_path`
- `base_model_manifest_path`
- `checkpoint_manifest_path`
- `isaac_project_root`
- `isaac_entrypoint_path`
- `python_executable`
- `env_profile`
- `output_root`
- `logs_root`
- `table_output_root`
- `max_steps`
- `save_checkpoint`
  - 默认应为受控禁用或极窄范围。
- `batch_size`
- `worker_count`
- `action_horizon`
- `action_dim`
- `embodiment_tag`
- `modality_config_path`
- `num_gpus`
- `master_port`
- `slurm_partition`
- `slurm_account`
- `slurm_qos`
  - 如需要。
- `cpus_per_task`
- `memory`
- `time_limit`
- `wandb_mode`
  - 必须 fail-closed 到 offline/disabled。
- `hf_offline`
  - 必须显式开启。
- `allow_network`
  - 必须为 `false`。
- `allow_checkpoint_download`
  - 必须为 `false`。
- `allow_tokenizer_load_on_login`
  - 必须为 `false`。
- `require_compute_node`
  - 必须为 `true`。

## 7. Required Emitted Artifacts And Tables

后续真实桥至少要产出以下 AutoVLA-owned artifacts；没有这些工件，不应视作 bakeoff evidence 完整：

### Run and provenance manifests

- `run_manifest.json`
  - 记录 run_id、candidate、step cap、env guards、entrypoint、argv、input fingerprints、output roots。
- `base_model_manifest.json`
  - 记录 base model / checkpoint provenance，不需要读取权重内容。
- `log_path_manifest.json`
  - 记录 stdout/stderr、scheduler logs、wrapper logs、telemetry file paths。

### Telemetry outputs

- `per_step_telemetry.json`
  - 每步 GPU / CPU / IO / data-wait proxy / step timing / loss availability。
- `aggregate_telemetry.json`
  - first/last/min/max/mean/p50/p95、missing counts、completion ratio、termination classification。
- `resume_or_checkpoint_status.json`
  - 即使本波不写 checkpoint，也要显式说明 `not_written` / `disabled_by_contract`。

### Table outputs

- `performance_summary.csv`
- `performance_summary.md`
- `performance_gate_table.md`
- `missing_telemetry_table.md`
- `performance_environment_table.md`
- `readme_feed_table.md` 或 README 可直接 include 的中间表源

### Classification outputs

- `run_classification.json`
  - `completed_200_steps` / `partial` / `blocked_model_assets` / `blocked_data_candidate` / `blocked_compute_env` 等。
- `forbidden_claims.md` 或等价 manifest field
  - 明确本次 bounded run 不能外推的结论。

## 8. Forbidden Claims Even After A Successful Bounded Run

即使后续 200-step bounded run 成功，也仍然禁止以下表述：

- “AutoVLA 已原生支持 GR00T-N1.6 训练”
- “该 candidate 已证明 fine-tune readiness”
- “该 bounded run 已证明 checkpoint compatibility”
- “该 bounded run 已证明 tokenizer / processor compatibility”
- “该 bounded run 已证明 model correctness”
- “该 bounded run 已证明 deployment / inference readiness”
- “该 candidate 已是最终 backend winner”
- “200-step telemetry 可直接代表长程生产训练性能”

允许的最强表述只能是：

- 在受控、离线、bounded 200-step envelope 下，某 candidate 与受控 Isaac-GR00T17 运行桥可以产出可比较 telemetry；
- 结果可作为后续 training hot-path / data backend / compute telemetry 决策输入；
- 结果不等于正式 fine-tune readiness。

## 9. Which Current Telemetry Pieces Can Be Reused, And Which Should Not

### Reuse directly

当前 `autovla/training/telemetry/**` 中，以下部分适合复用：

- config validation 的 fail-closed 风格
- `missing` / `not_observed` / `not_parseable` 的显式缺失语义
- per-step / aggregate JSON schema 组织方式
- Markdown / JSON / table reporting helper
- Slurm wrapper 渲染思路
- offline / no-W&B-online / no-HF-online guard fields

### Do not extend as-is into “real runtime”

以下部分不建议直接把当前 metadata-only 包强行扩成真实 GR00T runtime：

- `python -m autovla.training.telemetry run-governed`
  - 该名字和当前语义已经是 metadata-only / surface-only；继续扩展会混淆 dry telemetry 与 real runtime bridge。
- 当前 telemetry package 的顶层 contract
  - 它更像 bakeoff telemetry/reporting utility，而不是真实模型运行桥。

### Recommendation

更诚实的方式是：

- **保留当前 `autovla/training/telemetry/**` 作为 telemetry/reporting substrate**
- **后续新增 distinct real-run bridge**
  - 可以是 `autovla/training/telemetry/bridge_*` 子模块，或 `autovla/training/gr00t_bridge.py` / `autovla/training/gr00t_gpu200_bridge.py`
  - 该桥调用 Isaac entrypoint，但把 artifacts 统一落在 AutoVLA 治理面下

这样可以复用现有 telemetry schema，又不会误导后续读者以为 telemetry package 本身已经等于真实训练器。

## 10. DevSpace MCP Compliance

- DevSpace MCP used: no

## 11. Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## 12. Conclusion

`APPROVE_BRIDGE_PLAN`
