# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Data Diagnose Wave 7

Role: `30-OWNER · Data`

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`

## 2. Raw Baseline Diagnosis (`zjh_lerobot_v21_raw`)

### Conclusion

The minimal safe repair is a **task-local compatibility proxy root**. It is **not** impossible, and it does **not** require mutating the read-only source dataset.

### Evidence

The read-only source dataset already contains the underlying content Isaac expects for episode loading:

- `data/chunk-000/**`
- `videos/chunk-000/**`
- `meta/info.json`
- `meta/stats.json`
- `meta/tasks.jsonl`

Key source metadata from `meta/info.json` is already LeRobot-like:

- `data_path: data/chunk-{episode_chunk:03d}/episode_{episode_index:06d}.parquet`
- `video_path: videos/chunk-{episode_chunk:03d}/{video_key}/episode_{episode_index:06d}.mp4`
- `codebase_version: v2.1`

Wave 6 compute showed the raw telemetry failure is specifically:

- missing `meta/modality.json`

Isaac GR00T’s LeRobot validation surface requires the standard meta directory and specifically checks:

- `meta/info.json`
- `meta/episodes.jsonl`
- `meta/tasks.jsonl`
- `meta/modality.json`
- `meta/stats.json`

This requirement is explicit in:

- `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/configs/finetune_with_val_config.py`
- `/home/cz-jzb/workspace/Isaac-GR00T17/gr00t/data/dataset/lerobot_episode_loader.py`

So the raw source is not fundamentally incompatible. It is missing a GR00T-consumable metadata surface.

### Minimal Safe Repair Choice

Recommended: create a **task-local compatibility proxy root** that:

1. preserves the source dataset as read-only;
2. reuses the existing raw `data/` and `videos/` content;
3. materializes the missing GR00T-required metadata files under a proxy `meta/`;
4. avoids rewriting or “fixing” the immutable source tree itself.

This is narrower than creating a reusable rebuilt working artifact for raw, because the underlying raw content already exists and the gap is at the metadata compatibility layer.

## 3. `zjh_lerobot_v3_local` Diagnosis

### Conclusion

`zjh_lerobot_v3_local` is **not** merely missing metadata files. Its current artifact layout is **structurally incompatible** with the Isaac GR00T LeRobot loader even if the missing metadata files were added.

### Evidence

The current generated candidate root contains:

- `candidate_manifest.json`
- `sample_index.jsonl`
- `episode_index.jsonl`
- `records/sample-*.json`

Its manifest explicitly says:

- `format_contract: lerobot_v3_local_json_index_v1`
- `dependency_mode: autovla_owned_local_v3_style_no_upstream_package`

The current builder (`autovla/dataloader/stores/lerobot_v3_builder.py`) writes JSON record files plus JSONL indices only. The current reader (`autovla/dataloader/stores/lerobot_v3_reader.py`) reads those JSON record files directly.

By contrast, Isaac’s `LeRobotEpisodeLoader` does **not** read `records/sample-*.json` or `sample_index.jsonl`. It requires:

1. `meta/info.json`, `meta/episodes.jsonl`, `meta/tasks.jsonl`, `meta/modality.json`, `meta/stats.json`;
2. `info.json` fields such as `data_path` and `video_path`;
3. actual episode parquet files at `dataset_path / data_path_pattern.format(...)`;
4. actual video files at `dataset_path / video_path_pattern.format(...)`.

The loader path is hard-wired to:

- load parquet via `pd.read_parquet(...)`
- load video via `video_path_pattern` + `modality.json`

So adding only `meta/info.json` would not make the current `zjh_lerobot_v3_local` artifact consumable by Isaac. The runtime would simply fail later on missing parquet/video layout.

## 4. Exact Missing Files And Why They Matter

### Raw baseline (`zjh_lerobot_v21_raw`)

Required GR00T/Isaac files:

- `meta/info.json`
  - already present
  - defines `data_path`, `video_path`, feature schema, chunk sizing
- `meta/episodes.jsonl`
  - missing
  - required so Isaac can enumerate episodes and compute per-episode lengths
- `meta/tasks.jsonl`
  - already present
  - required for task text mapping
- `meta/modality.json`
  - missing
  - required for modality structure and camera key mapping
- `meta/stats.json`
  - already present
  - required by Isaac loader for statistics loading

Important note:

- root-level `metadata.json` exists, but Isaac does not look for it in place of `meta/modality.json` or `meta/episodes.jsonl`

### `zjh_lerobot_v3_local`

Required GR00T/Isaac metadata files:

- `meta/info.json`
- `meta/episodes.jsonl`
- `meta/tasks.jsonl`
- `meta/modality.json`
- `meta/stats.json`

All of the above are missing from the current candidate root.

But metadata alone is still insufficient. The Isaac loader also expects:

- `data/chunk-*/episode_*.parquet`
- `videos/chunk-*/<video_key>/episode_*.mp4`

The current `records/sample-*.json` layout does not satisfy that contract.

## 5. Structural Compatibility Verdict

- `zjh_lerobot_v21_raw`: **compatible after metadata-surface repair**
- `zjh_lerobot_v3_local`: **not structurally compatible in current form**

Why:

- raw already has the underlying parquet/video content and most of the meta surface;
- `zjh_lerobot_v3_local` is a local JSON-record artifact for AutoVLA benchmarking, not a GR00T/Isaac LeRobot dataset root.

## 6. Recommended Minimal Data Repair Scope

### Raw baseline repair scope

Narrowest safe Data scope:

- generate a task-local compatibility proxy root
- write only:
  - synthesized `meta/episodes.jsonl`
  - synthesized `meta/modality.json`
  - copied or referenced compatible `meta/info.json`, `meta/tasks.jsonl`, `meta/stats.json`
- keep the source dataset under `datasets/readonly/**` untouched

This can live under a task-local ignored path rather than rewriting the source root.

### `zjh_lerobot_v3_local` repair scope

Narrowest meaningful Data scope is broader than metadata patching. It must include:

1. builder-side source changes for the candidate artifact writer;
2. regeneration of the candidate root under approved working/task-local output;
3. emission of a real Isaac-consumable LeRobot-style surface:
   - standard `meta/*.json*`
   - parquet episode files
   - video path layout compatible with `video_path`

If Data is not authorized to emit a true LeRobot-style derivative, then `zjh_lerobot_v3_local` should remain non-consumable for Isaac telemetry rather than being “repaired” with metadata-only cosmetics.

## 7. Recommended Handoff Boundary To Training

After Data-side repair, the following remains Training-owned:

1. bridge config selection and final dataset-root choice for telemetry;
2. GR00T modality-config interpretation and any embodiment-side key mapping decisions;
3. telemetry launch, runtime debugging, and model/runtime log triage;
4. any training-side interpretation of statistics, masking, batching, or loader performance;
5. any decision to proceed from telemetry dry-run into actual fine-tune or model-runtime claims.

Data should stop at:

- producing an Isaac-consumable dataset root or proxy root;
- proving the metadata/layout contract is valid;
- preserving read-only source boundaries and ignored generated artifacts.

## 8. DevSpace MCP Compliance

- DevSpace MCP used: no

## 9. Subagent Retirement Ledger

- child subagents used: none
- retired: yes

## Conclusion

`PASS_PLAN`

The raw baseline is repairable through a minimal task-local compatibility proxy root that leaves the read-only source untouched. The current `zjh_lerobot_v3_local` candidate is not just metadata-incomplete; its JSON-record artifact layout is structurally incompatible with Isaac’s LeRobot parquet/video loader and therefore requires a true candidate-side artifact rebuild, not a metadata-only patch.
