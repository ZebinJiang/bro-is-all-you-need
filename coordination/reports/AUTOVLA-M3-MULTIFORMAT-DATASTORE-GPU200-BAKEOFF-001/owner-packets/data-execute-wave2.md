# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Packet · Data Execute Wave 2

You are `30-OWNER · Data`.

Workspace:
- `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`

Branch / HEAD expected at dispatch:
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`

Execution mode:
- write-capable owner execution
- single writer
- no parallel source writes
- no DevSpace MCP

Model / reasoning for Manager dispatch:
- `model=gpt-5.4`
- `thinking=high`

## First read

1. `AGENTS.md`
2. `boundaries.txt`
3. `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
4. `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
5. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-plan.md`
6. `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute.md`
7. `autovla/dataloader/stores/**`
8. `autovla/dataloader/perf/**`
9. `autovla/dataloader/format_pipeline/**`

## Workspace verification required in report

Before normal task content, record:
- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`
- `git status --short --branch`

If branch/HEAD/workspace do not match, stop and write only the failure notice.

## Why this wave exists

Wave 1 delivered a good scaffold, but it is not enough for the actual goal.

Current gaps Manager verified:
- `autovla/dataloader/stores/benchmark.py` has no real CLI entrypoint for governed compute execution.
- `configs/dataloader/multiformat_bakeoff.yaml` is still missing.
- `datasets/working/autovla_multiformat_bakeoff_gpu200/**` has not been populated.
- `zjh_lerobot_v3_local` was left as `NOT_RUN_DEPENDENCY_BLOCKED`, but the top-level goal explicitly allows an AutoVLA-native local v2.1-to-v3-style route when the official package is unavailable.
- current load-benchmark rows are still scaffold-level and do not yet satisfy the full numeric field set needed for the real compute bakeoff.

## Your exact objective in Wave 2

Upgrade the datastore scaffold into a real compute-runnable bounded bakeoff path for the data side.

Deliver:

1. a governed config surface:
   - `configs/dataloader/multiformat_bakeoff.yaml`

2. a compute-runnable CLI/module surface for:
   - shared sample/window manifest creation
   - candidate artifact build
   - candidate load benchmark
   - JSON / CSV / Markdown table emission
   - generated artifact ledger emission

3. real bounded support for these candidates:
   - `zjh_lerobot_v21_raw`
   - `zjh_webdataset_tar`
   - `zjh_robodm_container_v1`

4. a serious attempt at:
   - `zjh_lerobot_v3_local`
   using an AutoVLA-native local v2.1-to-v3-style converter/reader
   without adding dependencies

5. focused tests that prove the new bounded contracts

Do not touch README or docs in this wave unless a narrowly scoped source-owned table-render helper absolutely requires a doc fixture update. Default: no README/docs writes in this wave.

## Allowed write scope for this wave

- `autovla/dataloader/stores/**`
- `configs/dataloader/multiformat_bakeoff.yaml`
- `tests/dataloader/**`
- `datasets/working/autovla_multiformat_bakeoff_gpu200/**`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`

## Forbidden in this wave

- `autovla/training/telemetry/**`
- `README.md`
- `docs/benchmarks/**`
- `requirements/**`
- `pyproject.toml`
- `Makefile`
- `datasets/readonly/**`
- checkpoint/model/network/HF/W&B/endpoint/robot mutations

## Required implementation direction

### A. Shared manifest

Keep one deterministic shared sample/window manifest as the single fairness source.

Required path:
- `datasets/working/autovla_multiformat_bakeoff_gpu200/multiformat_bakeoff/multiformat_sample_window_manifest.json`

It must be reusable by later Compute/HPC and Training waves.

### B. Real runnable candidate paths

#### raw
- remain read-only over the source dataset
- produce validation and benchmark artifacts without writing under source root

#### webdataset
- use the already available governed `webdataset` dependency route
- produce deterministic shard names, sample index, shard index, and real reader benchmark support

#### robodm_style
- remain AutoVLA-owned prototype
- produce deterministic container/index/manifest/checksum outputs

#### lerobot_v3_local
- do not stop at package-missing alone
- first try an AutoVLA-native local v3-style artifact/reader route
- if you still must block it, the blocked reason must be concrete and format-contract-specific, not just "dependency missing"

### C. Compute-runnable surface

Manager expects a direct module entrypoint such as:
- `python -m autovla.dataloader.stores ...`
or an equivalent explicit CLI under the same allowed scope.

The compute side must not need ad hoc inline Python snippets to run the bakeoff.

### D. Numeric outputs

Emit machine-readable tables that later waves can consume directly:
- JSON
- CSV
- Markdown

The fields do not need to be fully documented in README in this wave, but the data contract must be stable enough for later README/docs publication.

### E. Generated artifact safety

All generated candidate artifacts must stay under:
- `datasets/working/autovla_multiformat_bakeoff_gpu200/**`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/**`

No generated dataset/tar/container artifact may become tracked in git.

## Validation you must run locally

Use the root project-local toolenv directly:

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile <changed_python_files>`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader -q`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check autovla/dataloader/stores tests/dataloader`
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/pyright --venvpath /home/cz-jzb/workspace/vla-flywheel/runs/tmp -p pyrightconfig.autovla.json autovla/dataloader/stores tests/dataloader`
- `git diff --check`

If directory-level Black hangs again, use the same honest file-by-file fallback pattern and record exactly which files were checked.

## Required report

Write only:
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`

The report must contain:

1. Workspace verification
2. Files changed
3. What became compute-runnable
4. Whether `zjh_lerobot_v3_local` is now runnable or still blocked
5. Exact output roots used
6. Validation commands and results
7. Generated-artifact tracking safety status
8. DevSpace MCP compliance
9. Subagent retirement ledger
10. Conclusion:
   - `PASS`
   - or `REQUEST_CHANGES`
   - or `BLOCKED_SCOPE`
   - or `BLOCKED_TOOL_ENV`

## Manager decision for this wave

Do not stop at scaffold improvements alone.
Do not stop at a package-missing explanation for LeRobot v3.
Produce a compute-runnable datastore wave that the later Compute/HPC owner can actually execute.
