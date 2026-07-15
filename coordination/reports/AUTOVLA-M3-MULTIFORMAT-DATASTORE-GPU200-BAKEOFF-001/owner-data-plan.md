# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Owner Data Plan

## Workspace Verification

- Role: `30-OWNER · Data`
- Mode: read-only planning
- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`

## Scope Read

- owner packet: `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-packets/data-plan.md`
- task card: `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- reuse candidates:
  - `autovla/dataloader/perf/bakeoff.py`
  - `autovla/dataloader/perf/benchmark.py`
  - `autovla/dataloader/perf/training_store.py`
  - `autovla/dataloader/perf/webdataset_streaming_store.py`
  - `autovla/dataloader/format_pipeline/contracts.py`
  - `autovla/dataloader/format_pipeline/pipeline.py`
  - `tests/dataloader/test_backend_bakeoff_dashboard.py`
  - `tests/dataloader/test_format_native_loader_bakeoff.py`

## Data Assessment

### 1. Deterministic shared sample/window manifest

`autovla/dataloader/perf/bakeoff.py` already contains a strong reusable seed for this task in `build_zjh_subset_window_manifest(...)`:

- deterministic `training_window_ids`
- explicit `dataset_fingerprint`
- explicit `selected_sample_count` / `selected_episode_count`
- fixed `worker_count`
- explicit raw ZJH field mapping
- stable manifest fingerprint via canonical payload hashing

For this GPU200 bakeoff, Data recommends reusing the same manifest concept but lifting it into a task-neutral store-facing contract under the new task scope, rather than directly coupling new logic to old bakeoff task ids or old markdown writers.

Minimum manifest fields for this task should be:

- `schema_version`
- `dataset_uri`
- `dataset_fingerprint`
- `source_sample_count`
- `source_episode_count`
- `selected_sample_count`
- `selected_episode_count`
- `training_window_ids`
- `payload_field_specs`
- `same_subset_required=true`
- `worker_count`
- `seed`
- `fingerprint`

### 2. Same-sample fairness across raw/v3/WebDataset/RoboDM-style

Data approves a single shared fairness rule:

- one manifest is created once from the read-only ZJH source;
- every candidate must consume the exact same ordered `training_window_ids`;
- candidates may differ in storage/layout/reader path only;
- candidates must not re-sample, reshuffle, or infer their own subset independently.

Practical implication:

- `raw`: reads directly from the source dataset using the shared manifest;
- `lerobot_v3`: may only be benchmarked if a converted/store representation can prove one-to-one preservation of the same window ids;
- `webdataset`: shard writer and reader must preserve manifest order or record an explicit index mapping back to shared window ids;
- `robodm_style`: owned container/index prototype must store `training_window_id`, `sample_id`, and `episode_id` explicitly.

This means the fairness contract should live above candidate-specific writers/readers. Reusing only per-candidate benchmark helpers without a shared manifest layer would be too fragile.

### 3. Source read-only guarantee

The task card boundary is correct and should remain hard:

- never mutate `datasets/readonly/**`;
- generated stores belong only under task-approved working/output roots;
- no symlink-only candidate outputs;
- no candidate may use the source dataset as its output root.

Existing `FormatPipelineConfig` path guards already enforce key parts of this policy:

- `working_root` must not be inside source dataset
- `output_dir` must not be inside source dataset

Data recommends carrying this exact fail-closed pattern into the new multiformat datastore config and store builders.

### 4. Reuse from existing perf/format_pipeline code

Safe reuse without old-task overfitting:

1. Reuse concepts directly
- subset/window manifest fingerprinting from `bakeoff.py`
- path containment and output-root protections from `format_pipeline/contracts.py`
- artifact ledger style from `bakeoff.py`
- build/read report split from `training_store.py` and `webdataset_streaming_store.py`

2. Reuse implementation patterns selectively
- shared candidate manifest/index/checksum layout
- explicit external-effects false fields
- deterministic shard naming
- bounded `max_episodes=4`, `max_samples=512`, `seed=11`

3. Do not overfit
- do not hardwire old task ids
- do not reuse old final-decision strings
- do not couple new candidate rows to older README/dashboard adjudication semantics
- do not import old benchmark table wording as if this task were only a report refresh

Recommended implementation direction is a new neutral datastore layer under the task’s allowed write scope, with old `perf/format_pipeline` code used as reference and utility source, not as the final task-specific public contract.

### 5. Exact dependency-free fallback routes

Data’s recommended fallback matrix is:

#### raw
- dependency-free runnable route exists now
- can use shared manifest plus bounded source-reader path
- remains the fallback baseline

#### robodm_style
- dependency-free owned prototype route exists now in principle
- can reuse AutoVLA-native container/index ideas from existing `robodm_style` format-pipeline path
- must stay explicitly `prototype_only`, not actual Robo-DM dependency support

#### webdataset
- primary comparable route is package-backed and should reuse existing `webdataset_streaming_store.py` / `format_pipeline.py` behavior if the dependency is already present in the governed project environment
- exact dependency-free fallback is only:
  - stdlib tar layout writer/validator
  - metadata/index/checksum verification
  - non-comparable placeholder row
- this fallback is useful for build/layout safety but is **not** a fair substitute for actual WebDataset streaming benchmark evidence

#### lerobot_v3
- exact dependency-free fallback is metadata-only blocked/not-run evidence
- no honest dependency-free comparable reader route is present in current repository surfaces
- if the milestone later requires runnable LeRobot v3 parity, that becomes a separate dependency/product decision

## Planning Recommendation

Data approves proceeding with the plan under these conditions:

1. The shared manifest is implemented first and treated as the sole fairness source.
2. Raw and RoboDM-style owned prototype may proceed on dependency-free paths.
3. WebDataset may proceed as a real comparable candidate only when the already-governed project environment exposes the package-backed route; otherwise it must degrade to a clearly non-comparable fallback row.
4. LeRobot v3 must remain explicit `NOT_RUN_DEPENDENCY_BLOCKED` unless a later approved dependency route is introduced.
5. Generated outputs remain outside `datasets/readonly/**` and outside git-tracked artifact paths.

## Residual Risks

- The existing reusable code spans several older task families; direct copy-forward would risk old-task wording and report semantics leaking into this bakeoff.
- A dependency-free WebDataset fallback can preserve layout semantics but not true streaming-comparable performance semantics.
- If Product/Architecture later require all four candidates to be runnable and numerically comparable with zero dependency delta, this Data plan would need a user-level dependency decision.

## Subagent Ledger

- child subagents used: none
- retired: yes

## Conclusion

APPROVE
