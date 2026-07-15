# M10 distributed correctness repair W1

- role: `M10-DISTRIBUTED-CORRECTNESS-REPAIR-W1`
- route: non-President repair writer; model/reasoning fields requested by parent prompt, not exposed in this runtime
- workspace: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-distributed-correctness-repair-w1`
- branch: `dev/m10-distributed-correctness-repair-w1`
- base and starting HEAD: `bf6eaaef84260265877c6c8b41e516e4ecc5b820`
- decision: `REQUEST_CHANGES`
- safe_to_close: `false`
- commit: recorded in the final worker return after this report is committed

## Identity and boundaries

The exact worktree, branch, starting HEAD, clean worktree, and clean index were
verified before edits. Work remained inside the sole-owned paths. No DevSpace
MCP, descendants, network, GPU, Slurm submission, push, PR, dataset mutation,
checkpoint, service token, Hugging Face upload, or W&B action was used. No
registered StarVLA baseline path or `tests/model` path was edited.

PDE-001, PDE-002, and PDE-003 are implemented. PDE-004 pinned-memory overlap
and PDE-005 per-shard checkpoint manifests remain explicit future-evidence
deferrals and were not implemented.

## Execution path and integration boundary

The traced path is:

`TrainingEngine.setup`
-> validated `TrainingTopology`
-> `DataModule.bind_partition/setup`
-> immutable dataset manifest plus rank-local `DataLoaderState`
-> `DistributedBatchPlan`
-> strategy `prepare`
-> DDP rendezvous/process-group setup
-> model/optimizer/scheduler binding
-> optional checkpoint restore and a second remaining-batch proof
-> batch CPU-to-device preparation
-> forward/backward/accumulation boundary
-> synchronized gradient aggregate
-> clip/optimizer/scheduler/zero-grad.

This preserves the StarVLA engineering-base to AutoVLA-native target boundary:
the repair stays in existing `autovla/data`, `autovla/config`, and
`autovla/training` contracts and adds no wrapper tree or competing source
layout. Canonical `TrainingBatch` tensor ownership remains unchanged: the
processor is still the only CPU-to-device transfer owner, the prepared session
still owns forward/backward/step, and checkpoint state remains rank-local plus
the existing collective protocol.

## Implementation summary

### PDE-001

- Added `DistributedBatchPlan` and exact per-rank committed-batch arithmetic.
- Map plans use immutable train-split sample counts, world size, batch size,
  `drop_last`, partition policy, and committed resume cursor without
  materializing the sample sequence.
- Non-divisible `exact_no_pad` tails fail only when rank batch counts differ.
  Divisible/equivalent exact plans remain valid. `drop_global_tail` is the
  preferred repair and does not repeat samples. `pad_repeat` is rejected.
- Streaming plans use the explicit per-rank nominal epoch size and committed
  cursor to prove equal remaining batch counts.
- Engine validation occurs before any collective-bearing strategy `prepare`,
  and runs again after checkpoint restore before training resumes.

### PDE-002

- DDP validates the topology-derived master address and port before CUDA or
  process-group side effects.
- `dist.init_process_group` receives explicit `tcp://` init method, `rank`, and
  `world_size`. A direct Slurm launch therefore does not depend on absent
  torchrun `RANK/WORLD_SIZE` variables.

### PDE-003

- Replaced per-parameter `torch.isfinite(...).all().item()` calls with one
  `_foreach_norm(..., inf)` device aggregate for dense gradients, a device-side
  sparse-value aggregate when needed, and one final host `item()` decision.
- Native DDP calls this only at a synchronized accumulation boundary, where DDP
  gradients are already rank-consistent, so no extra gradient-finiteness rank
  collective is added.
- Accumulation, short-tail scaling, unscale, clipping, precision step,
  optimizer/scheduler counters, zero-grad, and save/resume ownership remain in
  the existing session.

## Changed files

- `autovla/data/contracts.py`
- `autovla/config/schema/data.py`
- `autovla/training/engine.py`
- `autovla/training/session.py`
- `autovla/training/strategy/distributed_data_parallel.py`
- `tests/data/test_distributed_batch_plan.py`
- `tests/config/test_distributed_loader_policy.py`
- `tests/training/test_ddp_correctness_repair.py`
- `docs/validation/M10_DISTRIBUTED_AND_SCALING.md`
- this report

## Validation evidence

- deterministic focused pytest: `61 passed, 25 skipped`
  - the production DDP class was AST-extracted and its real `setup` method ran
    against a pure CPU fake-dist surface;
  - non-divisible map tails, no-repeat global tail drop, exact divisible plans,
    resume cursors, streaming equivalence, setup ordering, and gradient source
    synchronization bounds are covered;
  - skips are existing conditional Torch/runtime tests in the focused files;
    the new CPU fake-dist and AST contract tests all ran and passed.
- Black check on all changed Python paths: pass.
- Ruff on all changed Python paths: pass.
- `py_compile` on all changed Python paths: pass; generated caches were removed.
- strict Pyright on Torch-independent owned source
  (`autovla/config/schema/data.py`, `autovla/data/contracts.py`) and the CPU
  fake-dist training test:
  `0 errors, 0 warnings, 0 informations`.
- full strict Pyright on all owned paths: blocked. The checked-in config points
  to missing `envs/training-deepspeed/.venv`, and the only available governed
  tool venv has pytest/Black/Ruff/Pyright but no Torch. Attempting the full
  command produced unresolved-Torch cascades rather than actionable owned-code
  type evidence. No dependency installation or network access was authorized.
- `git diff --check`: pass before report; rerun in the final scan.
- no real compute submission or distributed-runtime claim.

The strict-Pyright environment blocker prevents a truthful PASS token even
though the available source, fake-dist, formatting, lint, compile, and focused
pytest evidence is green.

## Complexity and efficiency

- Batch-plan proof: `O(W)` time and `O(W)` small-integer space for world size
  `W`; no `O(N)` sample-index materialization and no dataset data movement.
- Gradient finite check: `O(G)` device reads over total gradient elements and
  `O(P)` device scalars for `P` dense gradient tensors. Host synchronization is
  reduced from up to `O(P)` decisions to one per optimizer boundary. DDP adds no
  new gradient-finiteness collective.
- Rendezvous setup adds constant work and no steady-state memory.
- GPU utilization risk is reduced by removing parameter-by-parameter host
  stalls. The foreach still reads each dense gradient once after unscale.
- Distributed efficiency retains existing DDP bucket synchronization and
  accumulation `no_sync`; no extra wrapper, sample duplication, or collective
  is introduced.
- Baseline contamination risk is low: only AutoVLA-native owned paths and
  focused tests changed. No model family or protected baseline implementation
  changed.

## Reference reuse decision

- References considered: existing `PartitionPlan`, `drop_global_tail`,
  `TrainingDataLoader` committed cursor, PyTorch DDP public rendezvous arguments,
  and Torch foreach primitives already available to the runtime.
- Reuse mode: native extension of existing contracts and direct use of existing
  Torch APIs; no third-party source copied or adapted.
- License/copyright/notice: no copied code, no new notice required.
- Dependency impact: none.
- Native implementation reason: the required proof belongs at the existing
  AutoVLA data/training seam and needs no external package or wrapper.
- Residual risk: Torch-backed fake-dist and full strict typing still need the
  declared project environment; real DDP remains unclaimed.

## Slurm requirements and validation suggestion

No Slurm action was authorized or submitted. After the external real-data and
asset gates are satisfied, validation should use the existing project wrapper
in this order: project-local strict Pyright with the declared Torch environment,
CPU Torch fake-dist tests, one same-node DDP preflight, then an explicitly
authorized cross-node job. Record job IDs, exact HEAD, logs, rank-local batch
counts, optimizer-step parity, and outputs under `runs/`. That future evidence
must not be represented as part of this repair.

## Risks and rollback

- The main remaining blocker is absent Torch/Pyright environment evidence.
- `_foreach_norm` compatibility must be exercised in the supported pinned Torch
  runtime, including sparse-gradient fallback behavior.
- Streaming equality proves configured committed counts; backend underflow is
  still guarded by the existing loader underflow checks and needs real runtime
  evidence.
- Rollback is one commit revert. It restores the previous loader acceptance,
  environment-derived DDP rendezvous, and per-parameter gradient checks. No
  dataset, checkpoint, run artifact, or external state requires cleanup.
