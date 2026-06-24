# GVLA-M2-FINAL-CLOSURE-001 Owner Architecture Wave 1 Plan

## Decision

PASS_PLAN.

Architecture recommends Manager proceed with Wave 1 synthesis after collecting the remaining Owner plans. Wave 2 should remain serial: Q-W1 fixture dependency/bootstrap work first, then D-W1 data implementation, followed by Architecture/Quality review.

## Workspace verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- git root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m2-transform-data-contract-v2-restacked`
- branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- HEAD: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- required branch: `dev/feat-m2-transform-data-contract-v2-restacked`
- required base head: `53449a8e3d667998f8ffd0c5e09aa0e2947de29f`
- workspace_check: PASS.
- `git status --short` showed existing Manager/Owner coordination and report evidence plus final-closure task cards. Architecture did not modify source, tests, dependencies, workflows, PR body, git index, feature_list, task state, or M3 code.

## Files written by Architecture

- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/architecture/final-contract-review.md`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/owner-architecture-wave1-plan.md`

No other file was changed by this Architecture planning pass.

## Reviewed evidence

- `coordination/tasks/active/GVLA-M2-FINAL-CLOSURE-001.yaml`
- `coordination/tasks/active/GVLA-M2-FINAL-DATA-001.yaml`
- `coordination/tasks/active/GVLA-M2-FIXTURE-DEPS-001.yaml`
- `runs/tmp/GVLA-M2-FINAL-CLOSURE-001/findings.yaml`
- `coordination/reports/GVLA-M2-FINAL-CLOSURE-001/wave0-manager-preflight.md`
- `coordination/reports/GVLA-M2-HARDEN-001/manager-summary.md`
- `.agent-docs/feature_list.json` M2 section, read-only for context only
- `docs/genesisvla/m2_transform_data_contract.md`
- `docs/genesisvla/adr/ADR-001-m2-upstream-design-selection.md`
- `docs/references/upstream_sources.yaml`
- `genesisvla/core/types/sample.py`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/transforms/action_mode.py`
- `genesisvla/dataloader/transforms/image.py`
- `genesisvla/dataloader/transforms/state_action.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/testing/fixtures/tiny.py`

## Contract decisions

Full acceptance contract details are in:

`runs/tmp/GVLA-M2-FINAL-CLOSURE-001/architecture/final-contract-review.md`

Architecture decisions:

- F2.7 PASS requires generated actual LeRobot-format fixture evidence with `real_format=true`; current `lerobot-like-in-memory` evidence remains PARTIAL only.
- F2.8 PASS requires generated actual `.parquet` files written/read during tests with `real_format=true`; current `parquet-like-in-memory` mappings remain PARTIAL only.
- LeRobot policy: pin a LeRobot v3 file-format target exactly in docs/provenance. Do not use floating `latest`. Full LeRobot package dependency is not mandatory and should remain out of scope unless Q-W1 justifies and pins it.
- Relative `ActionModeTransform` policy: M2 relative mode accepts only one-dimensional numeric `sample.state`; multidimensional/temporal state must fail clearly. No implicit flattening or state slicing fallback.
- Bool-mask policy: action masks and statistics masks must reject numeric/string/object coercion. Accept bool arrays and Python bool-only sequences only, then copy to owned `np.bool_` arrays.
- These changes are not M1 breaking changes. They are acceptable M2 Draft hardening before final acceptance, though some draft tests/callers may need updates.

## Required Architecture review points for Q-W1

- Dependency additions are exact-pinned with license/provenance and wheelhouse evidence.
- PyArrow or equivalent remains test/quality scoped and does not become a core API dependency.
- Project-local offline bootstrap and fresh-runner CI semantics remain strict.
- No global Python, `/tmp` tool env, broad source build, blanket ignore, or diagnostic hiding is introduced.
- Workflow/cache policy does not cache venvs or broad `runs/tmp/**`.
- Existing genesis/governance/build gates are preserved.
- No generated Parquet/MP4/dataset binary is staged or packaged.

## Required Architecture review points for D-W1

- Generated real LeRobot-format and Parquet fixtures are created under `tmp_path` or governed `runs/tmp/**`, loaded from files, schema-validated, and adapted to `RawSample`.
- Fixture provenance records exact format/version/revision, `real_format=true`, `source=project-generated`, and `license=project-generated`.
- Malformed real fixtures fail clearly without fallback to in-memory helpers.
- Old in-memory helpers are renamed/labeled as lookalikes if retained.
- Collator image modality comparison uses key sets and deterministic ordering.
- Action masks and statistics masks are strict bool-only.
- `ImageNormalize` rejects non-finite mean/std and non-positive std.
- Relative action mode rejects multidimensional/temporal state under the M2 one-dimensional policy.
- Statistics reject negative std, max < min, numeric valid_mask coercion, empty names, duplicate names, and incomplete/contradictory invariants.
- CPU E2E covers generated real fixture -> `RawSample` -> transforms -> collate -> statistics cache -> inverse/roundtrip without M3 model/training behavior.

## Breaking-change risk

No accepted M1 contract is changed. M2 Draft behavior will tighten:

- numeric/string masks that were previously coerced to bool must now fail;
- multidimensional relative state must now fail;
- real-format fixture APIs may require explicit generated-file helpers or renaming old in-memory helpers.

Architecture classifies these as non-blocking draft-hardening changes required before M2 final acceptance, not as stable public API breaks.

## DevSpace MCP compliance

PASS. This Owner used local shell/project-file inspection only. DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP read/write/edit, and MCP bash were not used as workflow or evidence.

## Subagent retirement ledger

- A-RO1: used yes.
- Agent id: `019ef7dd-9ff9-78f2-83f8-599847f208ff`.
- Task: read-only acceptance-contract planning.
- Completed output: none; the subagent did not return before two wait windows.
- Retirement: yes; closed by Architecture Owner, previous status `running`.
- Compensating evidence: direct Owner review of required files and Manager findings.

## Parallelism

Wave 1 planning is read-only and may remain parallel across Owners. Architecture performed no parallel write. Wave 2 must preserve single-writer order: Quality dependency writer first, then Data implementation writer.

## Manager handoff

Manager may proceed with Wave 1 synthesis after other Owner plans arrive. Architecture recommends dispatching Q-W1 only after synthesis, then D-W1 only after Q-W1 PASS/Architecture review confirms dependency/bootstrap safety.
