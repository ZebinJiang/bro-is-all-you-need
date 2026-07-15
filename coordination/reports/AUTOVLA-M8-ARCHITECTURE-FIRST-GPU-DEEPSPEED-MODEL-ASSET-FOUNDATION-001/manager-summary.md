# AUTOVLA-M8 Manager Summary

## Decision

`PARTIAL_GPU_DEEPSPEED_ASSET_FOUNDATION_DRAFT_PUBLISHED`

The architecture and publication safety surface is coherent and published for
review, but the task does not meet the packet's architecture-complete runtime
matrix. Job `3167` stopped before CUDA model/tensor allocation on official
relative-action statistics shaped `[T,D]`; DDP, DeepSpeed ZeRO-1/2/3,
cross-node, and bounded checkpoint runtime targets were therefore not executed.

## Stack And Publication

- PR #33 started at `b24c3d6e914ce24e6698b693c8d5ba577a001f28` and was merged by merge commit.
- Recorded command-equivalent: `gh pr merge 33 --merge --match-head-commit b24c3d6e914ce24e6698b693c8d5ba577a001f28`. The canonical evidence retains the merge result rather than a terminal transcript.
- PR #33 merge SHA: `b73630b8123728906bab84fb95b11812faec904b`; parents: `be841be388018166637ff6f952772141299237c1` and `b24c3d6e914ce24e6698b693c8d5ba577a001f28`. No squash, rebase, or branch deletion occurred.
- PR #30 remains `OPEN`, `DRAFT`, unmerged into `main`, base `main`, head `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff` at `b73630b8123728906bab84fb95b11812faec904b`.
- M8 branch: `dev/feat-autovla-architecture-deepspeed-model-assets`.
- Product publication commit: `01af741cae14f9bf171438d3bc043ead927c3e09`.
- Draft PR: [#34](https://github.com/ZebinJiang/bro-is-all-you-need/pull/34), base `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`, head `dev/feat-autovla-architecture-deepspeed-model-assets`, `OPEN`, `DRAFT`, unmerged.
- Exact product head was verified live at `01af741cae14f9bf171438d3bc043ead927c3e09`. The later control-plane closure commit changes only this task card, state/index, and summary; the ignored full summary records the final live PR head after that push.
- Local no-renames publication manifest: 171 paths. GitHub's rename-aware PR count: 169 files.

## Governance And Routing

- Architecture-first governance is installed in the active root and coordination chain. Remote CI, CPU model runtime, FSDP/FSDP2, repeated parity, broad repeated validation, and backend selection are not Draft architecture gates.
- The previous baseline was `CORE_FRAMEWORK_ARCHITECTURE: SUBSTANTIALLY_ESTABLISHED`, `PRODUCTION_DISTRIBUTED_ARCHITECTURE: REQUIRES_DEEPSPEED_REDESIGN`, and `MODEL_ASSET_LIFECYCLE: NOT_YET_CANONICAL`.
- The user override routed ordinary Owner/worker implementation and validation to `gpt-5.6-sol / medium`; President Manager and non-President Manager-facing returns used `gpt-5.6-sol / max`.
- `max` was an explicit user override and was preserved as a distinct value, not aliased to `xhigh`.
- Five final Owner scopes ran once: Architecture/Packaging, Training/Distributed, Model/Assets, Data/Configuration, and Quality/Security/Product/Docs. Their findings were deduplicated into one ledger.
- Exactly one consolidated repair writer ran, followed by mapped validation and publication scans. No Owner re-review followed the repair.
- Four accidental duplicate persistent-Owner dispatches were interrupted and recorded as superseded; no persistent Owner was archived or replaced. All task-specific short-lived agents were collected and closed; no parallel source or Git writes occurred.
- DevSpace MCP was not used by Manager, Owners, workers, validators, or evidence.

## Canonical Architecture

```text
autovla.cli.train
  -> layered ExperimentConfig and registries
  -> ModelAssetStore -> GR00T N1D6 factory/checkpoint mapper
  -> TrainingTopology -> Data PartitionContext -> DataModule
  -> TrainingStrategy -> PreparedTrainingSession
  -> TrainingEngine -> CheckpointManager and telemetry

profiles:
  model-gr00t-n1d6  = Torch + Transformers + safetensors + WebDataset
  training-deepspeed = model profile requirements + DeepSpeed 0.19.2
  asset-acquisition = explicit huggingface_hub-only acquisition surface
```

- There is one `TrainingEngine`; it owns loop ordering, state progression, callback timing, and checkpoint cadence. Strategies own device/distributed preparation and return one `PreparedTrainingSession`, preventing duplicate optimizer/backward/step ownership.
- `single_gpu` is the native one-rank CUDA/BF16 strategy.
- DDP owns NCCL process-group setup, model wrapping, collective checkpoint participation, and transactional rollback that preserves pre-existing groups.
- One typed DeepSpeed strategy integrates official `deepspeed.initialize`, engine `backward`/`step`, and engine checkpoint APIs. Version: `0.19.2`, isolated to `training-deepspeed`.
- ZeRO-1 and ZeRO-2 use direct model construction, then DeepSpeed preparation. CPU/NVMe offload is rejected.
- ZeRO-3 uses a strategy-owned construction request under `deepspeed.zero.Init` before optimizer creation and `deepspeed.initialize`; full runtime/checkpoint memory proof remains deferred.
- Active topology presets cover single GPU, same-node DDP, same-node ZeRO-1/2/3, cross-node DDP, and cross-node ZeRO-3 with direct/torchrun/Slurm parsing and fail-closed rank identities.
- `CheckpointManager` coordinates logical manifests and completion state. Native/DDP sessions use the native backend; DeepSpeed sessions require all-rank official engine save/load APIs. Base model assets and run checkpoints have separate provenance and roots.

## Removed Active Surfaces

- FSDP/FSDP2 was removed from active presets, packaged resources, registry choices, launch matrix, environment requirements, and acceptance policy. Historical reports and compatibility-only symbols remain history, not production support.
- CPU model/training runtime and `local_debug` as an installed training default were removed. `autovla-train` now requires an explicit config; CPU remains allowed only for lightweight metadata/static work.
- DDP and DeepSpeed are BF16-only; DeepSpeed requires `bf16.enabled=true` and `fp16.enabled=false`.

## Assets And Model Integration

- Canonical model root: `/home/cz-jzb/workspace/vla-flywheel/base_model`.
- `.gitignore`, package/Pyright exclusion, explicit staging pathspecs, and `scripts/quality/check_staged_model_assets.py` prevent model assets, weights, checkpoints, tokenizers, caches, datasets, or run outputs from entering the PR.
- Existing base-model inventory was read without destructive mutation. The verified local `gr00t_n1d6` asset revision is `d0814e7ecb19202e7c8468b46098b0b7ef3a6d61`, manifest identity `a44b62e1217f603cbf5fc423c7f1b5c204e569ed97670cfb12736b166e9940ed`.
- Official Isaac-GR00T source is pinned to `5dc80c4afd726b34faad1d8f7e007a13b34e4c88` (`n1.6.1-release`) under `LicenseRef-NVIDIA-Isaac-GR00T-N1D6`, with non-commercial and redistribution constraints recorded.
- Acquisition used an offline local-provider copy with atomic publication; no network download occurred. Training is offline and cannot auto-download.
- The checkpoint mapper supports local manifest discovery, exactly-one-format selection, safetensors or bounded `weights_only=True` legacy loading, wrapper normalization, collision/shape rejection, strictness modes, and provenance hashes. Real successful model construction is still blocked before CUDA by `[T,D]` statistics handling.
- Eagle source responsibilities are mapped, but no complete authorized Eagle asset inventory exists. Production Eagle construction therefore fails closed before file reads; no Eagle runtime claim is made.
- AutoVLA owns config, processor, model factory, training strategy/session, checkpoint mapping, and runtime composition. Upstream GR00T runtime, trainer, launcher, server/client, datasets, remote-code dispatch, and whole-tree vendoring were not adopted.

## Reference Reuse Decision

- NVIDIA Isaac-GR00T: isolated adapted Eagle/DiT/embodiment regions, metadata adaptation, and clean contract reimplementation; exact notices and derivative headers are retained.
- DeepSpeed: official public API integration only; no DeepSpeed runtime source copied.
- WebDataset: lazy public API integration; LeRobot: local format target only.
- StarVLA, dexbotic, and FluxVLA remain historical inspiration/format references where recorded; no whole source tree was added.
- No model weights, tokenizer assets, fetched GR00T/Eagle bundle, upstream trainer, deployment stack, remote code, or universal model-zoo environment was adopted.
- Dependency impact is limited to explicit narrow profiles and lockfiles. The two runtime lock/fingerprint pairs are recorded in `envs/PROFILE_MATRIX.md`; no global/system environment was changed.

## Runtime Evidence And Limits

- Job `3163`: failed on unknown `training.max_steps`; one bounded source repair corrected sparse override ordering.
- Job `3167`: one A100, 8 CPUs, 64 GiB; configuration and the official local asset verified. It then raised `UnsupportedOfficialRelativeStatisticsError` because official relative-action statistics are `[T,D]` while the accepted normalization path is one-dimensional.
- The stop was before CUDA model/tensor allocation, forward, loss, backward, optimizer step, metrics, or checkpoint.
- Same-node DDP: not run. ZeRO-1/2/3: not run. Cross-node DDP/ZeRO-3: not run. Bounded checkpoint save/resume: not run.
- The remaining matrix is explicitly runtime-deferred. There is no single-GPU training success, distributed success, checkpoint parity, throughput, numerical parity, model-quality, deployment, or long-training claim.
- `NO_BACKEND_WINNER` remains literal.

## Validation, Review, And Safety

- The sole consolidated repair closed ten accepted ledger items: CLI default, canonical asset root, transactional process-group cleanup, BF16-only distributed config, verified/fail-closed Eagle assets, ZeRO-3 construction boundary, truthful runtime/lock docs, AutoVLA source-map keys, strict product static checks, and publication hygiene.
- Mapped repair validation passed 143 tests with 4 optional-runtime skips; writer validation passed 165 tests with 4 skips. Black, Ruff, strict product Pyright (`0/0/0`), redirected compile, structured parse, CLI help, source contracts, and `git diff --check` passed.
- Publication scans passed: exact staged path equality, whitespace/conflict markers, secret/token/private-endpoint patterns, model-asset policy, forbidden paths, artifacts/generated binaries/caches, files over 50 MiB, large text diffs, dependency/lock visibility, and license/notice/source-map consistency.
- Exactly five ignored architecture documents were force-added by exact pathspec; no other ignored path was staged. Optional gitleaks was not installed and was not added.
- The final Owner findings were all addressed by the one repair pass. The known `[T,D]` runtime limitation was intentionally deferred rather than converted into an unlimited repair loop.

## Rollback And Next Action

- No rollback, branch deletion, merge, ready transition, force push, direct-main push, or root-checkout mutation was performed.
- An authorized rollback should use non-destructive `git revert` on the control-plane closure commit first and product commit `01af741cae14f9bf171438d3bc043ead927c3e09` second. Closing PR #34 or deleting its branch requires separate authorization. Do not remove `/home/cz-jzb/workspace/vla-flywheel/base_model` as part of code rollback.
- Recommended next milestone: a bounded GR00T relative-statistics/runtime follow-up that implements shape-correct `[T,D]` normalization, then retries single-GPU before any serial DDP/ZeRO/cross-node matrix. Verified Eagle asset registration requires a separate license/asset authorization.
- Stop here for user/ChatGPT review of Draft PR #34. Do not merge, mark ready, start CI repair, benchmark, long training, model-quality evaluation, or another completion audit automatically.
