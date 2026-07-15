# M10 N1D6 checkpoint mapping repair W1

Conclusion: `PASS_SOURCE_REPAIR`

- worker: `M10-N1D6-CHECKPOINT-MAPPING-REPAIR-W1`
- isolated worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-n1d6-checkpoint-mapping-repair-w1`
- branch: `dev/m10-n1d6-checkpoint-mapping-repair-w1`
- base HEAD/current HEAD: `1f90b7509819b745f15e9f3ed8fba5e8228ce504`
- base tree manifest: `git_ls_tree_r_z_sha256_v1:6fcb3366483e997ce5512f6ab412b7715e3cf433e97bcf2d43932596758c5f79`
- commit SHA: `NOT_CREATED_HIGHER_LEVEL_RUNTIME_FORBIDS_COMMIT`
- safe_to_close: `true`

## Causal diagnosis

Job 3397 reached the pinned official model and local safetensors loader, then failed before data, forward, backward, optimizer, save/resume, or distributed execution. The exact receipt contained 356 missing keys, 388 unexpected keys, and one shape mismatch.

The full receipt lists and official index form a complete systematic correspondence:

- 4 timestep MLP keys used official `timestep_encoder.timestep_embedder.linear_{1,2}` names while the local module uses `time_encoder.linear{1,2}`.
- Every one of 32 blocks used official diffusers `to_q/to_k/to_v`, `to_out.0`, `ff.net.0.proj`, and `ff.net.2` names. Local PyTorch MHA needs split Q/K/V weights for the 16 even cross-attention blocks, packed Q/K/V weights for the 16 odd self-attention blocks, and packed Q/K/V bias for all blocks.
- Local `norm2` incorrectly used an adaptive norm. The pinned official source uses a non-affine LayerNorm before FFN, so the local model invented 64 `norm2.linear.{weight,bias}` parameters that cannot exist in the checkpoint.
- The pinned official action head constructs `position_embedding` from `max_seq_len=1024` and indexes only the current action sequence. Local construction incorrectly used `action_horizon=50`, causing the sole shape mismatch.
- Local timestep frequencies already used official cosine/sine ordering, but the denominator omitted official `downscale_freq_shift=1`; this was corrected from `half` to `half - 1`.

Static full-list reconciliation after the correction produced:

```text
receipt_missing=356
receipt_unexpected=388
receipt_shapes=1
removed_nonofficial_norm_parameters=64
mapped_targets=292
uncovered_expected=[]
extra_mapped=[]
position_shape_corrected=True
```

## Before/after examples

- `action_head.model.timestep_encoder.timestep_embedder.linear_1.weight` -> `action_head.model.time_encoder.linear1.weight`
- even cross block `to_q.weight`, `to_k.weight`, `to_v.weight` -> separate `q_proj_weight`, `k_proj_weight`, `v_proj_weight`
- odd self block Q/K/V weights -> one `in_proj_weight` concatenated in exact Q, K, V order
- all block Q/K/V biases -> one `in_proj_bias` concatenated in exact Q, K, V order
- `attn1.to_out.0.weight` -> `attn1.out_proj.weight`
- `ff.net.0.proj.weight` -> `ff.proj_in.weight`
- `ff.net.2.weight` -> `ff.proj_out.weight`
- `position_embedding.weight`: local expected `(50, 1536)` -> official `(1024, 1536)`

Incomplete Q/K/V groups and source-to-target collisions raise before loading. Non-optional missing, unexpected, and shape-mismatch keys remain fatal. No tensors are fabricated, resized, truncated, or silently dropped.

## Changed files

- `autovla/models/families/gr00t_n1d6/_nvidia/dit.py`
- `autovla/models/families/gr00t_n1d6/action_head.py`
- `autovla/models/families/gr00t_n1d6/checkpoint.py`
- `autovla/models/families/gr00t_n1d6/config.py`
- `tests/model/test_m10_gr00t_n1d6_checkpoint_mapping.py`
- this report
- ignored handoff under `runs/tmp/.../agents/m10-n1d6-checkpoint-mapping-repair-w1/handoff.yaml`

No shared assembly, assets, data/training, dependency lock, docs/configs, Slurm scripts, governance, root checkout, or `base_model` file was modified.

## Validation

- filewise Black 24.2.0: 5/5 passed, each file exit 0. The combined invocation hit the known Black shutdown timeout after reporting all five unchanged; filewise runs are authoritative.
- Ruff 0.15.17: passed on all five changed Python files.
- `python -m py_compile`: passed on all five changed Python files.
- focused pytest: `10 passed in 1.46s` for the new checkpoint mapping tests plus `test_m10_gr00t_n1d6_family.py`.
- exact receipt-list reconciliation: 292 mapped targets exactly cover all remaining expected keys after removal of 64 non-official norm parameters; no extras remain.
- `git diff --check`: passed.
- scope/status: only the five implementation/test files plus this authorized report are visible; index is empty and no staged artifact exists.
- suppression scan: no `Any`, `type: ignore`, `noqa`, `ignore_missing`, or `ignore_unexpected` added.
- strict project Pyright was attempted but is not viable in this worktree: `pyrightconfig.autovla.json` points to absent `envs/training-deepspeed/.venv`, so imports such as torch/numpy/pytest are unresolved and generate environment-wide unknown-type fallout. No suppression was added to mask this environment blocker.

No official model construction, official checkpoint load, CUDA, Slurm, network, install, data, forward/backward, or optimizer action was run in this repair worktree.

## Complexity and memory

- Key discovery and renaming: `O(K)` time and `O(K)` key metadata for a shard.
- Packed projections: `O(P)` tensor-copy time and `O(P)` transient space for packed Q/K/V elements. Even cross-attention weights are reused without copying; self-attention weights and all biases are concatenated exactly once per conversion pass.
- Temporary packed references are explicitly released after each shard audit/load pass, bounding added live space to the current shard's packed projections.
- Forward GPU utilization and distributed communication are unchanged. Checkpoint conversion adds local tensor concatenations only; it adds no synchronization or collectives.
- Existing loader behavior still audits before writing and then rereads shards for loading. This preserves fail-closed semantics at the cost of two sequential shard passes.

## Reference reuse decision

- considered: pinned `NVIDIA/Isaac-GR00T@5dc80c4afd726b34faad1d8f7e007a13b34e4c88`, official `gr00t/model/modules/dit.py`, official `gr00t/model/gr00t_n1d6/gr00t_n1d6.py`, and the canonical checkpoint index.
- reuse: no new third-party file or block was copied. Existing NVIDIA-adapted family file attribution and license header remain intact; the repair aligns the existing adaptation and adapter with pinned source evidence.
- license/dependency impact: no license, notice, or dependency change.
- residual risk: real 6.57 GB shard loading and full official state-dict equality require one follow-up A100 Slurm rerun; static/synthetic validation cannot prove runtime memory headroom or safetensors shard execution.

## Slurm requirement and next validation

No Slurm job was required or authorized for this source-only repair. The next owner stage should rerun the existing project wrapper on one A100 with the exact canonical local asset receipt, requiring strict zero missing/unexpected/shape mismatches before proceeding to any forward/data phase.

## Risks and rollback

- Baseline contamination risk: low and bounded to the explicitly scoped `gr00t_n1d6` family; no registered sibling family or shared model core changed.
- Runtime risk: packed projections temporarily allocate concatenated tensors; per-shard release limits retention, but the official A100 rerun remains required.
- Rollback: discard the five family/test file changes and this report/handoff from the isolated branch/worktree. No commit, push, PR, dataset, checkpoint, or external state needs reversal.
