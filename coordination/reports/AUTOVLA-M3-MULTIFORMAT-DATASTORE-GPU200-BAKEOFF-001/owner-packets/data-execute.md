# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Data Execute Packet

## Role

You are `30-OWNER · Data`.

This is the sole source writer for the data-store tranche.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
Do not create child write-capable subagents.
No parallel source writes.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`

Before writing, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

Required branch/head context:

- branch must be `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- current base/head before execution planning is `3573930421a2f9be66b222d602db680a77aadf3f`

## Source dataset and working roots

- source dataset (read-only only):
  `/home/cz-jzb/workspace/vla-flywheel/datasets/readonly/black-rubber-bellows-0622-0623-768-cmd-256-30hz`
- working dataset root:
  `/home/cz-jzb/workspace/vla-flywheel/datasets/working/autovla_multiformat_bakeoff_gpu200`
- ignored evidence root:
  `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/`

Never mutate `datasets/readonly/**`.
Never write generated artifacts outside `datasets/working/**` and `runs/tmp/**`.

## Allowed write scope

- `autovla/dataloader/stores/**`
- `tests/dataloader/**`
- `configs/dataloader/multiformat_bakeoff.yaml`
- `docs/benchmarks/**` only if needed for schema/report stubs, not final result claims
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute.md`

Do not write:

- `autovla/training/**`
- `scripts/slurm/**`
- `configs/training/**`
- `requirements/**`
- `pyproject.toml`
- `Makefile`
- `README.md`

## Planning decisions already approved

- Shared sample/window manifest is the single fairness source.
- `autovla/dataloader/stores/**` is the correct new implementation surface.
- Reuse existing `autovla/dataloader/perf/**` and `autovla/dataloader/format_pipeline/**` concepts, but do not hardwire old task ids or old report wording.
- Root project-local toolenv is approved for direct validation:
  `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python`
- WebDataset dependency is already present in the approved project-local env.
- LeRobot v3 may remain explicit `NOT_RUN_DEPENDENCY_BLOCKED` if no honest offline comparable route exists without new dependency/governance changes.
- Robo-DM must remain AutoVLA-native/prototype-owned, not upstream package support.

## Required deliverables in this tranche

Implement the data-store layer and load-benchmark scaffold for the four mandatory candidates:

1. `zjh_lerobot_v21_raw`
2. `zjh_lerobot_v3_local`
3. `zjh_webdataset_tar`
4. `zjh_robodm_container_v1`

Minimum required source surfaces:

- shared manifest contract
- candidate build/read contracts
- artifact ledger helpers
- load-benchmark executor
- JSON/CSV/Markdown table rendering for load benchmark

Expected module targets:

- `autovla/dataloader/stores/common.py`
- `autovla/dataloader/stores/sample_window_manifest.py`
- `autovla/dataloader/stores/lerobot_v21_reader.py`
- `autovla/dataloader/stores/lerobot_v3_builder.py`
- `autovla/dataloader/stores/lerobot_v3_reader.py`
- `autovla/dataloader/stores/webdataset_builder.py`
- `autovla/dataloader/stores/webdataset_reader.py`
- `autovla/dataloader/stores/robodm_manifest.py`
- `autovla/dataloader/stores/robodm_builder.py`
- `autovla/dataloader/stores/robodm_reader.py`
- `autovla/dataloader/stores/robodm_style.py`
- `autovla/dataloader/stores/artifact_ledger.py`
- `autovla/dataloader/stores/benchmark.py`
- `autovla/dataloader/stores/report.py`

Manager may accept close layout adaptation if behavior is preserved.

## Behavioral requirements

### Shared manifest

Create deterministic shared sample/window manifest support with fields required by the task prompt, including:

- `manifest_version`
- `dataset_root`
- `source_format`
- `seed`
- `max_episodes`
- `max_samples`
- `window_size`
- `camera_views`
- `action_horizon`
- `action_dim`
- `selected_episodes`
- `selected_sample_ids`
- `selected_window_ids`
- `language_present_count`
- `state_present_count`
- `camera_ref_count`
- `checksum`

The manifest must be the sole fairness source across all candidates.

### Raw candidate

- Real runnable baseline.
- Read source dataset in read-only mode.
- No conversion.
- No source cache.
- Use the shared manifest.

### LeRobot v3 candidate

- Prefer honest offline route only.
- If no safe comparable offline route exists without new dependency/runtime changes, implement explicit blocked-row behavior with:
  - candidate id present in all outputs
  - status `NOT_RUN_DEPENDENCY_BLOCKED`
  - exact blocker reason
- Do not fake comparability.

### WebDataset candidate

- Use current approved `webdataset` route if importable from the root project-local env.
- Build deterministic tar shards under the working root.
- Emit shard index and sample index.
- Preserve same sample/window ids.
- If a true reader benchmark cannot run safely, degrade honestly with explicit status and reason.

### Robo-DM-style candidate

- Implement AutoVLA-native prototype-owned container/index route.
- No upstream package coupling.
- Preserve sample/window ids, action/state/language, and 3 camera refs.
- Keep it explicitly prototype-owned in metadata/reporting.

### Tables and artifacts

Emit load benchmark tables in:

- JSON
- CSV
- Markdown

and an artifact ledger entry structure compatible with the task prompt.

Do not update README final dashboard here unless needed for a local stub; final README integration belongs after telemetry.

## Tests required in this tranche

Use tiny fixtures only.
No real dataset in unit tests.

Add/update focused tests for:

- manifest schema and determinism
- raw candidate manifest validation
- LeRobot v3 blocked-row semantics or local-style manifest if actually implemented
- WebDataset shard grouping and index schema
- Robo-DM-style manifest/container/index schema
- candidate sample/window id preservation
- 3 RGB camera ref preservation
- action/language/state/action_mask validation
- benchmark table JSON/CSV/Markdown rendering
- artifact ledger structure
- source dataset path rejected as output root
- generated candidate outputs not staged by default contract helpers

## Validation commands

Use direct root project-local toolenv commands, not worktree-relative wrapper paths:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile $(rg --files autovla/dataloader/stores tests/dataloader | tr '\n' ' ')`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -v`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check --config 'line-length=100' autovla/dataloader/stores tests/dataloader`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores tests/dataloader`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright -p pyrightconfig.autovla.json`
- `git diff --check`

If a command fails, record the exact command and failure.

## Required report

Write exactly one owner report:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute.md`

The report must include:

- workspace verification
- files changed
- what was implemented
- validation commands run and results
- any honest blocked candidate rows and reasons
- subagent retirement ledger

Allowed conclusion values:

- `PASS`
- `REQUEST_CHANGES`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `READY_FOR_USER_DECISION_FORMAT_DEPENDENCY`
