# M1 EXECUTE-FIX-1: pytest pythonpath gate fix

| Field | Value |
| --- | --- |
| Milestone | M1 |
| Stage | EXECUTE scoped fix |
| Date | 2026-06-18 |
| Manager | Codex |
| Recommended next stage | VERIFY |

## 1. Scope

Claude identified one real local-gate defect after M1 EXECUTE:

```text
make genesis-check runs bare pytest tests/... rather than python -m pytest.
Without editable install, bare pytest could not import genesisvla and failed with
ModuleNotFoundError: No module named 'genesisvla'.
```

Approved fix:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

Writable path for the worker: `pyproject.toml` only.

## 2. Worker Dispatch Summary

Manager dispatched one approved serial `coding_integration_engineer` worker:

```text
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: apply ONE config fix so make genesis-check's bare pytest can import genesisvla without editable install.
```

Worker returned `DONE_WITH_CONCERNS`:

- Added only the requested `[tool.pytest.ini_options]` table to `pyproject.toml`.
- Confirmed bare pytest now passes.
- Reported full `make genesis-check` proceeds through Black and Ruff but remains blocked at the
  previously documented repo-local Pyright dependency discovery issue.

## 3. Exact `pyproject.toml` Diff

Full tracked diff for `pyproject.toml` currently also includes pre-existing M0/M1 dependency changes.
The scoped fix hunk is only the new pytest table:

```diff
+[tool.pytest.ini_options]
+pythonpath = ["."]
```

Current full `git diff -- pyproject.toml`:

```diff
diff --git a/pyproject.toml b/pyproject.toml
index f90dcb4..c1ce7fa 100644
--- a/pyproject.toml
+++ b/pyproject.toml
@@ -27,6 +27,8 @@ classifiers = [
     "Topic :: Scientific/Engineering :: Artificial Intelligence",
 ]
 dependencies = [
+    "numpy",
+    "omegaconf",
 ]

 [project.optional-dependencies]
@@ -35,6 +37,8 @@ dev = [
     "gpustat",
     "ipython",
     "pre-commit",
+    "pytest",
+    "pyright",
     "ruff>=0.2.2",
 ]
 sagemaker = [
@@ -42,6 +46,8 @@ sagemaker = [
     "sagemaker"
 ]

+[tool.pytest.ini_options]
+pythonpath = ["."]

 [tool.setuptools.packages.find]
 where = ["."]
```

The dependency hunks predate this scoped fix. The worker edited only the pytest config table.

## 4. Before Evidence

Claude external validation before this fix:

```text
pytest tests/core tests/config -v
ModuleNotFoundError: No module named 'genesisvla'
```

Worker retained the same pre-fix signal:

```text
Pre-fix signal: pytest tests/core tests/config -v failed 14/14 with
ModuleNotFoundError: No module named 'genesisvla'.
```

## 5. After Evidence: Bare Pytest

Manager command:

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
collecting ... collected 14 items

tests/core/test_action.py::test_should_validate_action_chunk_shape PASSED [  7%]
tests/core/test_action.py::test_should_reject_invalid_action_mask_shape PASSED [ 14%]
tests/core/test_action.py::test_should_create_action_space PASSED        [ 21%]
tests/core/test_raw_sample.py::test_should_create_raw_sample_from_legacy_dict PASSED [ 28%]
tests/core/test_raw_sample.py::test_should_validate_required_modalities PASSED [ 35%]
tests/core/test_raw_sample.py::test_should_reject_invalid_action_shape PASSED [ 42%]
tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata PASSED [ 50%]
tests/core/test_registry.py::test_should_register_and_get_item PASSED    [ 57%]
tests/core/test_registry.py::test_should_reject_duplicate_registry_key PASSED [ 64%]
tests/core/test_registry.py::test_should_raise_clear_error_for_missing_registry_key PASSED [ 71%]
tests/config/test_loader.py::test_should_load_yaml_into_experiment_config PASSED [ 78%]
tests/config/test_loader.py::test_should_apply_cli_dotlist_override PASSED [ 85%]
tests/config/test_loader.py::test_should_emit_clear_error_on_invalid_backend PASSED [ 92%]
tests/config/test_loader.py::test_should_export_resolved_yaml PASSED     [100%]

============================== 14 passed in 0.19s ==============================
```

Result: `PASS`.

Manager command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/meta/test_repo_policy.py tests/core tests/config -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 18 items

tests/meta/test_repo_policy.py::test_should_have_genesisvla_docs PASSED  [  5%]
tests/meta/test_repo_policy.py::test_should_have_make_genesis_check PASSED [ 11%]
tests/meta/test_repo_policy.py::test_should_have_pyright_strict_config PASSED [ 16%]
tests/meta/test_repo_policy.py::test_should_have_pr_template_with_test_plan PASSED [ 22%]
tests/core/test_action.py::test_should_validate_action_chunk_shape PASSED [ 27%]
tests/core/test_action.py::test_should_reject_invalid_action_mask_shape PASSED [ 33%]
tests/core/test_action.py::test_should_create_action_space PASSED        [ 38%]
tests/core/test_raw_sample.py::test_should_create_raw_sample_from_legacy_dict PASSED [ 44%]
tests/core/test_raw_sample.py::test_should_validate_required_modalities PASSED [ 50%]
tests/core/test_raw_sample.py::test_should_reject_invalid_action_shape PASSED [ 55%]
tests/core/test_raw_sample.py::test_should_preserve_robot_tag_metadata PASSED [ 61%]
tests/core/test_registry.py::test_should_register_and_get_item PASSED    [ 66%]
tests/core/test_registry.py::test_should_reject_duplicate_registry_key PASSED [ 72%]
tests/core/test_registry.py::test_should_raise_clear_error_for_missing_registry_key PASSED [ 77%]
tests/config/test_loader.py::test_should_load_yaml_into_experiment_config PASSED [ 83%]
tests/config/test_loader.py::test_should_apply_cli_dotlist_override PASSED [ 88%]
tests/config/test_loader.py::test_should_emit_clear_error_on_invalid_backend PASSED [ 94%]
tests/config/test_loader.py::test_should_export_resolved_yaml PASSED     [100%]

============================== 18 passed in 0.18s ==============================
```

Result: `PASS`.

## 6. Full Gate Result

Manager command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 180s make genesis-check
```

Output summary:

```text
black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config
All done! ✨ 🍰 ✨
37 files would be left unchanged.
ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config
All checks passed!
pyright -p pyrightconfig.genesisvla.json
...
142 errors, 0 warnings, 0 informations
make: *** [Makefile:30: genesis-check] Error 1
```

Result: `FAIL_AT_PYRIGHT_ENV_DISCOVERY`.

Interpretation:

- This scoped fix succeeded: bare pytest no longer fails with `ModuleNotFoundError`.
- Full Make now reaches Pyright after Black and Ruff pass.
- The remaining failure is the previously documented repo-local Pyright dependency discovery issue in
  this Codex sandbox, not the pytest `pythonpath` defect.
- Venv-aware diagnostic Pyright remains clean:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pyright -p /tmp/m1-pyright-check/pyrightconfig.json
```

```text
0 errors, 0 warnings, 0 informations
```

## 7. Path Boundary

Manager command:

```bash
git status --short --untracked-files=all
```

Output:

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
?? .github/workflows/genesisvla.yml
?? .pre-commit-config.yaml
?? docs/genesisvla/coding_standard.md
?? docs/genesisvla/rfc_000_architecture.md
?? docs/genesisvla/testing_standard.md
?? genesisvla/__init__.py
?? genesisvla/config/__init__.py
?? genesisvla/config/loader/__init__.py
?? genesisvla/config/loader/export.py
?? genesisvla/config/loader/legacy_omegaconf.py
?? genesisvla/config/loader/load_yaml.py
?? genesisvla/config/loader/merge_cli.py
?? genesisvla/config/loader/validate.py
?? genesisvla/config/presets/local_debug.yaml
?? genesisvla/config/schema/__init__.py
?? genesisvla/config/schema/base.py
?? genesisvla/config/schema/data.py
?? genesisvla/config/schema/experiment.py
?? genesisvla/config/schema/model.py
?? genesisvla/config/schema/runner.py
?? genesisvla/core/__init__.py
?? genesisvla/core/compat/__init__.py
?? genesisvla/core/compat/legacy_sample.py
?? genesisvla/core/protocols/__init__.py
?? genesisvla/core/protocols/framework.py
?? genesisvla/core/protocols/policy.py
?? genesisvla/core/protocols/runner.py
?? genesisvla/core/registry/__init__.py
?? genesisvla/core/registry/errors.py
?? genesisvla/core/registry/registry.py
?? genesisvla/core/types/__init__.py
?? genesisvla/core/types/action.py
?? genesisvla/core/types/framework.py
?? genesisvla/core/types/modality.py
?? genesisvla/core/types/sample.py
?? genesisvla/py.typed
?? pyrightconfig.genesisvla.json
?? scripts/teamwork/dispatch_codex_manager.py
?? tests/config/__init__.py
?? tests/config/test_loader.py
?? tests/core/__init__.py
?? tests/core/test_action.py
?? tests/core/test_raw_sample.py
?? tests/core/test_registry.py
?? tests/meta/__init__.py
?? tests/meta/test_repo_policy.py
```

Command:

```bash
git diff --name-only HEAD
```

Output:

```text
.github/PULL_REQUEST_TEMPLATE.md
.gitignore
Makefile
docs/agent_skills/integrate-starvla-dataset/assets/templates/data_config.py
docs/agent_skills/integrate-starvla-dataset/assets/templates/modality.json
docs/agent_skills/integrate-starvla-dataset/assets/templates/model2bench_interface.py
docs/agent_skills/integrate-starvla-dataset/assets/templates/run_train.sh
docs/agent_skills/integrate-starvla-dataset/assets/templates/training_config.yaml
pyproject.toml
```

Path-boundary assessment:

- This scoped fix changed only `pyproject.toml`.
- Other dirty/untracked paths are pre-existing M0/M1 worktree state and were not modified by this
  fix.
- No source, tests, docs, Makefile, workflow, pre-commit, Slurm, dataset, `starVLA/`, or
  `code-input/` paths were edited by this scoped worker.

## 8. Residual Risks

- Repo-local `pyright -p pyrightconfig.genesisvla.json` still fails in this Codex sandbox because
  Pyright does not discover installed `numpy`, `omegaconf`, and `pytest`; this is outside the scoped
  pytest import fix.
- Full `make genesis-check` remains blocked at that Pyright environment issue in this sandbox, even
  though Black, Ruff, and bare pytest now pass.
- Publication still needs clean staging to avoid unrelated deleted `docs/agent_skills/...` paths.

## 9. Rollback

Remove the scoped table from `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
```

Then rerun:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pytest tests/core tests/config -v
```

Expected rollback effect: bare pytest may again fail to import `genesisvla` without editable install.

## 10. Recommended Next Stage

Recommend returning to `VERIFY`.

VERIFY should confirm:

- bare `pytest tests/core tests/config -v` passes without editable install;
- full gate status with a Pyright environment that can discover project dependencies;
- independent `code_reviewer` review remains required by the M1 worker coverage ledger.
