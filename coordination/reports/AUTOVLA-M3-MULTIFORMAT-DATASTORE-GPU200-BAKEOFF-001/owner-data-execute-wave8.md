# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Data Execute Wave 8

Role: `30-OWNER · Data`

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## 2. Files Changed

- `autovla/dataloader/stores/benchmark.py`
- `autovla/dataloader/stores/common.py`
- `autovla/dataloader/stores/lerobot_compat.py`
- `autovla/dataloader/stores/lerobot_v3_builder.py`
- `autovla/dataloader/stores/lerobot_v3_reader.py`
- `tests/dataloader/test_multiformat_datastore_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave8.md`

## 3. Exact Raw-Candidate Repair Shape

`zjh_lerobot_v21_raw` 继续保持 raw benchmark 读取语义不变，但 task-owned candidate root 已改成 Isaac-consumable compatibility root:

- root:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/zjh_lerobot_v21_raw`
- 写出完整 `meta/` surface:
  - `meta/info.json`
  - `meta/episodes.jsonl`
  - `meta/tasks.jsonl`
  - `meta/modality.json`
  - `meta/stats.json`
- `meta/info.json` 由 source `meta/info.json` 派生，按 bounded sample/window subset 回填:
  - `total_episodes`
  - `total_frames`
  - `total_tasks`
  - `total_videos`
  - `total_chunks`
  - `splits`
- `meta/episodes.jsonl` 为 Data-owned 非空生成，不再依赖 source root 缺失的文件。
- `meta/modality.json` 为 Data-owned black-rubber modality layout，和 Isaac/GR00T 所需 video/state/action/annotation contract 对齐。
- `data/` 与 `videos/` 通过 task-owned 相对符号链接安全引用只读 source 内容；未修改 `datasets/readonly/**`。
- 当 source fixture 缺失 `meta/stats.json` 时，兼容层会生成最小 fallback stats；真实只读源仍直接复用原 `stats.json`。

## 4. Exact `zjh_lerobot_v3_local` Repair Shape

`zjh_lerobot_v3_local` 已从 JSON-record-only layout 修成真实 LeRobot-compatible candidate root:

- root:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local`
- 写出完整 `meta/` surface:
  - `meta/info.json`
  - `meta/episodes.jsonl`
  - `meta/tasks.jsonl`
  - `meta/modality.json`
  - `meta/stats.json`
- 写出真实 `data/` 布局:
  - `data/chunk-*/episode_*.parquet`
- 写出真实 `videos/` 引用:
  - task-owned相对符号链接到 source `videos/`
- `sample_index.jsonl` 增加真实读取所需字段:
  - `episode_index`
  - `row_in_episode`
  - `data_path`
- `read_lerobot_v3_local_batches(...)` 不再读取 `records/*.json`；现在从 `sample_index.jsonl -> data_path -> parquet row` 重建 payload。
- `records/*.json` 保留为调试/辅助旁路，但已不是 benchmark/test 的必需消费面。
- `candidate_manifest.json` 的 `format_contract` 更新为 `lerobot_v3_local_isaac_compatible_v2`。

## 5. Focused Validation Commands And Results

### RED evidence

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
  - initial result: `2 failed, 6 passed`
  - failing tests:
    - `test_raw_candidate_root_should_emit_isaac_required_meta_surface`
    - `test_lerobot_v3_local_candidate_should_not_depend_on_records_json_only_layout`

### GREEN / final validation

- `PYTHONPYCACHEPREFIX=/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff/runs/tmp/pycache /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/stores/benchmark.py autovla/dataloader/stores/common.py autovla/dataloader/stores/lerobot_compat.py autovla/dataloader/stores/lerobot_v3_builder.py autovla/dataloader/stores/lerobot_v3_reader.py tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - PASS
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
  - PASS (`8 passed`)
- `runs/tmp/m1-tool-venv/bin/python -m ruff check autovla/dataloader/stores/benchmark.py autovla/dataloader/stores/lerobot_v3_builder.py autovla/dataloader/stores/lerobot_v3_reader.py autovla/dataloader/stores/lerobot_compat.py tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - PASS
- changed-file Black checks:
  - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores/benchmark.py`
  - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores/lerobot_v3_builder.py`
  - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores/lerobot_v3_reader.py`
  - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores/lerobot_compat.py`
  - `runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - PASS
- `runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/stores tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - PASS (`0 errors, 0 warnings, 0 informations`)
- `git diff --check`
  - PASS

## 6. Whether Reduced Benchmark Rerun Completed Locally

Yes.

Executed:

- `runs/tmp/m1-tool-venv/bin/python -m autovla.dataloader.stores run --config runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_reduced.yaml`

Result:

- command exit status: PASS
- updated output:
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.json`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.csv`
  - `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/load-benchmark.md`

Key rerun evidence:

- `zjh_lerobot_v21_raw`
  - status: `PASS`
  - candidate root: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/store-benchmark/zjh_lerobot_v21_raw`
  - `p50_ms`: `0.588633`
  - `p95_ms`: `0.696064`
  - `samples_per_second`: `432399.294316`
- `zjh_lerobot_v3_local`
  - status: `PASS`
  - candidate root: `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/working/zjh_lerobot_v3_local`
  - `p50_ms`: `10.78924`
  - `p95_ms`: `14.491`
  - `samples_per_second`: `23555.451561`

## 7. Residual Blocker For The Next Compute Wave

No remaining Data-scope blocker is visible after this wave.

The next compute wave should now rerun bounded Isaac telemetry against the repaired task-owned roots to confirm:

- raw compatibility root is accepted with generated `meta/modality.json` and non-empty `meta/episodes.jsonl`;
- `zjh_lerobot_v3_local` is accepted through its real `meta/ + parquet + videos` layout rather than the old JSON-record-only surface.

This wave did not run compute telemetry and does not claim training/runtime success beyond local datastore validation.

## 8. DevSpace MCP Compliance

- DevSpace MCP used: no

## 9. Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

`PASS`
