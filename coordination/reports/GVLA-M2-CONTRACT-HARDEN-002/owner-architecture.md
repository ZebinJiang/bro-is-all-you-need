# GVLA-M2-CONTRACT-HARDEN-002 Owner Architecture Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `cc85077c8cc2d327e89ada4afebab7fda2e0cedc`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- workspace_check: `PASS`
- status_short_before_AW1 included pre-existing Q-W1 / coordination dirtiness:
  - `M .github/workflows/genesisvla.yml`
  - `M coordination/PROGRAM_STATE.yaml`
  - `M coordination/TASK_INDEX.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATE-AUDIT-001.yaml`
  - `M coordination/tasks/active/GVLA-M2-INTEGRATION-PUBLISH-002.yaml`
  - `M coordination/tasks/active/GVLA-M2-MILESTONE-AUDIT-001.yaml`
  - `M scripts/quality/bootstrap_project_local_tools.sh`
  - `M tests/meta/test_repo_policy.py`
  - multiple untracked coordination report/task files for the M2 hardening flow

Architecture A-W1 did not stage, unstage, commit, push, edit PR state, reset, restore, clean, stash, delete files, mark M2 complete, or modify `.agent-docs/feature_list.json`.

## Current Conclusion

`PASS`

A-W1 implemented the Architecture-owned public contract hardening within the amended allowed scope. Data D-W1 may proceed after Manager confirms the serial handoff.

## Files Changed By A-W1

- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/transforms/compose.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/__init__.py`
- `genesisvla/dataloader/transforms/__init__.py`
- `tests/dataloader/test_transform_registry.py`
- `tests/dataloader/test_dataset_statistics.py`
- `tests/dataloader/test_collate.py`
- `docs/genesisvla/m2_transform_data_contract.md`

No changes were made to `genesisvla/core/protocols/transform.py`; the core `TransformProtocol` remains the minimal `RawSample -> RawSample` protocol.

## Implementation Summary

- Added `genesisvla.dataloader.contracts` as the M2 dataloader-owned public contract surface.
- Added strict JSON aliases and canonicalization for `JsonScalar`, `JsonValue`, and `JsonObject`.
- Added immutable/versioned `TransformSpec`, `ComposeConfig`, `SerializableTransformProtocol`, `TransformContext`, and `CollatedBatch`.
- Preserved source-compatible `TransformSpec(name=..., params=...)` construction while adding default `schema_version="2.0"` and `implementation_version="1"`.
- Reworked `ComposeTransform` so public serialization is explicit through stored specs / `to_spec()`, not dynamic `getattr()`.
- Updated transform fingerprint payload to include fingerprint schema version, spec schema version, implementation version, name, and canonical params.
- Added typed batch collation with canonical batched action mask shape `[B,H,D]`; legacy sample mask `[D]` is accepted only at the collate conversion boundary and broadcast to `[H,D]`.
- Kept legacy `collate_raw_samples()` dict output by delegating through `CollatedBatch.to_legacy_dict()`.
- Hardened `FeatureStatistics` and `DatasetStatistics` ownership with defensive copies, read-only stored arrays, and strict JSON metadata canonicalization.
- Updated public exports and M2 docs for serialization, versioning, `TransformContext`, typed batch, and statistics ownership.

## Public Contract Decisions

- Core protocol boundary: unchanged; no core -> dataloader dependency was introduced.
- JSON contract: mapping keys must be strings; non-finite floats, numpy arrays, sets, bytes, callables, dataclasses, and arbitrary runtime objects are rejected.
- Transform specs: params are deep-owned, sorted, immutable, and included in stable fingerprints with schema and implementation versions.
- Serialization: only explicitly serializable transforms expose `to_spec()`; runtime-only `ComposeTransform` instances fail serialization clearly.
- TransformContext: immutable dataloader-owned context with seed, epoch, sample key/index, worker id/count, rank/world size, and JSON-safe metadata.
- CollatedBatch: typed numpy-only batch with defensive array ownership; sample actions remain `[H,D]`, batch actions/masks are `[B,H,D]`.

## Compatibility / M1 Regression Analysis

- M1 public contracts were not modified.
- Existing `RawSample` behavior remains intact.
- Existing `TransformSpec(name, params)` call sites remain compatible because the new version fields have defaults.
- Legacy `collate_raw_samples()` remains available and returns the existing dict-shaped batch surface, now with canonical default action masks when actions exist.
- Fingerprint values intentionally change because the payload is now versioned and includes implementation versions; this is acceptable before M3 consumes the public M2 contract.

## Commands And Results

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_transform_registry.py tests/dataloader/test_dataset_statistics.py tests/dataloader/test_collate.py tests/dataloader/test_cpu_tiny_e2e.py -q`: `PASS`, `26 passed`.
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q`: `PASS`, `51 passed`.
- `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`: `PASS`, `0 errors, 0 warnings, 0 informations`.
- Intermediate `make genesis-check`: `BLOCKED_TEST` only by Black/Ruff formatting; product tests and Pyright passed. Formatting was fixed within allowed A-W1 files.
- Final `make genesis-check`: `PASS`; product pytest `143 passed`, product Black/Ruff/Pyright passed, governance pytest `21 passed`, governance Black/Ruff passed.
- `git diff --check`: `PASS`.
- `git status --short`: shows A-W1 allowed file changes plus pre-existing Q-W1 / coordination dirtiness; no staging was performed.
- Suppression scan on A-W1 touched source/tests: `PASS`; no `type: ignore`, `pyright: ignore`, `# pyright`, or `cast(Any, ...)` matches.

## Remaining Data-Owned Follow-Ups For D-W1

- Implement production transform factories / action-mode policy serialization through the new `SerializableTransformProtocol.to_spec()` surface.
- Wire dataset/source provenance through Data-owned loaders and mixture/dataset paths using `TransformContext` and `CollatedBatch.sample_source`.
- Confirm any Data-owned transform reconstruction uses the versioned `TransformSpec` and does not reintroduce dynamic `getattr()` serialization.
- Extend production statistics/fingerprint integration where Data-owned caches combine transform specs with dataset statistics.

## Scope / Protected Path Check

`PASS`

A-W1 touched only the amended Architecture write scope. It did not modify model, training, deployment, acceleration, datasets, code-input, feature-list passes, PR/remote state, git index, Q-W1 workflow/bootstrap/meta files, or M1 completion state.

## Risks

- `TransformSpec` fingerprint changes are intentional contract hardening, but downstream caches must treat old M2 draft fingerprints as stale.
- `CollatedBatch` is now stricter about JSON-safe metadata and `[B,H,D]` mask shape; Data D-W1 should route non-JSON runtime objects outside public metadata.
- Production transform serialization remains incomplete until Data D-W1 adds `to_spec()` on concrete Data-owned transforms where needed.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit/bash, new worktree, new Python environment, stage, commit, push, PR edit/create, merge, force push, stash, reset, restore, clean, rm, feature-list pass update, or milestone completion update was used.

## Subagent Retirement Ledger

- A-W1 writer: executed directly by the persistent Architecture Owner; retired: `yes`.
- Short-lived subagents: none used; no child subagent contexts remain active.

## Parallelism Note

Single canonical writer for A-W1; no parallel write.
