# AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001 Model Owner Plan Gate

## Workspace Verification

- Role: 40-OWNER · Model
- Stage: Wave 1 read-only plan gate
- Dispatch thinking mode recorded: thinking=xhigh
- thinking=max used: no
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-m3-dataloader-perf-harness`
- branch: `dev/feat-autovla-m3-dataloader-perf-harness`
- HEAD: `69c371e5861dccb6d374f8c1e155b55304a1f927`
- status: `## dev/feat-autovla-m3-dataloader-perf-harness...origin/dev/feat-autovla-m3-dataloader-perf-harness`
- workspace_check: PASS

## Evidence Reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `autovla/dataloader/perf/config.py`
- `autovla/dataloader/perf/benchmark.py`
- `autovla/dataloader/perf/metrics.py`
- `autovla/dataloader/perf/report.py`
- `autovla/dataloader/perf/MODULE.md`
- `tests/dataloader/test_perf_harness.py`
- `docs/architecture/DATALOADER_PERFORMANCE_HARNESS.md`
- `docs/architecture/FAST_TRAINING_VIEW.md`
- `autovla/dataloader/contracts.py`
- `autovla/dataloader/collate.py`
- `autovla/training/adapter.py`
- `autovla/training/testing.py`
- `tests/meta/test_m3_zjh_gr00t_readiness_policy.py`

Task-card/spec note:

- No exact `AUTOVLA-M3-PFS-TRAINING-STORE-BUILDER-001` task card or task-local spec file was found under `coordination/tasks/**` or `runs/tmp/**` during targeted lookup.
- This review therefore uses the dispatch plus current Fast Training View and dataloader perf-harness docs as the available plan/spec evidence.

## Model Boundary Assessment

APPROVE_PLAN.

The PFS training-store builder can proceed from Model perspective if it remains a data/cache preparation surface and does not introduce a model runtime surface. The existing perf harness already records `model_load`, `checkpoint_read`, `real_training`, `hf_network`, and `wandb_network` as false external effects, and the current AutoVLA training adapter already maps `CollatedBatch` into `ModelInput` without requiring new model contracts.

## Required No-Model Runtime Rules

The builder must not:

- instantiate, import, or load a real model;
- construct or load a tokenizer;
- read, probe, or download checkpoint/model weights;
- add Hugging Face, W&B, endpoint, robot, GPU/CUDA, Slurm submission, or real training behavior;
- add model-family compatibility claims to the store manifest;
- add `genesisvla` compatibility paths or aliases;
- add dependency changes for model/tokenizer runtimes.

If `model_registry_key` appears, it should be manifest metadata only and must not trigger registry lookup, adapter construction, or compatibility validation.

## Required Store Semantics For Later Model Handoff

The v0 `.npz`/`.jsonl` store is acceptable if it preserves the existing dataloader/model handoff semantics:

- actions are stored as padded numeric arrays with shape `[N,H,D]` or shard-local `[S,H,D]`;
- `action_mask` is stored as strict bool with the exact same shape as actions;
- per-sample `action_horizon` and `action_dim` are stored so padded regions are unambiguous;
- state is stored as numeric arrays with explicit shape/dtype metadata;
- language remains UTF-8 text or stable language keys in `.jsonl`, not tokenizer IDs unless a future tokenizer-specific task supplies a tokenizer fingerprint and policy;
- sample provenance is preserved with dataset/episode/frame/sample identifiers and source path or logical ref;
- dataset, transform, and statistics fingerprints are copied into the manifest;
- action normalization status is explicit, including whether actions are normalized and which statistics fingerprint applies;
- robot tag, task/language key, and modality names are preserved for future validation;
- shard ordering and deterministic sampler metadata are recorded without requiring a model contract change.

The store should be able to reconstruct an equivalent `CollatedBatch` and then use the existing `collated_batch_to_model_input()` path. Model should not need a new `ModelInput` schema for this v0 builder.

## `.npz` / `.jsonl` Model-Boundary Risks

P0 risks to guard:

- Do not store language or nested metadata as NumPy object arrays. Use `.jsonl` for strings and JSON metadata.
- Do not allow numeric or string coercion for `action_mask`; it must remain bool.
- Do not drop `action_horizon` / `action_dim`, or padded action loss will become ambiguous.
- Do not mix normalized and physical actions in one store without explicit per-store or per-shard normalization metadata.
- Do not store checkpoint URI/path or model weight provenance in the training-store manifest except as an explicit unsupported/absent field.
- Do not advertise support for GR00T, PI, OpenVLA, Qwen, or any real model family based only on the presence of this store.

P1 risks to document/test:

- Preserve sample order determinism and shard ordering for repeatable runner tests.
- Include enough provenance to trace each stored sample back to source metadata without reading media/checkpoints.
- Keep `.jsonl` records bounded and JSON-safe; avoid arbitrary Python object serialization.
- Version the store schema and include migration policy before multiple variants exist.

## Acceptance Criteria For Data/Training Implementation

From Model Owner perspective, the future implementation should be accepted only if:

- focused tests prove `action_mask` dtype is bool and shape equals action array shape;
- tests cover padded actions with variable horizon/action dim;
- tests prove language metadata is JSONL text/key metadata, not tokenizer output;
- tests prove no model/checkpoint/tokenizer import/load/download path is called;
- manifest asserts external effects are false for model load, checkpoint read, tokenizer load, HF/W&B/network, GPU/CUDA, and real training;
- store metadata can reconstruct the existing `CollatedBatch` and pass through `collated_batch_to_model_input()` without changing `ModelInput`, `FrameworkProtocol`, or `FrameworkOutput`;
- docs explicitly describe this as a PFS/Fast Training View data store, not a model-compatible checkpoint or model-specific dataset format.

## DevSpace MCP Compliance

- DevSpace MCP used: no
- `vla-flywheel-devspace` used: no
- MCP connector / `open_workspace` / MCP read/write/edit/bash used: no

## Subagent Ledger

- Child subagents used: none
- Retired: yes

## Conclusion

APPROVE_PLAN
