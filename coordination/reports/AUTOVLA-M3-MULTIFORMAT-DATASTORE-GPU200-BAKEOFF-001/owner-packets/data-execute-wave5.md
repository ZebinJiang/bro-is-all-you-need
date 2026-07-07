# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 Data Execute Wave 5 Packet

## Role

You are `30-OWNER · Data`.

Use:

- model: `gpt-5.4`
- thinking: `high`

Do not use DevSpace MCP.
No parallel write.
No child write-capable subagents.

## Workspace

- worktree: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- branch: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- expected HEAD: `3573930421a2f9be66b222d602db680a77aadf3f`

Before acting, verify:

- `pwd`
- `git rev-parse --show-toplevel`
- `git branch --show-current`
- `git rev-parse HEAD`

## Allowed write scope

This is a narrow source repair wave.

You may modify only:

- `autovla/dataloader/stores/common.py`
- `tests/dataloader/test_multiformat_datastore_bakeoff.py`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave5.md`

You may write task-local scratch or evidence only under:

- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/data-wave5/**`

Do not modify:

- any other `autovla/dataloader/stores/**` file
- `autovla/training/**`
- `configs/**`
- `scripts/**`
- `README.md`
- `docs/**`
- `datasets/readonly/**`
- `datasets/working/**`
- `/home/cz-jzb/workspace/Isaac-GR00T17/**`

## Required prior evidence

Read before execution:

- `coordination/tasks/active/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001.yaml`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave2.md`
- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-compute-execute-wave4.md`
- `runs/tmp/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/compute/reduced-store-benchmark/benchmark_runtime_failure.md`

## Manager read-only diagnosis you must honor

The Wave 4 runtime blocker is now concrete and narrow:

1. the narrowed benchmark launch succeeded on compute;
2. the failure is not scheduler policy anymore;
3. the failure occurred in:
   - `autovla/dataloader/stores/common.py`
   - `_build_source_sample(...)`
   - current line family around `camera_refs = tuple(require_str(raw.get(camera), camera) for camera in CAMERA_VIEWS)`
4. the error text was:
   - `ValueError: observation.images.left_wrist_rgb must be a non-empty string`

Manager also performed a read-only bounded dataset inspection:

- real ZJH parquet camera fields are not strings;
- they are mapping objects shaped like:
  - `{\"path\": \"videos/...mp4\", \"timestamp\": 0.0}`
- lightweight aggregate check over the source dataset found:
  - `empty = 0`
  - `none = 0`
  - total rows inspected per camera field = `188404`

Interpretation:

- the current loader is rejecting the real dataset schema because it expects `str`
- the immediate fix is a source-contract repair, not a dataset cleanup and not a compute-policy issue

## Objective of this wave

Repair the datastore source-sample loader so the real ZJH v2.1 camera reference schema is accepted without mutating the source dataset.

Keep the behavioral change narrow:

1. preserve current support for fixture-style string camera refs;
2. add support for real-dataset mapping camera refs that contain a non-empty `path` string;
3. keep `SourceSample.camera_refs` as `tuple[str, str, str]`;
4. fail closed on malformed values with exact field-specific errors;
5. do not widen into new benchmark/report/runtime semantics.

## Implementation requirements

Implement the smallest correct contract repair in `autovla/dataloader/stores/common.py`.

Expected behavior after repair:

- if a camera field is a non-empty string, accept it unchanged;
- if a camera field is a mapping with a non-empty string `path`, extract that path;
- if a camera field is a mapping but `path` is missing or empty, raise a clear field-specific `ValueError`;
- if a camera field is any other type, raise a clear field-specific `ValueError`.

Do not silently drop rows.
Do not mutate parquet payloads.
Do not invent fallback paths.
Do not relax unrelated language/action/state validation.

## Test requirements

Update `tests/dataloader/test_multiformat_datastore_bakeoff.py` to cover:

1. existing string-based tiny fixture path still passes;
2. a tiny fixture with mapping-shaped camera refs also passes;
3. malformed mapping camera ref without valid `path` fails with a field-specific error.

Keep tests tiny-fixture only.
Do not run compute jobs in this wave.

## Validation requirements

Run only lightweight validation:

1. `py_compile` on changed Python files
2. focused pytest:
   - `tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
3. optionally one additional narrow local reproduction under `runs/tmp/.../data-wave5/` if needed, but no heavy benchmark and no Slurm
4. `ruff check` on changed files if the repo toolenv supports it
5. `git diff --check`

Do not run compute-node jobs.
Do not rerun the real benchmark in this wave.
Manager will route the next compute retry after your repair lands.

## Report requirements

Write:

- `coordination/reports/AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001/owner-data-execute-wave5.md`

Include:

1. workspace verification
2. exact source-contract diagnosis
3. files changed
4. validation commands and results
5. whether string fixtures remain supported
6. whether mapping-shaped camera refs are now supported
7. whether malformed mapping refs still fail closed
8. DevSpace MCP compliance
9. subagent retirement ledger

## Allowed conclusions

Use one of:

- `PASS`
- `BLOCKED_TEST`
- `BLOCKED_SCOPE`
- `FAIL`

Guidance:

- correct narrow fix plus focused tests pass:
  - `PASS`
- fix would require edits outside the allowed files:
  - `BLOCKED_SCOPE`
- focused tests or syntax/lint validation fail:
  - `BLOCKED_TEST`
