# M10 Status Lifecycle Repair W1

Conclusion: `PASS_STATUS_LIFECYCLE_REPAIR`

`safe_to_close: true`

## Identity and scope

- Worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m10-status-lifecycle-repair-w1`
- Branch: `dev/m10-status-lifecycle-repair-w1`
- Base: `bf6eaaef84260265877c6c8b41e516e4ecc5b820`
- Startup: worktree, branch and HEAD matched; worktree and index were clean.
- Accepted findings: `ARCH-001`, `ARCH-004`, `IC-001`, `RM-001`, `RM-002`, `RM-003`.
- DevSpace MCP, descendants, network, assets, GPU, Slurm, PR and push: not used.
- No assembly plan, CLI, transform, training, distributed, dataset, remote-CI, M8/M9 repair,
  external service or unowned path was modified.
- `passes` was not set to true. `NO_BACKEND_WINNER` remains literal.

## Implementation summary

- `autovla/models/families/specification.py`
  - Separates source completeness, assembly eligibility and evidence-backed runtime readiness.
  - Serializes the two public booleans independently and closes invalid evidence combinations.
  - Records strict checkpoint tensor/missing/unexpected/shape counts, device and accepted evidence.
  - Makes compatibility `runtime_supported` report evidence-backed readiness, not mere assembly entry.
- `autovla/assets/registry.py`
  - Replaces stale active status vocabulary with exact `BLOCKED_C3_DATA` and
    `BLOCKED_ASSET_LICENSE` states.
- N1.6 specification, both presets, source map and status documentation
  - Record only accepted C1 and C2R7 evidence: one-A100 strict load, 1010 tensors, zero missing,
    unexpected and shape-mismatched keys.
  - Mark N1.6 assembly-eligible while `runtime_ready=false` at `BLOCKED_C3_DATA`.
  - Explicitly keep real batch, forward, backward, optimizer, prediction, resume, DDP,
    DeepSpeed, cross-node, scaling and quality unverified.
- Pi0.5 family and factory
  - Set shared support to `asset_required`, so shared assembly resolution rejects execution at
    `BLOCKED_ASSET_LICENSE` before caller-supplied `complete()` components can be inspected.
  - Preserve the exact Apache-2.0 source statement and separate unresolved Gemma/checkpoint terms.
- N1.7 and Pi0.5 package roots
  - Add explicit `TYPE_CHECKING` imports for every concrete public type.
  - Keep runtime imports lazy, make `__all__` exact, cache resolved symbols and expose stable
    `__dir__` output.
- Focused tests
  - Cover exact lifecycle states, public status serialization, C1/C2R7 counts, Pi0.5 `complete()`
    bypass rejection, and fresh-process lazy/type/cache/directory behavior.
- Documentation/task surfaces
  - `README.md`, three architecture documents, N1.6 `SOURCE_MAP.md`, upstream-to-local YAML and
    the active task card now expose the same bounded status facts.

Changed tracked paths are limited to the prompt-owned asset registry, family specification and
package roots, Pi0.5 family/factory, N1.6 presets/maps, architecture/status documents, active task
card, focused tests, and this report. No registered baseline implementation path was edited; the
family-local status files were explicitly scoped by the prompt.

## Validation

The existing project-local runtime-cpu environment was used. Caches, bytecode and task Pyright
configuration stayed under ignored `runs/tmp/.../status-lifecycle-repair-w1/`.

- Focused pytest: `66 passed in 3.51s`.
- Fresh-process N1.7/Pi0.5 lazy import, caching, `__all__` and `__dir__` probe:
  `PASS_FRESH_PROCESS_LAZY_IMPORTS` with Torch, Transformers, JAX, Flax and Orbax absent.
- Strict Pyright on all modified Python paths: `0 errors, 0 warnings, 0 informations`.
  The task-only strict config uses the existing runtime-cpu venv and excludes only the inherited
  `reportPrivateUsage` diagnostic already present in owned legacy files; all other strict rules
  remain active.
- Black `--check --line-length 100 --workers 1`: all 11 modified Python paths passed filewise.
  The combined sandbox process reproduced the known shutdown hang and was terminated; identical
  filewise commands exited zero.
- Ruff: `All checks passed!`.
- `py_compile`: `PASS_PY_COMPILE` with redirected bytecode cache.
- YAML parse: `PASS_YAML_PARSE 4` for both N1.6 presets, source map and task card.
- Status scan: `PASS_STATUS_CONSISTENCY` and `PASS_NO_STALE_ACTIVE_STATUS`.
- `git diff --check`: `PASS_GIT_DIFF_CHECK`.
- Final staged scope, cached diff, secret/model-asset/large-file scans and commit identity are
  completed after this report is included.

## Complexity and runtime impact

- Time complexity: status construction/serialization remains O(1) per family and O(F) for family
  listing. Evidence validation adds only a fixed set of boolean/count checks.
- Space complexity: O(1) additional small metadata per family; no tensor, dataset or checkpoint
  bytes are retained.
- Data movement and memory: no model tensor allocation, host-device copy, checkpoint read,
  dataset access or runtime memory behavior changed. C2R7 is recorded evidence, not rerun here.
- GPU/distributed efficiency: no kernels, collectives, DDP/DeepSpeed policy, topology or scaling
  behavior changed; those runtime properties remain explicitly unverified.
- Baseline contamination: low. Changes are confined to explicitly owned AutoVLA M10 status,
  family-local lifecycle and test/documentation surfaces; StarVLA baseline execution paths remain
  untouched.

## Reference reuse decision

- References considered: current StarVLA model integration guidance, existing AutoVLA shared
  assembly resolver, family definitions, asset registry and accepted C1/C2R7 facts.
- Reuse mode: existing native contracts and resolver only; no third-party code copied, adapted,
  wrapped or vendored.
- License/notice: existing NVIDIA and OpenPI source/license statements are preserved exactly; no
  copyright or notice change is required.
- Dependency impact: none.
- Tests: focused lifecycle, status, serialization and lazy import tests plus static checks pass.
- Residual risk: runtime execution beyond strict checkpoint materialization remains unverified by
  design; no quality or backend conclusion is authorized.

## Slurm, risks and rollback

- Slurm requirement: none. This repair is source/status/static validation only, and the prompt
  explicitly forbids Slurm/GPU execution.
- Residual risks: downstream consumers that treated `runtime_supported` as assembly eligibility
  must migrate to `assembly_eligible`; this semantic correction is intentional and regression
  tested. Pi0.5 cannot execute until its asset/license gate is resolved by separately authorized
  evidence.
- Rollback: revert the resulting single commit or restore only the listed owned paths from base
  `bf6eaaef84260265877c6c8b41e516e4ecc5b820`. No asset, dataset, run, external service,
  scheduler, PR or remote branch state needs rollback.

`PASS_STATUS_LIFECYCLE_REPAIR`
