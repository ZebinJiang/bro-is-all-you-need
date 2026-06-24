# GVLA-M2-DATA-TYPING-001 Owner Data Wave 1 Report

## Workspace verification

- target_worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- required_branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required_HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `e59f6b34bc6c76181b630d3b446a0438bff01da8`
- workspace_check: PASS
- git status --short at start:

```text
 M coordination/PROGRAM_STATE.yaml
 M coordination/TASK_INDEX.yaml
?? coordination/reports/GVLA-M2-RESTACK-001/
?? coordination/tasks/active/GVLA-M2-CORE-TYPING-001.yaml
?? coordination/tasks/active/GVLA-M2-DATA-TYPING-001.yaml
?? coordination/tasks/active/GVLA-M2-TOOLCHAIN-001.yaml
?? coordination/tasks/active/GVLA-M2-UNBLOCK-REVIEW-001.yaml
```

- Existing dirty state was not modified by Data Wave 1 except for the allowed report/evidence paths.
- Persistent Owner reasoning/speed note: `thinking=xhigh` was requested by dispatch; speed/latency fields are requested/not exposed by the current tool surface.

## Report path correction

- Initial report landed in the main checkout at `/home/cz-jzb/workspace/vla-flywheel/coordination/reports/GVLA-M2-DATA-TYPING-001/owner-data-wave1.md`.
- The main checkout file was not deleted.
- Canonical report has now been written to `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked/coordination/reports/GVLA-M2-DATA-TYPING-001/owner-data-wave1.md`.
- Manager should record the initial report-path scope deviation.

## Inputs read

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `coordination/tasks/active/GVLA-M2-DATA-TYPING-001.yaml`
- `docs/coordination/plans/GVLA-M2-PLAN.md`
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- `runs/tmp/GVLA-M2-UNBLOCK-001/pyright-before.txt`
- `runs/tmp/GVLA-M2-UNBLOCK-001/pyright-before-summary.json`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/datasets/mixture.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/testing/fixtures/tiny.py`
- `tests/dataloader/test_image_transforms.py`
- Compatibility context from `coordination/tasks/active/GVLA-M2-CORE-TYPING-001.yaml`, `coordination/tasks/active/GVLA-M2-TOOLCHAIN-001.yaml`, `genesisvla/core/types/action.py`, and `genesisvla/dataloader/transforms/action_mode.py`.

## Complete error clusters and recommended owner split

Source baseline: `runs/tmp/GVLA-M2-UNBLOCK-001/pyright-before-summary.json` records 42 errors, 0 warnings, exit code 1.

Cluster 1: statistics and normalization arrays leak broad `Any`.

- Count: 23 errors.
- Files: `genesisvla/core/types/action.py`, `genesisvla/dataloader/statistics/schema.py`, `genesisvla/dataloader/transforms/state_action.py`.
- Root cause: public/statistics array fields are broad (`NDArray[Any]` or equivalent), so Pyright propagates unknowns through `np.all`, `np.any`, `.copy()`, mask composition, assignment, and `.astype()`.
- Owner split: Architecture owns the one core `action.py` error through `GVLA-M2-CORE-TYPING-001`; Data owns `statistics/schema.py` and `transforms/state_action.py` after Architecture canonical integration.

Cluster 2: image transform numpy shape operations lack typed local boundaries.

- Count: 11 errors.
- File: `genesisvla/dataloader/transforms/image.py`.
- Root cause: chained `np.linspace(...).round().astype(...)`, `np.any`, and `reshape` calls are runtime-correct but too broad for strict Pyright with the current NumPy stubs.
- Owner split: Data owns this in Wave 2; Quality should only verify the strict wrapper stays unchanged.

Cluster 3: collate stack helper has no typed `np.stack` boundary.

- Count: 3 errors.
- File: `genesisvla/dataloader/collate.py`.
- Root cause: optional arrays and metadata-derived masks are stacked through broad `NDArray[np.generic]` inputs and a public `dict[str, Any]` return.
- Owner split: Data owns this, tied to the typed batch/mask/source contract below.

Cluster 4: mixture dataset RNG/weights need explicit typed locals.

- Count: 2 errors.
- File: `genesisvla/dataloader/datasets/mixture.py`.
- Root cause: `np.any` and `Generator.choice` overloads remain partially unknown without typed `weights`/`choices` boundaries.
- Owner split: Data owns this; no Architecture/API change needed if `sample_source` remains Data metadata.

Cluster 5: tiny fixture and image tests have reshape-only strict typing noise.

- Count: 3 errors.
- Files: `genesisvla/testing/fixtures/tiny.py`, `tests/dataloader/test_image_transforms.py`.
- Root cause: inline `np.arange(...).reshape(...)` is valid at runtime but produces partially unknown reshape overloads.
- Owner split: Data owns fixture/test typing under Wave 2 write scope.

Recommended owner split:

- Architecture: finish `GVLA-M2-CORE-TYPING-001` for `genesisvla/core/types/action.py` before Data canonical writes.
- Quality: finish `GVLA-M2-TOOLCHAIN-001` for reproducible strict gate/build wrapper without excluding M2 files or relaxing Pyright.
- Data D-W1: one serial write worker after Architecture and Quality canonical integrations pass, covering Data-owned dataloader/statistics/fixtures/tests/docs paths only.

## Data typed batch/mask/source contract proposal

Wave 2 should add an additive Data-layer typed boundary without changing M1 `RawSample`, `BatchSample`, `ModelInput`, or `ActionChunk`.

Recommended names:

- `SampleSource`: a Data-local `TypedDict` or dataclass for provenance fields such as `dataset`, `index`, `position`, `epoch`, `worker_id`, `worker_count`, `episode_id`, `robot_tag`, and `format`.
- `CollatedBatch`: a Data-local `TypedDict` or dataclass preserving the current mapping keys: `images`, `language`, `actions`, `state`, `robot_tag`, `action_mask`, `metadata`, plus a normalized `source` tuple.

Canonical shapes:

- `images[modality]`: `(B, *image_shape)`; modality names, shapes, and dtypes must match across the batch.
- `language`: tuple length `B`.
- `actions`: `None` when all samples omit actions, else `(B, H, A)`.
- `state`: `None` when all samples omit state, else `(B, *state_shape)`, with state/action transforms using the final dimension.
- `robot_tag`: tuple length `B`.
- `metadata`: tuple length `B`, shallow copied from each `RawSample.metadata`.
- `source`: tuple length `B`, normalized from `metadata["sample_source"]` and safe fallbacks.

Canonical `action_mask`:

- Dtype: `np.bool_`.
- Batch shape: `(B, H, A)` when present.
- `True` means valid action element; `False` means padding/invalid.
- Accepted per-sample input shapes: `(A,)` broadcast across horizon to `(H, A)`, or exact `(H, A)`.
- Rejections: mixed missing/present masks, mask when `actions is None`, wrong rank, wrong length/shape.

M3 compatibility boundary:

- Keep this numpy-only and torch-free.
- Do not add model tokenization, device transfer, masked loss, runner adapters, checkpoint behavior, or framework changes in Wave 2.
- The `(B, H, A)` mask and `source` tuple provide future M3/M4 adapters a stable input without making M3 part of M2.

## JSON/statistics/fixture typing gaps

Observed gaps:

- `TransformSpec.params` is `Mapping[str, Any]`; canonicalization rejects tokenizer/device keys but does not expose a `JsonValue`/`JsonObject` alias or early non-JSON rejection.
- `FeatureStatistics` and `DatasetStatistics` JSON methods return/accept broad `dict[str, Any]`/`Mapping[str, Any]`; malformed JSON payloads rely on runtime casts and late validation.
- `FeatureStatistics` array fields are currently broad enough to seed many `Unknown` follow-on errors in `state_action.py`.
- `TinyParquetFixture.records` is `tuple[Mapping[str, Any], ...]`; required record keys and array dtypes/shapes are not represented as a typed fixture record.
- `MixtureDataset` injects `metadata["sample_source"]` as an untyped nested dict; tests index through unrestricted `Any`.
- Several tests use broad helper payloads (`**overrides: Any`, `dict[str, Any]`) at the same boundaries Wave 2 should harden.

Recommended test gaps for Wave 2:

- Add collate contract tests for typed keys, 1-D mask broadcast, 2-D mask preservation, mixed mask rejection, mask-without-actions rejection, source provenance extraction, and modality mismatch.
- Add statistics/schema tests for malformed `mean/std/minimum/maximum`, wrong `valid_mask`, bad `names`, non-mapping state/action payloads, metadata key coercion, and checksum stability.
- Add image transform tests for CHW resize/normalize, invalid resize size, channel-stat mismatch, probability 0, unsupported augment mode, and multi-image mapping.
- Add fixture tests for parquet-like record keys/dtypes/shapes and JSON-safe generated fixture metadata.
- Keep any remaining `Any` localized to explicit untrusted JSON/input-boundary tests.

## Wave 2 D-W1 implementation plan with exact write scope

Precondition: start only after Architecture `GVLA-M2-CORE-TYPING-001` and Quality `GVLA-M2-TOOLCHAIN-001` canonical integrations pass and Manager dispatches Data write phase.

Single write worker: `D-W1 canonical Data typing implementer`.

Exact recommended write scope:

- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/__init__.py`
- `genesisvla/dataloader/datasets/mixture.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/testing/fixtures/tiny.py`
- `tests/dataloader/test_collate_contract.py` or equivalent new focused collate test file
- `tests/dataloader/test_image_transforms.py`
- `tests/dataloader/test_dataset_statistics.py`
- `tests/dataloader/test_state_action_normalization.py`
- `tests/dataloader/test_mixture_dataset.py`
- `tests/dataloader/test_tiny_fixtures.py`
- `tests/dataloader/test_cpu_tiny_e2e.py` only if the canonical batch mask assertion needs an update
- `docs/genesisvla/m2_transform_data_contract.md`
- `coordination/reports/GVLA-M2-DATA-TYPING-001/owner-data-wave2.md`
- `runs/tmp/GVLA-M2-UNBLOCK-001/data/**`

Explicitly out of Data Wave 2 scope unless Manager issues a revised task:

- `genesisvla/core/**`
- `tests/core/**`
- `scripts/**`
- `Makefile`
- `pyproject.toml`
- `pyrightconfig*`
- `.agent-docs/feature_list.json`
- M1/M2 completion or publication state
- datasets, checkpoints, model weights, external paths, git staging/commit/push/PR/merge/stash/reset/clean/rm

Implementation order:

1. Add failing focused tests for `CollatedBatch`, canonical `(B, H, A)` mask behavior, and `SampleSource`.
2. Add typed batch/source aliases or `TypedDict`s in Data-owned code and export them if needed.
3. Harden `collate_raw_samples()` with typed local stack helpers, mask expansion, and source normalization while preserving current runtime keys.
4. Tighten `FeatureStatistics` stored array field annotations and local casts so `state_action.py` receives typed arrays.
5. Add typed numpy local boundaries in `image.py`, `mixture.py`, and tiny fixture/test reshape helpers.
6. Add negative JSON/statistics/fixture tests only where they support the existing M2 contract; defer broad production serialization hardening to later scope.
7. Update `docs/genesisvla/m2_transform_data_contract.md` with batch/mask/source wording and explicit non-M3 boundary.

Required validation for Wave 2:

- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -v`
- `runs/tmp/m1-tool-venv/bin/pyright --project pyrightconfig.genesisvla.json`
- `make genesis-check`
- `git diff --check`

## Compatibility assessment

Architecture compatibility:

- Data Wave 1 does not modify core contracts.
- The only baseline core Pyright item is `genesisvla/core/types/action.py:51`; it remains Architecture-owned under `GVLA-M2-CORE-TYPING-001`.
- Data Wave 2 should consume the canonical core array/action typing result and avoid redefining M1 `RawSample`, `ActionChunk`, `BatchSample`, `ModelInput`, or action mask semantics in core.
- The proposed Data `CollatedBatch` is additive and Data-local, so it does not force a breaking public protocol change.

Quality compatibility:

- Data Wave 1 does not modify toolchain or gate configuration.
- Data Wave 2 assumes Quality canonical integration keeps strict Pyright coverage, reproducible build tooling, and affected M2 file inclusion.
- The recommended fixes use typed local boundaries and contracts, not Pyright exclusions, blanket `type: ignore`, or config weakening.

Known coordination sequencing:

- Architecture and Quality have active isolated Wave 1 writer tasks in scratch scopes.
- Canonical Data writes should remain serial after those integrations so the same Pyright baseline is not being modified by multiple writers at once.

## Subagent retirement ledger

| Subagent | Agent id | Scope | Output | Output collected | Risks summarized | Retired |
| --- | --- | --- | --- | --- | --- | --- |
| D-RO1 | `019ef452-2216-7521-8c99-1e4571d8bd69` | Classify all remaining Pyright errors | `runs/tmp/GVLA-M2-UNBLOCK-001/data/error-clusters.md` | yes | yes | yes |
| D-RO2 | `019ef452-22df-7d12-af38-52ef2b26512b` | Propose typed batch/action-mask/source contract | `runs/tmp/GVLA-M2-UNBLOCK-001/data/batch-mask-contract.md` | yes | yes | yes |
| D-RO3 | `019ef452-23db-7010-b403-2ae7e162f6ce` | Audit JSON/config/statistics/fixture typing and test gaps | `runs/tmp/GVLA-M2-UNBLOCK-001/data/test-gap-inventory.md` | yes | yes | yes |

Note: D-RO3 reported that it corrected an initial report-path placement slip before finalizing. Final collected artifacts are under the allowed `runs/tmp/GVLA-M2-UNBLOCK-001/data/**` path.

## DevSpace MCP compliance

PASS. Data Wave 1 did not use DevSpace MCP, `vla-flywheel-devspace`, MCP connector workspace operations, `open_workspace`, MCP read/write/edit/bash, or any DevSpace evidence path. Work used local shell reads, approved multi-agent subagents, and writes only to the allowed report/evidence paths.

## Parallelism note

Wave 1 used three read-only inspectors in parallel because the task card explicitly allowed parallel read-only Data inspectors and their outputs were disjoint. No parallel writes to source/tests/tooling occurred. Wave 2 should use one serial Data write worker (`D-W1`) after Architecture and Quality canonical integrations pass.

## Files written by Data Wave 1

- `runs/tmp/GVLA-M2-UNBLOCK-001/data/error-clusters.md`
- `runs/tmp/GVLA-M2-UNBLOCK-001/data/batch-mask-contract.md`
- `runs/tmp/GVLA-M2-UNBLOCK-001/data/test-gap-inventory.md`
- `coordination/reports/GVLA-M2-DATA-TYPING-001/owner-data-wave1.md`

No source, test, tooling, feature-list, completion-state, git staging, commit, push, PR, merge, stash, reset, restore, clean, or rm operation was performed by the Owner.

## Conclusion

PASS

Data Wave 1 read-only discovery is complete. Branch/HEAD verification passed, all required inputs were read, all three read-only inspectors completed and were retired, and the Wave 2 D-W1 plan is ready for Manager sequencing after Architecture and Quality canonical integrations pass.
