# M10 Assembly / CLI Repair W1

## Verdict

`PASS_ASSEMBLY_CLI_REPAIR`

`safe_to_close: true`

## Identity and scope

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-assembly-cli-repair-w1`
- Branch: `dev/m10-assembly-cli-repair-w1`
- Frozen base: `bf6eaaef84260265877c6c8b41e516e4ecc5b820`
- Findings closed: `ARCH-003`, `IC-002`, `IC-003`
- No DevSpace MCP, descendants, network, external assets, GPU, Slurm, push, or PR was used.
- No lifecycle/status file, protected baseline path, dataset, checkpoint, run output, service
  credential, or third-party code was modified.

## Changed files

- `autovla/models/assembly/__init__.py`
- `autovla/models/assembly/contracts.py`
- `autovla/models/assembly/plan.py`
- `autovla/models/families/gr00t_n1d6/factory.py`
- `autovla/cli/train.py`
- `tests/model/test_m10_assembly_cli_repair.py`
- This report.

## Implementation summary

1. Added the shared typed `TrainingAssemblyAdapter`, `PreparedTrainingAssembly`, and
   `BaseModelAssetIdentity` contracts. The production CLI now resolves a registered family,
   checks its runtime gate, and invokes this family-owned adapter. The CLI contains no
   `registry_key == gr00t_n1d6` branch, no N1.6 import, and no N1.6 config/asset construction.
2. Moved N1.6 local receipt resolution, checkpoint metadata parsing, family config projection,
   embodiment transform selection, and `ModelAssemblyRequest` creation into
   `Gr00tN1d6ModelFactory.prepare_training_assembly`.
3. Made non-executable family runtime gates run before training dependency checks, CUDA process
   setup, asset access, or model construction. Existing lifecycle/status sources were untouched.
4. Consolidated registered processor/backbone/action-head/checkpoint paths and full-model
   construction behind `Gr00tN1d6ModelFactory`. The full model enters exactly one initialization
   context and constructs backbone, action head, model, and processor inside that context.
5. Split assembly dependency selection by operation. Asset receipt and checkpoint index factories
   have no CUDA-extension requirement; processor excludes GPU extensions; parameter allocation
   retains the declared `flash_attn` requirement.
6. Preserved `NO_BACKEND_WINNER`, lazy imports, local-only asset semantics, checkpoint evidence,
   training-plan identity, and M1-M9 compatibility surfaces.

## Execution path and tensor/data flow

The repaired path is:

`ExperimentConfig -> model family registration -> runtime gate -> training strategy/process device
-> TrainingAssemblyAdapter -> verified local receipts/checkpoint JSON -> TransformPlan ->
ModelAssemblyRequest -> ModelAssemblyPlan/TrainingPlan -> one initialization context ->
processor + [B,image/token/state] backbone inputs -> action head [B,T,D] -> checkpoint load ->
TrainingEngine`.

No tensor shape, normalization, action horizon, action dimension, state dimension, or physical
action semantics changed. The N1.6 family continues to own its existing 50/128/128 envelope and
per-embodiment transform plan.

## Complexity and performance

- Time complexity: registry/adapter dispatch is `O(1)`; dependency filtering is `O(D)` over the
  small immutable dependency tuple; checkpoint index inspection remains `O(K)` in index keys;
  model allocation/load complexity is unchanged.
- Space complexity: new composition records are `O(1)`; checkpoint inspection still reads JSON
  metadata without tensor materialization. No model, dataset, or checkpoint copy was added.
- Data movement: no new host/device transfer, tensor clone, serialization, or dataset movement.
- GPU utilization: model kernels and tensor paths are unchanged. One ZeRO-3 initialization context
  encloses all parameter allocation, avoiding repeated partition-context entry.
- Distributed efficiency: no new collective, synchronization point, wrapper stack, or per-rank
  duplicated model construction was introduced.
- Baseline contamination risk: low. Changes are limited to the explicitly owned AutoVLA assembly,
  N1.6 factory, CLI, focused test, and report paths; registered lifecycle/status files are unchanged.

## Validation

- Focused assembly/N1.6/CLI regression:
  `40 passed in 3.96s`.
- Strict Pyright over all owned Python source and the focused test:
  `0 errors, 0 warnings, 0 informations`.
- Black exact owned files, line length 100, one worker: pass.
- Ruff exact owned files: pass.
- `py_compile` exact owned Python files with redirected cache: pass.
- Fresh lightweight import of `autovla.cli.train` and `autovla.models.assembly`: pass;
  `torch`, `flash_attn`, and the N1.6 factory remained unloaded.
- Missing-module regression: checkpoint index factory loads when `flash_attn` is simulated missing;
  parameter-allocation factory fails with `OptionalDependencyError`.
- Single initialization-context regressions: full-model AST ownership and registered backbone
  one-shot runtime delegation both pass.
- `git diff --check`: pass.
- Additional compatibility probe: `33 passed, 3 failed`; all three failures are pre-existing,
  out-of-scope config-contract drift in `test_production_runtime_source_contract.py` and
  `test_packaged_resources.py`, with no stack frame in changed source. They were not modified.

## Slurm requirements

None. The task explicitly prohibited GPU and Slurm, and all required checks were lightweight local
static/unit validation. Real CUDA forward/backward/update remains an integration-stage concern.

## Reference reuse decision

- References considered: current StarVLA/AutoVLA assembly, registry, N1.6 factory, training CLI,
  and existing M10 tests.
- Reuse mode: native extension of existing typed registry/factory seams; no external code copied,
  wrapped, adapted, or vendored.
- License/copyright/notice status: no new third-party code or dependency; no notice change needed.
- Dependency impact: no dependency added; existing dependency declarations are applied at narrower
  component/operation boundaries.
- Native implementation reason: the accepted findings are ownership and composition defects in the
  existing local contracts, so a minimal local repair is safer than introducing another wrapper.
- Residual risk: official CUDA/ZeRO-3 runtime remains unexecuted by task policy.

## Risks and rollback

- Risk: future executable families must implement `TrainingAssemblyAdapter` before the production
  CLI can train them; otherwise they fail closed with a typed boundary error.
- Risk: full N1.6 parameter allocation now explicitly checks the already-declared `flash_attn`
  extension while metadata/index operations do not.
- Rollback: revert the repair commit. No migration, generated asset, dataset mutation, checkpoint,
  remote state, or external side effect requires cleanup.
