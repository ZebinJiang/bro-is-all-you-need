# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Training Execute Wave 3

## Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## Files Changed

- `autovla/training/telemetry/__init__.py`
- `autovla/training/telemetry/__main__.py`
- `autovla/training/telemetry/bridge_manifest.py`
- `autovla/training/telemetry/bridge_runtime.py`
- `autovla/training/telemetry/config.py`
- `autovla/training/telemetry/slurm.py`
- `configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
- `tests/training/test_gpu200_multiformat_telemetry.py`
- `docs/benchmarks/GR00T_GPU200_MULTIFORMAT_TELEMETRY.md`
- `docs/benchmarks/README.md`
- `README.md`

No writes were made to:

- `autovla/dataloader/stores/**`
- `requirements/**`
- `pyproject.toml`
- `Makefile`
- `datasets/readonly/**`
- `datasets/working/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

## Bridge Files Added/Updated

### Distinct bridge surface

本波新增了独立于 metadata-only `run-governed` 的真实桥接表面：

- `bridge_manifest.py`
  - 提供 AutoVLA-owned 本地 base-model provenance manifest writer。
- `bridge_runtime.py`
  - 提供 Isaac bounded run argv 渲染与后续 compute-node `bridge-run` 入口。
- `__main__.py`
  - 新增：
    - `validate-config`
    - `write-base-model-manifest`
    - `render-slurm`
    - `bridge-run`
  - 保留 `run-governed` 作为 metadata-only 遥测输出路径，不把它伪装成真实 Isaac launch。
- `slurm.py`
  - 从 metadata-only `run-governed` 渲染升级为 bridge-ready wrapper / plan surface。

### Public surface now available

- `python -m autovla.training.telemetry validate-config --config <path>`
- `python -m autovla.training.telemetry write-base-model-manifest --config <path>`
- `python -m autovla.training.telemetry render-slurm --config <path> --output-dir <path>`
- `python -m autovla.training.telemetry bridge-run --config <path>`

`bridge-run` 已存在为后续 compute 波次入口，但本波没有执行它。

## Config Fields Added/Changed

`configs/training/gr00t_n1d6_gpu200_multiformat.yaml` 现在是 honest bridge-ready surface，增加/显式化了以下字段：

- `model_registry_key`
- `candidate_store_root`
- `sample_window_manifest_path`
- `sample_window_manifest_fingerprint`
- `isaac_project_root`
- `isaac_entrypoint_path`
- `python_executable`
- `base_model_root`
- `base_model_manifest_path`
- `logs_root`
- `table_output_root`
- `num_gpus`
- `wandb_mode`
- `hf_hub_offline`
- `transformers_offline`
- `hf_datasets_offline`
- `allow_network`
- `allow_checkpoint_download`
- `require_compute_node`
- `embodiment_tag`
- `modality_config_path`
- `global_batch_size`
- `dataloader_num_workers`

关键合同约束：

- `max_steps` 必须为 `200`
- `num_gpus` 必须为 `1`
- `gres` 不允许为 `none`
- 离线字段必须 fail-closed：
  - `wandb_mode=offline|disabled`
  - `hf_hub_offline=true`
  - `transformers_offline=true`
  - `hf_datasets_offline=true`
  - `allow_network=false`
  - `allow_checkpoint_download=false`
  - `require_compute_node=true`

## Whether `gres: none` Was Removed

是。

- 旧 surface：`gres: none`
- 当前 surface：`gres: gpu:1`

因此当前配置已经表达真实 1-GPU 意图，而不是 metadata-only 假 GPU 合同。

## Exact Bridge Command / Wrapper Surfaces Now Available

### Rendered later real-run argv shape

桥接命令渲染到 Isaac `launch_finetune_n1d6.py`，最小 argv 现在包括：

- configured local `python_executable`
- configured local `isaac_entrypoint_path`
- `--base-model-path <base_model_root>`
- `--dataset-path <candidate_store_root>`
- `--embodiment-tag <embodiment_tag>`
- `--modality-config-path <modality_config_path>` when present
- `--num-gpus 1`
- `--output-dir <output_dir>`
- `--max-steps 200`
- `--global-batch-size <...>` when present
- `--dataloader-num-workers <...>` when present

### Wrapper / plan surface

`render-slurm` 现在生成 bridge-ready surface，而不是旧的 metadata-only wrapper：

- sbatch script invokes:
  - `python -m autovla.training.telemetry bridge-run --config "$1"`
- wrapper exports:
  - `WANDB_MODE=offline`
  - `HF_HUB_OFFLINE=1`
  - `TRANSFORMERS_OFFLINE=1`
  - `HF_DATASETS_OFFLINE=1`
- wrapper records real GPU intent:
  - `#SBATCH --gres=gpu:1`

生成的 plan JSON 为：

- `telemetry_bridge_plan.json`

并包含：

- `command_argv`
- `rendered_command`
- `isaac_entrypoint_path`
- `base_model_manifest_path`
- `checkpoint_manifest_path`
- `dataset/transform/statistics/sample_window` fingerprints
- `output_log_path`
- `error_log_path`
- offline env contract
- claim boundary and external-effect flags

## Exact Base-Model Manifest Surface Now Available

新增 AutoVLA-owned manifest：

- `base_model_manifest.json`

当前 schema：

- `schema_version`
- `task_id`
- `model_family_key`
- `model_registry_key`
- `support_status_at_launch`
- `source_repo_root`
- `source_repo_head`
- `base_model_root`
- `path_policy`
  - `read_only`
  - `local_only`
  - `no_download`
  - `no_cache_probe`
  - `no_mutation`
  - `hf_online`
- `required_files`
- `required_file_presence`
- `weight_inventory`
- `license_and_card`
- `runtime_offline_env`
- `claim_boundary`
  - `runnable_bounded_telemetry_only`
  - `checkpoint_correctness_validated`
  - `training_readiness_validated`
  - `model_compatibility_validated`
  - `tokenizer_processor_validated`

本 manifest 只做本地文件 presence / provenance inventory，不语义读取权重，不做 checkpoint correctness claim。

## Validation Commands And Results

### TDD evidence

- RED:
  - `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/training/test_gpu200_multiformat_telemetry.py -v`
  - initial failure:
    - `ImportError: cannot import name 'write_base_model_manifest' from 'autovla.training.telemetry'`
- GREEN:
  - same focused pytest command
  - result: `4 passed`

### Fresh validation evidence

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m autovla.training.telemetry validate-config --config configs/training/gr00t_n1d6_gpu200_multiformat.yaml`
  - PASS
  - emitted `model_runtime_status = bridge_ready_unverified`
  - confirmed `gres = gpu:1`
  - confirmed `num_gpus = 1`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/training/test_gpu200_multiformat_telemetry.py -v`
  - PASS (`4 passed`)
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
  - PASS
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/training/telemetry tests/training/test_gpu200_multiformat_telemetry.py`
  - PASS (`0 errors, 0 warnings, 0 informations`)
- `PYTHONPYCACHEPREFIX=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/pycache /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/training/telemetry/*.py tests/training/test_gpu200_multiformat_telemetry.py`
  - PASS
- `git diff --check`
  - PASS

### Black note

- directory/multi-file Black check again hung in this worktree
- packet-approved fallback was used:
  - file-by-file `black --check` across the touched training/test files
- final focused evidence:
  - all checked files passed after formatting `autovla/training/telemetry/bridge_runtime.py`

## Remaining Compute-Evidence Dependency

本波只完成了 implementation-only bridge surface，仍然明确缺少 compute evidence：

- 没有执行真实 GPU 作业
- 没有提交 Slurm 作业
- 没有执行 `bridge-run`
- 没有产出真实 candidate 200-step telemetry 数值
- 没有产出真实 bounded Isaac runtime logs

后续 Compute/HPC 波次仍需补：

1. 真实 compute allocation
2. 使用受控 bridge config 的 bounded 1-GPU `max_steps=200` 运行
3. 实际 base-model/checkpoint manifest path approval
4. 每个可运行 datastore candidate 的真实 telemetry outputs / logs / tables

因此当前状态只能到：

- `bridge_ready_unverified`
- `runnable_bounded_telemetry_only`

不能前推到 training readiness / checkpoint correctness / model compatibility validation。

## DevSpace MCP Compliance

- DevSpace MCP used: no

## Subagent Retirement Ledger

- child subagents used: none
- write-capable child subagents used: none
- no parallel source writes: yes
- retired: yes

## Conclusion

`PASS`
