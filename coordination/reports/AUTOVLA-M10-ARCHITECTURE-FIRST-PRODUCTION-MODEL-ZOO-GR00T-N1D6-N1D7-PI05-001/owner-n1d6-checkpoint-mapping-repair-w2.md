# M10 N1D6 checkpoint mapping repair W2

Conclusion: `PASS_SOURCE_REPAIR`

- task: `AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001`
- worker: `M10-N1D6-CHECKPOINT-MAPPING-REPAIR-W2`
- route requested: `gpt-5.6-sol / medium`; route fields not exposed in the local shell
- isolated worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-n1d6-checkpoint-mapping-repair-w2`
- branch: `dev/m10-n1d6-checkpoint-mapping-repair-w2`
- base/current HEAD: `dfb0e2f7634561279367947ea85fef834ef6bb63`
- DevSpace MCP: `no`
- descendants: `none`
- commit/push/PR/stage mutation: `none`

## Workspace verification

Before edits, `pwd` and `git rev-parse --show-toplevel` both matched the required isolated worktree. The branch and HEAD matched exactly. `git status --short` had no tracked changes and `git diff --cached --name-only` was empty. The canonical M10 worktree and root checkout were read only; no file there was mutated.

## Official-source and header evidence

The inspected official source was the prompt-pinned local checkout at NVIDIA/Isaac-GR00T commit `5dc80c4afd726b34faad1d8f7e007a13b34e4c88`, file `gr00t/model/modules/dit.py`. Its `BasicTransformerBlock` delegates to diffusers `FeedForward` with `activation_fn`, `inner_dim=ff_inner_dim`, `bias=True`, and `final_dropout`. The N1.6 DiT defaults are `activation_fn="gelu-approximate"`, `ff_inner_dim=None`, and `final_dropout=True`; upstream pins `diffusers==0.35.1`. The verified checkpoint config further fixes width `32 * 48 = 1536`, 32 layers, dropout `0.2`, and `final_dropout=true`.

Only the safetensors 8-byte length prefix and JSON header were read from both official shards; no tensor payload was loaded and no asset was mutated. The index contains 1106 source keys. Exactly 64 are `action_head.model.transformer_blocks.{0..31}.ff.net.0.proj.{weight,bias}`:

- every weight: BF16 `[6144, 1536]`
- every bias: BF16 `[6144]`
- representative output projection: `[1536, 6144]`

The first shard contains blocks 0 through 17 FFN input projections and the second contains blocks 18 through 31. Evidence is under `runs/tmp/AUTOVLA-M10-ARCHITECTURE-FIRST-PRODUCTION-MODEL-ZOO-GR00T-N1D6-N1D7-PI05-001/engineering/n1d6-checkpoint-mapping-repair-w2/`.

## Root cause and implementation

The local FFN incorrectly implemented GEGLU: it allocated `proj_in: 1536 -> 12288`, split the result into value/gate halves, and multiplied by gated GELU. Official N1.6 uses a single `1536 -> 6144` projection followed by tanh-approximate GELU. Therefore all 32 `proj_in` weights and biases had exactly twice the official leading dimension while every other mapped key and shape already matched in C2R5.

The repair is family-local and direct because a checkpoint adapter cannot change an incorrect parameter layout or forward activation without forbidden resize/truncation/fabrication. `_nvidia/dit.py` now implements:

`Linear(1536, 6144) -> GELU(approximate="tanh") -> Dropout(0.2) -> Linear(6144, 1536) -> Dropout(0.2)`.

The checkpoint key mapping remains exact and unchanged. Its shard-loader docstring now preserves the older public tensor-only safety marker while documenting that safetensors is equivalent to `weights_only=True`. Tests now verify all 32 weight/bias target shapes, the activation path, FFN source-to-target collision failure, and incomplete Q/K/V failure.

No config, action-head call site, dependency, quality config, sibling family, shared model core, data path, Slurm path, root checkout, canonical worktree, or asset changed. The renamed internal FFN class was not exported and has no public contract surface.

## Changed files

- `autovla/models/families/gr00t_n1d6/_nvidia/dit.py`
- `autovla/models/families/gr00t_n1d6/checkpoint.py`
- `tests/model/test_m10_gr00t_n1d6_checkpoint_mapping.py`
- this Owner report
- ignored evidence only under the authorized `runs/tmp/.../engineering/n1d6-checkpoint-mapping-repair-w2/` root

## Validation and gates

- focused plus directly related N1.6 pytest: `25 passed, 1 warning in 4.08s`. The warning is the existing non-writable NumPy fixture warning in `test_gr00t_n1d6_runtime_contract.py`.
- Black: all four changed Python paths passed filewise. The combined invocation hit the existing shutdown hang after 60 seconds and was terminated; each authoritative filewise invocation exited 0 after the evidence script was formatted.
- Ruff: `All checks passed!`
- `py_compile`: passed with `PYTHONPYCACHEPREFIX` redirected under the authorized evidence root.
- strict Pyright: the repaired behavioral source `_nvidia/dit.py` passed with `0 errors, 0 warnings, 0 informations` using an existing project-local runtime-cpu environment and an evidence-local strict config. Full changed source/test checking remains blocked by 15 pre-existing strict errors: two in unchanged checkpoint implementation lines (`_flatten_official_stat` unused and `_tensor_mapping` narrowing) and thirteen in existing dynamically typed test helpers. No suppression or quality-policy weakening was added.
- exact full header-to-local reconciliation: 1106 checkpoint header keys converted by the real adapter to 1010 keys; complete local meta `state_dict` has 1010 keys; `missing=[]`, `unexpected=[]`, `shape_mismatches=[]`; all 64 FFN input targets have official shapes; `full_tensor_data_loaded=false`.
- `git diff --check`: passed.
- index: empty; no staging occurred.

## Complexity, memory, and distributed impact

- Forward time remains linear in batch and sequence length. For FFN linear layers, the repair reduces each block from approximately `12*d^2` to official `8*d^2` multiply-add structure, removing the extra gated input projection and its elementwise multiply.
- The repair removes 9,443,328 invented parameters per block, 302,186,496 across 32 blocks. At the configured trainable FP32 policy this removes about 1.13 GiB of parameter storage and the same gradient volume; Adam-like FP32 optimizer state can avoid roughly another 2.25 GiB before ZeRO partitioning.
- The widest FFN preactivation decreases from 12,288 to 6,144 elements per token, reducing forward/backward activation traffic and pressure. No new host-device copy, synchronization, collective, wrapper, or checkpoint pass was introduced.
- DDP gradient communication and ZeRO partition/storage decrease with the removed non-official parameters. Topology behavior and communication algorithms are otherwise unchanged.
- Header reconciliation is `O(K + P)` metadata time and `O(K + P_meta)` meta-state space for 1106 source keys and 1010 targets; it reads approximately the two JSON headers rather than 6.57 GB of tensor payload.

## Reference reuse decision

- references considered: pinned NVIDIA/Isaac-GR00T `dit.py`, its pinned diffusers dependency/config semantics, official checkpoint config/index, and both shard headers.
- reuse mode: source-aligned native correction of the existing attributed NVIDIA adaptation; no new third-party code block or file was copied.
- license/notice: existing NVIDIA source header and repository license reference remain unchanged; no notice update is required.
- dependency impact: none.
- native implementation rationale: the family already owns a dependency-light PyTorch implementation; adding diffusers would be an unauthorized dependency change and an unnecessary wrapper.
- tests: shape, numerical activation, collision/incomplete fail-closed behavior, related N1.6 contracts, and full metadata reconciliation all passed as recorded above.
- residual risk: metadata equality proves exact keys and shapes, not numerical tensor contents or CUDA materialization behavior.

## Slurm requirement, risks, and rollback

Slurm/GPU execution was explicitly forbidden for this worker and was not used. A later authorized canonical A100 rerun should perform the real full checkpoint materialization and proceed to forward/backward only after the runtime loader also reports zero missing/unexpected/shape mismatches. No CPU full-tensor load should be substituted for that gate.

Baseline contamination risk is low and bounded to the explicitly authorized `gr00t_n1d6` family. The main residual risk is that real BF16 checkpoint materialization, CUDA memory peaks, and numerical forward equivalence remain for the next compute owner. Rollback is limited to discarding the three tracked implementation/test diffs and this report from the isolated worktree; ignored evidence can be left unreferenced. No external or Git publication state requires reversal.

PASS_SOURCE_REPAIR
