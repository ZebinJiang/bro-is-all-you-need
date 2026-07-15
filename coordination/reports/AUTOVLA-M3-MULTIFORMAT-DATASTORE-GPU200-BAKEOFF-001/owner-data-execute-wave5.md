# AUTOVLA-M3-MULTIFORMAT-DATASTORE-GPU200-BAKEOFF-001 · Owner Data Execute Wave 5

Role: `30-OWNER · Data`

## 1. Workspace Verification

- `pwd`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse --show-toplevel`: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/autovla-multiformat-datastore-gpu200-bakeoff`
- `git branch --show-current`: `dev/feat-autovla-multiformat-datastore-gpu200-bakeoff`
- `git rev-parse HEAD`: `3573930421a2f9be66b222d602db680a77aadf3f`
- `git status --short --branch`: pre-existing Wave 2/Wave 4 WIP remained present outside Wave 5 scope; this wave changed only the allowed files below

## 2. Exact Source-Contract Diagnosis

Wave 4 compute narrowed the active blocker to a real runtime/data-contract mismatch in `autovla/dataloader/stores/common.py`:

- failing path: `_build_source_sample(...)`
- prior behavior: `camera_refs = tuple(require_str(raw.get(camera), camera) for camera in CAMERA_VIEWS)`
- failure observed on compute:
  - `ValueError: observation.images.left_wrist_rgb must be a non-empty string`
- Manager-provided real-data inspection showed the camera columns are not empty, but mapping-shaped values such as:
  - `{"path": "videos/...mp4", "timestamp": 0.0}`

So the source contract bug was not "missing camera data"; it was that the loader only accepted fixture-style string refs and rejected the real mapping-shaped camera payload surface.

## 3. Files Changed

- `autovla/dataloader/stores/common.py`
- `tests/dataloader/test_multiformat_datastore_bakeoff.py`

No other source, config, docs, dataset, or benchmark-runtime files were modified in this wave.

## 4. Repair Summary

### `autovla/dataloader/stores/common.py`

- added `_coerce_camera_ref(...)`
- preserved existing support for non-empty string camera refs
- added support for mapping-shaped camera refs with a required non-empty string `path`
- kept `SourceSample.camera_refs` as `tuple[str, str, str]`
- kept fail-closed behavior for malformed values

New fail-closed behavior is field-specific:

- mapping without a usable path raises:
  - `observation.images.<camera>.path must be a non-empty string`
- non-string, non-mapping values raise:
  - `observation.images.<camera> must be a non-empty string or mapping with path`

### `tests/dataloader/test_multiformat_datastore_bakeoff.py`

- kept the original string-based tiny fixture path alive
- added a focused success case for mapping-shaped camera refs
- added a focused fail-closed case for malformed mapping refs
- extended `_tiny_zjh_fixture(...)` with a bounded `camera_ref_mode` switch for string, mapping, and malformed-mapping test coverage

## 5. Contract Outcome

- string fixtures remain supported: yes
- mapping-shaped camera refs are now supported: yes
- malformed mapping refs still fail closed: yes

This wave intentionally did **not** widen camera semantics beyond extracting a stable string path from the real mapping-shaped payload.

## 6. Validation Commands And Results

### Syntax

- ` /home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m py_compile autovla/dataloader/stores/common.py tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - result: PASS

### Focused tests

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m pytest tests/dataloader/test_multiformat_datastore_bakeoff.py -v`
  - result: PASS
  - summary: `6 passed in 0.41s`

### Ruff

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m ruff check autovla/dataloader/stores/common.py tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - result: PASS

### Changed-file Black check

- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 autovla/dataloader/stores/common.py`
  - result: PASS
- `/home/cz-jzb/workspace/vla-flywheel/runs/tmp/m1-tool-venv/bin/python -m black --check --line-length 100 --workers 1 tests/dataloader/test_multiformat_datastore_bakeoff.py`
  - result: PASS

### Diff hygiene

- `git diff --check`
  - result: PASS

## 7. Wave 5 Scope Notes

- DevSpace MCP used: no
- child subagents used: none
- retired: yes
- no parallel source writes: yes

This wave stayed inside the packet-authorized write scope and did not modify:

- other datastore builder/reader files
- configs
- docs/README
- datasets/readonly
- datasets/working
- compute wrappers
- training or telemetry surfaces

## Conclusion

`PASS`

Wave 5 repaired the exact compute-proven runtime blocker by teaching `_build_source_sample(...)` to accept both fixture-style string camera refs and real mapping-shaped camera refs with a non-empty `path`, while preserving fail-closed behavior for malformed mappings. Focused syntax, test, lint, format, and diff checks passed inside the allowed scope.
