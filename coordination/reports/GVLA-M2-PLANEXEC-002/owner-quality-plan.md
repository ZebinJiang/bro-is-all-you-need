target_branch: dev/m2-transform-data-contract-v2
pwd: /home/cz-jzb/workspace/vla-flywheel
git_root: /home/cz-jzb/workspace/vla-flywheel
branch: dev/m2-transform-data-contract-v2
workspace_check: PASS

# GVLA-M2-PLANEXEC-002 Owner Quality Plan

Decision: QUALITY_PLAN_READY

## Scope And Constraints

- Owner: 60-OWNER - Quality
- Task: GVLA-M2-PLANEXEC-002 - Plan and execute M2 tranche A on a new branch
- Mode: read-only Quality planning plus this report write
- Allowed Quality write used: `coordination/reports/GVLA-M2-PLANEXEC-002/owner-quality-plan.md`
- Source, tests, config, `feature_list`, M1 publication gate: not modified by Quality
- Sibling worktree `/home/cz-jzb/workspace/vla-flywheel-m2-planexec`: not touched
- Stash operations: none; no apply/drop/pop
- M1 publication status: still `BLOCKED_PR_TOOL_OR_AUTH`; do not mark M1 complete
- M2 milestone status: remains incomplete; do not mark M2 complete

## Context Read

Read-only context reviewed:

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `coordination/tasks/active/GVLA-M2-PLANEXEC-002.yaml`
- `docs/genesisvla/rfc_000_architecture.md`
- `docs/genesisvla/coding_standard.md`
- `docs/genesisvla/testing_standard.md`
- `.agent-docs/feature_list.json`
- `scripts/quality/genesis_check_project_local.sh`
- `.agent-docs/git_workflow.md`
- existing `tests/core`, `tests/config`, and `tests/meta`

Task-card note: `coordination/tasks/active/GVLA-M2-PLANEXEC-002.yaml` currently records `status: blocked` and `conclusion: BLOCKED_OWNER_DISPATCH`, but this Quality Owner planning report was explicitly dispatched in the current thread. This report does not mutate the task card.

## Key Quality Findings

- Existing tests use small numpy arrays, direct assertions, Chinese docstrings, explicit Protocol annotation tests, and narrow failure-mode checks. M2 should preserve this test style.
- M2 feature-list entries are all `passes: false`, as required before implementation and publication evidence.
- Current wrapper covers future `genesisvla/dataloader/**` source for Black and Ruff because it scans `genesisvla`.
- Current wrapper does **not** run `tests/dataloader/**` under pytest and does **not** include `tests/dataloader` in generated Pyright config. M2 acceptance must update the wrapper under an approved scope, or record focused `tests/dataloader` pytest and pyright checks as mandatory compensating evidence.
- Tranche A should remain local-only and numpy-only. No dataset downloads, real dataset directories, Slurm submission, model weights, robot endpoints, or external services are needed.

## Tests/Dataloader File Plan

Recommended `tests/dataloader` layout:

- `tests/dataloader/__init__.py`
  - Package marker with Chinese module docstring.
- `tests/dataloader/test_transform_protocol.py`
  - Direct structural checks for `TransformProtocol` using explicit Protocol annotations.
- `tests/dataloader/test_compose_transform.py`
  - Ordered transform chaining, metadata preservation, empty-chain behavior, invalid member rejection, and failure propagation.
- `tests/dataloader/test_state_action_normalization.py`
  - State/action normalize and unnormalize, action mask preservation, zero-std rejection, and statistics shape mismatch rejection.
- `tests/dataloader/test_action_mode_transform.py`
  - Absolute, delta, and relative action mode contracts.
- `tests/dataloader/test_statistics_cache.py`
  - `DatasetStatistics` schema, save/load under pytest `tmp_path`, malformed payload rejection, and no writes outside the explicit temp path.
- Optional Tranche B:
  - `tests/dataloader/test_image_transforms.py`
  - `tests/dataloader/test_mixture_dataset.py`
- Tranche C:
  - Plan-only for now; do not add real LeRobot/Parquet fixture tests until fixture and dependency policy is approved.

## TDD Matrix For Tranche A

| Contract | Preferred test file | Required test functions | Initial expected failure | Acceptance result |
| --- | --- | --- | --- | --- |
| `TransformProtocol` accepts structural fake implementation | `tests/dataloader/test_transform_protocol.py` | `test_should_accept_transform_protocol_implementation` | Missing protocol import or symbol | Explicit annotation works without `runtime_checkable` or `isinstance` |
| Transform applies to `RawSample` | `tests/dataloader/test_transform_protocol.py` | `test_should_apply_transform_to_raw_sample` | Missing callable contract | Metadata or field transform is observable while core sample fields remain valid |
| Transform applies to `BatchSample` | `tests/dataloader/test_transform_protocol.py` | `test_should_apply_transform_to_batch_sample` | Batch contract missing | All samples are transformed in a predictable way |
| `ComposeTransform` applies transforms in order | `tests/dataloader/test_compose_transform.py` | `test_should_apply_compose_transform_in_order` | Compose class missing | Ordered metadata markers or numeric changes prove ordering |
| Empty compose behavior is explicit | `tests/dataloader/test_compose_transform.py` | `test_should_define_empty_compose_behavior` | Behavior undefined | Either identity or clear rejection is documented and tested |
| Compose rejects invalid members | `tests/dataloader/test_compose_transform.py` | `test_should_reject_invalid_compose_member` | Validation missing | Clear `TypeError` or `ValueError` |
| Compose propagates transform errors | `tests/dataloader/test_compose_transform.py` | `test_should_propagate_transform_failure` | Failure handling undefined | Original exception or clear wrapped error is observable |
| State normalization uses `(x - mean) / std` | `tests/dataloader/test_state_action_normalization.py` | `test_should_normalize_state_values` | Normalizer missing | `np.testing.assert_allclose` matches expected small array |
| Action normalization preserves action mask | `tests/dataloader/test_state_action_normalization.py` | `test_should_normalize_action_values_and_preserve_mask` | Mask handling missing | Values normalize; mask object or equal mask is preserved |
| Unnormalization reverses normalization | `tests/dataloader/test_state_action_normalization.py` | `test_should_unnormalize_state_and_action_values` | Unnormalizer missing | Roundtrip equals original arrays |
| Zero std is rejected | `tests/dataloader/test_state_action_normalization.py` | `test_should_reject_zero_statistics_std` | Validation missing | Clear error mentions std/statistics |
| Statistics shape mismatch is rejected | `tests/dataloader/test_state_action_normalization.py` | `test_should_reject_statistics_shape_mismatch` | Validation missing | Clear error mentions shape |
| Absolute action mode is pass-through | `tests/dataloader/test_action_mode_transform.py` | `test_should_keep_absolute_action_mode_values` | Mode transform missing | Values unchanged and mode metadata recorded |
| Delta action mode computes adjacent deltas | `tests/dataloader/test_action_mode_transform.py` | `test_should_convert_actions_to_delta_mode` | Delta conversion missing | Expected diff array matches |
| Relative action mode uses state/reference vector | `tests/dataloader/test_action_mode_transform.py` | `test_should_convert_actions_to_relative_mode` | Relative conversion missing | Expected action-minus-reference result matches |
| Unknown action mode is rejected | `tests/dataloader/test_action_mode_transform.py` | `test_should_reject_unknown_action_mode` | Validation missing | Clear error lists supported modes |
| `DatasetStatistics` preserves named state/action arrays | `tests/dataloader/test_statistics_cache.py` | `test_should_create_dataset_statistics_with_state_and_action_stats` | Schema missing | Mean/std/count fields preserved |
| Statistics cache roundtrips through `tmp_path` | `tests/dataloader/test_statistics_cache.py` | `test_should_save_and_load_statistics_cache_with_tmp_path` | Cache helpers missing | Roundtrip works under pytest temp path only |
| Malformed statistics payload is rejected | `tests/dataloader/test_statistics_cache.py` | `test_should_reject_invalid_statistics_cache_payload` | Validation missing | Clear error on missing or malformed stats |

## Focused Test Command Recommendations

Before Tranche A implementation:

```bash
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -v
```

Expected before implementation: FAIL because M2 modules/contracts are absent.

During implementation, run file-level loops as each contract lands:

```bash
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_transform_protocol.py -v
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_compose_transform.py -v
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_state_action_normalization.py -v
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_action_mode_transform.py -v
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_statistics_cache.py -v
```

Final focused test set:

```bash
runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -v
runs/tmp/m1-tool-venv/bin/python -m pytest tests/core tests/config tests/meta tests/dataloader -v
runs/tmp/m1-tool-venv/bin/python -m py_compile tests/dataloader/test_transform_protocol.py tests/dataloader/test_compose_transform.py tests/dataloader/test_state_action_normalization.py tests/dataloader/test_action_mode_transform.py tests/dataloader/test_statistics_cache.py
```

If `runs/tmp/m1-tool-venv` is unavailable, Manager should route a project-local tooling refresh using `runs/tmp/m2-tool-*` or approved existing project-local environment paths only. Do not use `/tmp` tool environments, global pip, conda base, or system Python modification.

## Full Wrapper Expectations

Current command:

```bash
bash scripts/quality/genesis_check_project_local.sh
```

For M2 acceptance, the wrapper should verify:

- `py_compile` over `tests/meta`, `tests/core`, `tests/config`, and `tests/dataloader`.
- `pytest tests/meta/test_repo_policy.py tests/core tests/config tests/dataloader -v`.
- Black file-list check over `genesisvla`, `tests/meta`, `tests/core`, `tests/config`, and `tests/dataloader`.
- Ruff over `genesisvla`, `tests/meta`, `tests/core`, `tests/config`, and `tests/dataloader`.
- Pyright strict config including `tests/dataloader`.
- Project-local cache/temp only under `runs/tmp/**`.
- `PYTEST_ADDOPTS` controlled by wrapper, not inherited from caller.
- Ruff and Black caches routed under project-local `runs/tmp/**`.

Current wrapper gap: `tests/dataloader` is absent from pytest and Pyright coverage. If wrapper edits are not in the approved write scope for Tranche A, Quality should require both existing wrapper PASS and focused `tests/dataloader` command PASS before accepting the task. If wrapper edits are approved, Architecture/Quality review must verify no public gate is weakened.

## Pre-Commit Scan Requirements

Before any M2 commit, run and record:

```bash
git branch --show-current
git diff --check
git diff --cached --check
git diff --cached --stat
git diff --cached --name-only
```

Then run `.agent-docs/git_workflow.md` scans:

- staged secret-pattern scan
- tracked working-tree secret-pattern scan
- blocked artifact-extension scan over staged files
- large staged-file scan with 50 MiB threshold
- large text-diff scan with 20000-line per-file threshold
- optional `gitleaks detect --source . --redact` if installed

M2-specific forbidden path scan:

```bash
git diff --cached --name-only | grep -E '^(datasets/|runs/|checkpoints/|\.ruff_cache/)|(^|/)(__pycache__|\.pytest_cache|\.ruff_cache)(/|$)|\.(pt|pth|ckpt|safetensors|onnx|bin|parquet|arrow|npy|npz|zip|tar|tar\.gz|tgz|zst|log)$'
```

Expected result: no output. Any match blocks commit unless Manager obtains explicit user override and records risk.

## Artifact / Forbidden Path Safeguards

- Use tiny in-memory numpy arrays in tests.
- Use pytest `tmp_path` only for statistics-cache roundtrip tests.
- Do not write `datasets/**`, `runs/**`, repository root temp files, or system `/tmp` from tests.
- Do not stage `runs/tmp/**`, `.pytest_cache/**`, `.ruff_cache/**`, `__pycache__/**`, logs, archives, parquet/arrow/npy/npz fixture dumps, checkpoints, weights, or model binaries.
- Real LeRobot/Parquet adapters remain Tranche C plan-only until fixture size, provenance, dependency, and storage policy are approved.
- If any future dataset-like fixture is needed, it must be tiny, text-reviewable where possible, and explicitly approved by Data + Quality before staging.

## Tranche A Acceptance Criteria

Tranche A may pass only when:

- Direct tests exist under `tests/dataloader` for every required Tranche A contract.
- Tests are written first and the Owner report records failing-test evidence before implementation.
- Implementation stays inside approved M2-native paths:
  - `genesisvla/core/protocols/transform.py`
  - `genesisvla/core/protocols/__init__.py`
  - `genesisvla/dataloader/__init__.py`
  - `genesisvla/dataloader/transforms/**`
  - `genesisvla/dataloader/statistics/**`
- No real datasets, downloads, Slurm jobs, robot endpoints, model weights, or external services are used.
- Focused `tests/dataloader` pytest passes.
- Existing `tests/core`, `tests/config`, and `tests/meta` still pass.
- Existing wrapper passes, and M2 focused commands compensate for wrapper scope gaps unless wrapper is approved and updated.
- Architecture approves public Protocol/schema boundaries.
- Quality approves focused tests, wrapper evidence, Pyright/Black/Ruff, and artifact scans.
- M1/M2 `passes` fields are not changed by Owner.

## Tranche B Acceptance Criteria

Tranche B may pass only after Tranche A is stable and reviewed:

- Simple image transforms use numpy-only logic or already-approved lightweight dependencies.
- Image transform tests use tiny in-memory arrays and assert shape/dtype/value behavior.
- Fake deterministic mixture sampling uses in-memory sample lists only.
- Mixture tests cover deterministic ordering/weights, invalid weight rejection, and metadata/source preservation.
- Tranche A remains green under focused tests and wrapper.
- Artifact and forbidden-path scans remain clean.

## Tranche C Acceptance Criteria

Tranche C remains plan-only in GVLA-M2-PLANEXEC-002. It may move to implementation only after a new task card approves:

- real LeRobot adapter scope
- real Parquet adapter scope
- fixture provenance, size, and storage policy
- dependency additions, if any
- no-write rules for `datasets/readonly`
- allowed tiny fixture location, if any
- updated wrapper/gate coverage

Future Tranche C acceptance must include adapter contract tests, tiny fixture validation, artifact scans, and Data + Architecture + Quality review. Until then, do not implement or stage real datasets, parquet files, large fixtures, conversion outputs, or streaming dataset behavior.

## DevSpace MCP Compliance

- Quality Owner used DevSpace MCP: no
- Subagents used DevSpace MCP: none
- Evidence depends on DevSpace MCP: no
- Any future M2 prompt, report, skill, or config that requires DevSpace MCP as internal workflow evidence must be treated as a governance violation and block acceptance.

## Subagent Retirement Ledger

- Short-lived Quality subagents used: none
- New Owner threads created: none
- Owner threads archived: none
- Retirement status: no active short-lived contexts remain

## Parallelism Proposal

- Default: `no_parallel_write`
- Planning/review: Data, Architecture, and Quality may perform read-only planning/review in parallel.
- Tranche A implementation: serial Data Owner write only because transforms, statistics, and action-mode transforms share public data behavior.
- Tranche B implementation: may split only after Tranche A stabilizes and only if Manager creates disjoint task cards.
- Tranche C: plan-only; no write workers in this task.

## Current Conclusion

QUALITY_PLAN_READY.

Workspace verification passed for `/home/cz-jzb/workspace/vla-flywheel` on branch `dev/m2-transform-data-contract-v2`. M2 Tranche A should proceed TDD-first with focused `tests/dataloader` coverage, wrapper coverage correction or explicit focused-command compensation, strict artifact safeguards, no stash mutation, no sibling worktree use, no M1 publication-state changes, and no M2 milestone completion in this task.
