# M1 EXECUTE-FIX-2 Report - legacy_sample Metadata Contract Fix

Milestone: M1 - Core Contract + Typed Config
Stage: EXECUTE-FIX-2
Manager: Codex Manager
Timestamp: 2026-06-18T18:59:31+08:00
Recommendation: `VERIFY-2`

## 1. Worker Dispatch Summary

Approved worker:

- Worker type: `coding_integration_engineer`
- Count: 1
- Mode: serial
- Agent id: `019eda57-2008-7e80-8a9b-f88ea8d2588f`
- Agent nickname: Hooke
- Scope: fix legacy sample metadata contract and update its test.
- Writable paths:
  - `genesisvla/core/compat/legacy_sample.py`
  - `tests/core/test_raw_sample.py`

Worker completed and was retired. It reported modifying only the two approved paths. It did not run Slurm, push, open PRs, mark completion state, or launch subworkers.

## 2. Before: Reviewer Finding

The M1 VERIFY independent reviewer found one blocking contract defect:

`genesisvla/core/compat/legacy_sample.py::from_legacy_dict` did not preserve `robot_tag` or top-level `episode_id` into `RawSample.metadata` as M1 PLAN Section 6.8 requires.

Approved contract:

- Start metadata from `payload["metadata"]` when it is a mapping.
- Preserve at least `robot_tag`.
- Preserve any top-level `episode_id`.
- Do not drop existing user metadata keys.

## 3. Exact Targeted Diff

The M1 files are still untracked in this worktree, so `git diff` cannot produce a normal tracked-file hunk for only this scoped fix. The exact targeted before/after hunk is recorded below.

`genesisvla/core/compat/legacy_sample.py`:

```diff
@@
     metadata_robot_tag = metadata.get("robot_tag")
     robot_value = payload.get("robot_tag", metadata_robot_tag if metadata_robot_tag else "unknown")
     robot_tag = str(robot_value)
+    metadata["robot_tag"] = robot_tag
+    if "episode_id" in payload and "episode_id" not in metadata:
+        metadata["episode_id"] = payload["episode_id"]

     sample = RawSample(
         images=images,
```

`tests/core/test_raw_sample.py`:

```diff
@@
 def test_should_preserve_robot_tag_metadata() -> None:
-    """验证机器人标识和元数据按输入保留。"""
+    """验证机器人标识会同步写入元数据且保留已有元数据。"""
     from genesisvla.core.compat.legacy_sample import from_legacy_dict
@@

     assert sample.robot_tag == "libero"
-    assert sample.metadata == {"episode_id": "ep-001"}
+    assert sample.metadata["robot_tag"] == "libero"
+    assert sample.metadata["episode_id"] == "ep-001"
+
+
+def test_should_preserve_top_level_episode_id_metadata() -> None:
+    """验证顶层 episode_id 会补入缺省元数据。"""
+    from genesisvla.core.compat.legacy_sample import from_legacy_dict
+
+    sample = from_legacy_dict(
+        _legacy_payload(
+            episode_id="ep-top",
+            metadata={"source": "legacy"},
+        )
+    )
+
+    assert sample.metadata["episode_id"] == "ep-top"
+    assert sample.metadata["source"] == "legacy"
```

Current changed lines:

```text
legacy_sample.py:83 metadata["robot_tag"] = robot_tag
legacy_sample.py:84 if "episode_id" in payload and "episode_id" not in metadata:
legacy_sample.py:85     metadata["episode_id"] = payload["episode_id"]
test_raw_sample.py:81 assert sample.robot_tag == "libero"
test_raw_sample.py:82 assert sample.metadata["robot_tag"] == "libero"
test_raw_sample.py:83 assert sample.metadata["episode_id"] == "ep-001"
test_raw_sample.py:86 test_should_preserve_top_level_episode_id_metadata
```

## 4. Validation Evidence

### 4.1 `pytest tests/core/test_raw_sample.py -v`

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/core/test_raw_sample.py -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 5 items

tests/core/test_raw_sample.py::test_should_create_raw_sample_from_legacy_dict PASSED [ 20%]
tests/core/test_raw_sample.py::test_should_validate_required_modalities PASSED [ 40%]
tests/core/test_raw_sample.py::test_should_reject_invalid_action_shape PASSED [ 60%]
tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata PASSED [ 80%]
tests/core/test_raw_sample.py::test_should_preserve_top_level_episode_id_metadata PASSED [100%]

============================== 5 passed in 0.09s ===============================
```

Result: PASS.

### 4.2 `pytest tests/core tests/config -v`

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/core tests/config -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 15 items

tests/core/test_action.py::test_should_validate_action_chunk_shape PASSED [  6%]
tests/core/test_action.py::test_should_reject_invalid_action_mask_shape PASSED [ 13%]
tests/core/test_action.py::test_should_create_action_space PASSED        [ 20%]
tests/core/test_raw_sample.py::test_should_create_raw_sample_from_legacy_dict PASSED [ 26%]
tests/core/test_raw_sample.py::test_should_validate_required_modalities PASSED [ 33%]
tests/core/test_raw_sample.py::test_should_reject_invalid_action_shape PASSED [ 40%]
tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata PASSED [ 46%]
tests/core/test_raw_sample.py::test_should_preserve_top_level_episode_id_metadata PASSED [ 53%]
tests/core/test_registry.py::test_should_register_and_get_item PASSED    [ 60%]
tests/core/test_registry.py::test_should_reject_duplicate_registry_key PASSED [ 66%]
tests/core/test_registry.py::test_should_raise_clear_error_for_missing_registry_key PASSED [ 73%]
tests/config/test_loader.py::test_should_load_yaml_into_experiment_config PASSED [ 80%]
tests/config/test_loader.py::test_should_apply_cli_dotlist_override PASSED [ 86%]
tests/config/test_loader.py::test_should_emit_clear_error_on_invalid_backend PASSED [ 93%]
tests/config/test_loader.py::test_should_export_resolved_yaml PASSED     [100%]

============================== 15 passed in 0.17s ==============================
```

Result: PASS.

### 4.3 Combined pytest fallback

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pytest tests/meta tests/core tests/config -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 19 items

tests/meta/test_repo_policy.py::test_should_have_genesisvla_docs PASSED  [  5%]
tests/meta/test_repo_policy.py::test_should_have_make_genesis_check PASSED [ 10%]
tests/meta/test_repo_policy.py::test_should_have_pyright_strict_config PASSED [ 15%]
tests/meta/test_repo_policy.py::test_should_have_pr_template_with_test_plan PASSED [ 21%]
tests/core/test_action.py::test_should_validate_action_chunk_shape PASSED [ 26%]
tests/core/test_action.py::test_should_reject_invalid_action_mask_shape PASSED [ 31%]
tests/core/test_action.py::test_should_create_action_space PASSED        [ 36%]
tests/core/test_raw_sample.py::test_should_create_raw_sample_from_legacy_dict PASSED [ 42%]
tests/core/test_raw_sample.py::test_should_validate_required_modalities PASSED [ 47%]
tests/core/test_raw_sample.py::test_should_reject_invalid_action_shape PASSED [ 52%]
tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata PASSED [ 57%]
tests/core/test_raw_sample.py::test_should_preserve_top_level_episode_id_metadata PASSED [ 63%]
tests/core/test_registry.py::test_should_register_and_get_item PASSED    [ 68%]
tests/core/test_registry.py::test_should_reject_duplicate_registry_key PASSED [ 73%]
tests/core/test_registry.py::test_should_raise_clear_error_for_missing_registry_key PASSED [ 78%]
tests/config/test_loader.py::test_should_load_yaml_into_experiment_config PASSED [ 84%]
tests/config/test_loader.py::test_should_apply_cli_dotlist_override PASSED [ 89%]
tests/config/test_loader.py::test_should_emit_clear_error_on_invalid_backend PASSED [ 94%]
tests/config/test_loader.py::test_should_export_resolved_yaml PASSED     [100%]

============================== 19 passed in 0.20s ==============================
```

Result: PASS.

## 5. `make genesis-check` Result and Fallback

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s make genesis-check
```

Output:

```text
black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config
Aborted!
Aborted!
All done! ✨ 🍰 ✨
37 files would be left unchanged.
```

Exit code: 124.

Assessment: this is the same known Codex sandbox Black timeout/abort behavior documented in M0/M1. Black reported that all files would be left unchanged, but `timeout` still killed the command before `make` advanced to Ruff/Pyright/pytest.

Fallback commands:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s black --check --line-length 100 --workers 1 genesisvla
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s black --check --line-length 100 --workers 1 tests/meta
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s black --check --line-length 100 --workers 1 tests/core
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s black --check --line-length 100 --workers 1 tests/config
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s black --check --line-length 100 --workers 1 genesisvla/core/compat/legacy_sample.py tests/core/test_raw_sample.py
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pyright -p pyrightconfig.genesisvla.json
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 60s pytest tests/meta tests/core tests/config -v
```

Fallback results:

- `black ... tests/meta`: exit 0; `2 files would be left unchanged`.
- `black ... tests/config`: exit 0; `2 files would be left unchanged`.
- `black ... genesisvla`: exit 124 after `All done!` and `29 files would be left unchanged`.
- `black ... tests/core`: exit 124 after `All done!` and `4 files would be left unchanged`.
- `black ... legacy_sample.py tests/core/test_raw_sample.py`: exit 124 after `All done!` and `2 files would be left unchanged`.
- `ruff check ...`: exit 0; `All checks passed!`
- `pyright -p pyrightconfig.genesisvla.json`: exit 1 with the known 142 dependency-resolution diagnostics from this Codex sandbox.
- `pytest tests/meta tests/core tests/config -v`: exit 0; 19 passed.

Conclusion: the scoped fix is test-green and Ruff-clean in the deps-present environment. Full `make genesis-check` still requires Claude/external dependency-present validation because this Codex sandbox reproduces the already-documented Black/Pyright environment issues.

## 6. Path Boundary

Targeted status:

```text
?? genesisvla/core/compat/legacy_sample.py
?? tests/core/test_raw_sample.py
```

Full status at validation time:

```text
 M .github/PULL_REQUEST_TEMPLATE.md
 M .gitignore
 M Makefile
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/data_config.py
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/modality.json
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/model2bench_interface.py
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/run_train.sh
D  docs/agent_skills/integrate-starvla-dataset/assets/templates/training_config.yaml
 M pyproject.toml
?? .github/workflows/
?? .pre-commit-config.yaml
?? docs/genesisvla/
?? genesisvla/
?? pyrightconfig.genesisvla.json
?? scripts/
?? tests/
```

Notes:

- The scoped worker was authorized to write only `legacy_sample.py` and `test_raw_sample.py`.
- Those paths are part of the currently untracked M1 deliverable tree, so Git reports them as untracked rather than as tracked diffs.
- Existing broader M0/M1 dirty and untracked paths remain present and were not reverted.
- No `starVLA/`, `code-input/`, `datasets/`, `runs/`, Slurm config, secrets, or unrelated source paths were touched by this fix.

## 7. Complexity and Risk

- Complexity change is O(1): two metadata key assignments in an already-created dictionary.
- No large-array copy, tensor movement, GPU behavior, Slurm behavior, or runtime dependency change was introduced.
- Residual risk is limited to external gate rerun in a dependency-present environment because this sandbox still cannot complete full `make genesis-check` cleanly.

## 8. Rollback Notes

Rollback this scoped fix by reverting only:

- the `metadata["robot_tag"]` assignment;
- the top-level `episode_id` backfill block;
- the updated assertions in `test_should_preserve_robot_tag_metadata`;
- the added `test_should_preserve_top_level_episode_id_metadata`.

No config, dependency, StarVLA, dataset, Slurm, or governance behavior must be reverted for this fix.

## 9. Recommended Next Stage

Recommended next stage: `VERIFY-2`.

Suggested VERIFY-2 scope:

- Re-review only `genesisvla/core/compat/legacy_sample.py` and `tests/core/test_raw_sample.py`.
- Confirm the Section 6.8 metadata contract is now satisfied.
- Re-state pytest evidence: `test_raw_sample.py` 5 passed, `tests/core tests/config` 15 passed, combined suite 19 passed.
- Claude may optionally run external `make genesis-check` for final full-gate evidence.
