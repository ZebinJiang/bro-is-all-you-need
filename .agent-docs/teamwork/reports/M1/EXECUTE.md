# M1 EXECUTE: Core Contract + Typed Config

| Field | Value |
| --- | --- |
| Milestone | M1 |
| Stage | EXECUTE |
| Date | 2026-06-18 |
| Manager | Codex |
| Recommended next stage | VERIFY with 1x `code_reviewer` |

## 1. Worker Dispatch Summary

Claude approved one serial write-capable worker:

```text
Worker type: coding_integration_engineer
Count: 1
Mode: serial
Scope: create all in-scope M1 artifacts, run TDD red-green and validation, capture evidence.
Writable paths: PLAN Section 2.1 whitelist only.
Read-only paths: all others.
```

Manager dispatched worker `019eda1d-2542-7751-b330-b71948d07f90` (`McClintock`) with the
approved whitelist, TDD red-green sequence, numpy-only/no-torch rule, frozen+slots dataclass rule,
governance update requirements, and no Slurm/push/PR authority.

Worker returned `DONE_WITH_CONCERNS`:

- Implemented M1 core types, protocols, registry, compatibility adapter, config schema, loader,
  preset, tests, and governance updates.
- Captured red/green TDD summary, green test evidence, Ruff evidence, path notes, complexity notes,
  and rollback notes.
- Reported concerns for exact `make genesis-check` Black timeout and repo-local Pyright package
  discovery in this sandbox.
- After Manager diagnostic review found strict-mode code issues, the same worker fixed them inside
  the approved whitelist. The worker was then retired.

Worker did not preserve the full red traceback output. The red command/status summary is recorded in
Section 3 as the retained evidence limitation.

## 2. Changed Files

M1 intended changed files and sizes after worker completion:

| Path | Size bytes |
| --- | ---: |
| `genesisvla/core/types/__init__.py` | 625 |
| `genesisvla/core/types/sample.py` | 2461 |
| `genesisvla/core/types/action.py` | 2595 |
| `genesisvla/core/types/modality.py` | 733 |
| `genesisvla/core/types/framework.py` | 1463 |
| `genesisvla/core/protocols/__init__.py` | 304 |
| `genesisvla/core/protocols/framework.py` | 542 |
| `genesisvla/core/protocols/runner.py` | 783 |
| `genesisvla/core/protocols/policy.py` | 458 |
| `genesisvla/core/registry/__init__.py` | 339 |
| `genesisvla/core/registry/registry.py` | 2655 |
| `genesisvla/core/registry/errors.py` | 326 |
| `genesisvla/core/compat/__init__.py` | 135 |
| `genesisvla/core/compat/legacy_sample.py` | 3037 |
| `genesisvla/config/schema/__init__.py` | 475 |
| `genesisvla/config/schema/base.py` | 348 |
| `genesisvla/config/schema/model.py` | 594 |
| `genesisvla/config/schema/data.py` | 725 |
| `genesisvla/config/schema/runner.py` | 1932 |
| `genesisvla/config/schema/experiment.py` | 1003 |
| `genesisvla/config/loader/__init__.py` | 658 |
| `genesisvla/config/loader/load_yaml.py` | 855 |
| `genesisvla/config/loader/merge_cli.py` | 936 |
| `genesisvla/config/loader/validate.py` | 5495 |
| `genesisvla/config/loader/export.py` | 1699 |
| `genesisvla/config/loader/legacy_omegaconf.py` | 1640 |
| `genesisvla/config/presets/local_debug.yaml` | 348 |
| `tests/core/__init__.py` | 42 |
| `tests/core/test_raw_sample.py` | 2761 |
| `tests/core/test_action.py` | 1354 |
| `tests/core/test_registry.py` | 1242 |
| `tests/config/__init__.py` | 42 |
| `tests/config/test_loader.py` | 1822 |
| `Makefile` | 995 |
| `pyrightconfig.genesisvla.json` | 379 |
| `.pre-commit-config.yaml` | 1093 |
| `.github/workflows/genesisvla.yml` | 1080 |
| `pyproject.toml` | 2560 |
| `tests/meta/test_repo_policy.py` | 3559 |

Pre-existing dirty/untracked paths from M0/governance state remain present and were not reverted:
`.github/PULL_REQUEST_TEMPLATE.md`, `.gitignore`, `docs/genesisvla/*`, `scripts/teamwork/*`,
`genesisvla/__init__.py`, `genesisvla/core/__init__.py`, `genesisvla/config/__init__.py`,
`genesisvla/py.typed`, `tests/meta/*`, and deleted `docs/agent_skills/...` template files.

## 3. RED Pytest Evidence

Mandatory tests-first command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH python -m pytest tests/core tests/config -v
```

Retained worker output:

```text
Status:
RED, expected failure before implementation.

Scope:
tests/core and tests/config were created first, then this command was run before implementing
the M1 artifacts.

Most specific retained failure summary:
The tests failed because the GenesisVLA M1 modules/contracts they imported were not implemented yet.
The worker did not retain the verbatim traceback text.
```

Evidence limitation: the full red traceback was not preserved by the worker. Manager did not
reconstruct it after implementation because doing so would require artificial source movement or a
non-equivalent temporary environment.

## 4. GREEN Pytest Evidence

Manager rerun:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH python -m pytest tests/core tests/config -v
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

============================== 14 passed in 0.16s ==============================
```

## 5. `make genesis-check` Evidence

Attempt:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 90s make genesis-check
```

Output:

```text
black --check --line-length 100 --workers 1 genesisvla tests/meta tests/core tests/config
Aborted!
All done! ✨ 🍰 ✨
37 files would be left unchanged.
```

Exit code: `124` from `timeout`. The command reached Black, Black reported clean formatting after
timeout termination, and Make did not advance to Ruff/Pyright/pytest before the timeout. This is
consistent with the M0 Black multi-path sandbox tooling issue.

Fallback checks:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH; for path in $(find genesisvla tests/meta tests/core tests/config -name '*.py' | sort); do black --check --quiet --line-length 100 --workers 1 "$path" || exit 1; done; echo 'black per-file PASS'
```

```text
black per-file PASS
```

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH ruff check --config 'line-length=100' genesisvla tests/meta tests/core tests/config
```

```text
All checks passed!
```

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH python -m pytest tests/meta/test_repo_policy.py tests/core tests/config -v
```

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

============================== 18 passed in 0.16s ==============================
```

Venv-aware strict Pyright diagnostic:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pyright -p /tmp/m1-pyright-check/pyrightconfig.json
```

```text
0 errors, 0 warnings, 0 informations
```

## 6. V1-V6 Manager Validation Results

### V1: File Existence

Command: PLAN Section 9 V1 file-existence script.

Output:

```text
V1 PASS
```

Result: `PASS`.

### V2: Core And Config Tests

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH python -m pytest tests/core tests/config -v
```

Output: see Section 4.

Result: `PASS`, `14 passed`.

### V3: Meta Policy Tests

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH python -m pytest tests/meta/test_repo_policy.py -v
```

Output:

```text
============================= test session starts ==============================
platform linux -- Python 3.12.13, pytest-9.1.0, pluggy-1.6.0 -- /tmp/vla-flywheel-m0-tools/bin/python
cachedir: .pytest_cache
rootdir: /home/cz-jzb/workspace/vla-flywheel
configfile: pyproject.toml
collecting ... collected 4 items

tests/meta/test_repo_policy.py::test_should_have_genesisvla_docs PASSED  [ 25%]
tests/meta/test_repo_policy.py::test_should_have_make_genesis_check PASSED [ 50%]
tests/meta/test_repo_policy.py::test_should_have_pyright_strict_config PASSED [ 75%]
tests/meta/test_repo_policy.py::test_should_have_pr_template_with_test_plan PASSED [100%]

============================== 4 passed in 0.02s ===============================
```

Result: `PASS`.

### V4: Full GenesisVLA Gate

Command:

```bash
PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH timeout 90s make genesis-check
```

Result: `PASS_WITH_TOOLING_NOTE` for implementation evidence, but exact Make command timed out with
exit `124` at the Black multi-path step. Fallback Black/Ruff/Pyright-diagnostic/pytest checks all
passed. Claude should rerun `make genesis-check` externally during VERIFY, as planned.

### V5: Pyright Strict

Required command:

```bash
VIRTUAL_ENV=/tmp/vla-flywheel-m0-tools PATH=/tmp/vla-flywheel-m0-tools/bin:$PATH pyright -p pyrightconfig.genesisvla.json
```

Output begins:

```text
/home/cz-jzb/workspace/vla-flywheel/genesisvla/config/loader/export.py
  /home/cz-jzb/workspace/vla-flywheel/genesisvla/config/loader/export.py:8:6 - error: Import "omegaconf" could not be resolved (reportMissingImports)
/home/cz-jzb/workspace/vla-flywheel/genesisvla/core/compat/legacy_sample.py
  /home/cz-jzb/workspace/vla-flywheel/genesisvla/core/compat/legacy_sample.py:8:8 - error: Import "numpy" could not be resolved (reportMissingImports)
/home/cz-jzb/workspace/vla-flywheel/tests/core/test_action.py
  /home/cz-jzb/workspace/vla-flywheel/tests/core/test_action.py:4:8 - error: Import "pytest" could not be resolved (reportMissingImports)
142 errors, 0 warnings, 0 informations
```

Result: `ENV_BLOCKED` for the exact repo-local command in this Codex sandbox. A venv-aware
diagnostic Pyright config under `/tmp/m1-pyright-check` resolves the same code and returns:

```text
0 errors, 0 warnings, 0 informations
```

No hardcoded temp venv path was added to `pyrightconfig.genesisvla.json`.

### V6: Path Boundary

Command:

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

Result: `PASS_WITH_PREEXISTING_DIRTY_NOTE`.

- M1 worker modified only approved M1 whitelist paths.
- No `starVLA/`, `code-input/`, `datasets/`, `runs/`, `configs/slurm/`, legacy
  `pyrightconfig.json`, checkpoints, source archives, or secrets changed.
- `.gitignore`, PR template, M0 docs/stubs, scripts wrapper, and deleted `docs/agent_skills/...`
  template paths were pre-existing dirty state and were not reverted.

## 7. Complexity And Performance Notes

- Raw sample conversion is linear in the number of keys/modalities and uses `np.asarray` only at the
  legacy input boundary.
- Action validation is constant time relative to array payload size; it reads shape metadata only.
- Registry lookup and membership are O(1); deterministic listing sorts keys in O(n log n).
- Config load/export is linear in the size of the small OmegaConf container.
- No torch, GPU, distributed runtime, Slurm, StarVLA import, model implementation, runner loop, or
  checkpoint behavior was added.
- Frozen dataclasses do not deep-freeze numpy arrays; this is an accepted M1 contract limitation and
  should be documented/reviewed in VERIFY.

## 8. Code-Input Adaptation And Attribution

None. M1 uses original minimal contracts and does not copy or adapt source from
`code-input/FluxVLA-main.zip` or `code-input/dexbotic-main.zip`.

## 9. Worker Coverage Ledger Status

| Stage | Required coverage | EXECUTE status |
| --- | --- | --- |
| EXECUTE | 1x `coding_integration_engineer`, serial, write-capable, whitelist only | Completed and retired |
| VERIFY | 1x `code_reviewer`, read-only, independent review | Pending Claude gate |
| REVIEW | Manager synthesis plus independent review evidence and final gates | Pending |

## 10. Residual Risks

- Full red traceback evidence is missing because the worker did not retain it. The red status and
  command summary are recorded, but not the verbatim traceback.
- Exact `make genesis-check` timed out in the Codex sandbox at Black multi-path execution. Fallback
  checks passed, but Claude should provide external full-gate evidence in VERIFY.
- Exact repo-local `pyright -p pyrightconfig.genesisvla.json` cannot discover temp venv packages in
  this sandbox and exits with missing-import cascades. Venv-aware diagnostic Pyright over the same
  code reports 0 errors.
- Current worktree remains dirty from earlier M0/governance artifacts and unrelated deleted
  `docs/agent_skills/...` templates. Publication must separate intended M1/M0 files from unrelated
  deletions before staging.
- M1 adds only contracts and schema; it does not validate real model/data/runner behavior.

## 11. Rollback Notes

Before publication, rollback M1 with:

```bash
rm -rf genesisvla/core/types
rm -rf genesisvla/core/protocols
rm -rf genesisvla/core/registry
rm -rf genesisvla/core/compat
rm -rf genesisvla/config/schema
rm -rf genesisvla/config/loader
rm -rf genesisvla/config/presets
rm -rf tests/core
rm -rf tests/config
git restore -- Makefile pyrightconfig.genesisvla.json .pre-commit-config.yaml .github/workflows/genesisvla.yml pyproject.toml tests/meta/test_repo_policy.py
```

Because several governance files are currently untracked or modified from earlier M0 work,
publication/rollback should first identify the intended staged set.

## 12. Recommended Next Stage

Recommend entering `VERIFY` with the approved independent worker:

```text
Worker type: code_reviewer
Count: 1
Mode: serial
Read-only: entire repository
Scope: independently review M1 code/tests/configs/gates for correctness, no torch, no code-input
copying, license cleanliness, Chinese docstrings, frozen+slots, registry semantics, config loader
behavior, path safety, and complexity.
```

VERIFY should also obtain Claude/external evidence for:

- full `make genesis-check`;
- repo-local `pyright -p pyrightconfig.genesisvla.json` in an environment where Pyright can discover
  installed `numpy`, `omegaconf`, and `pytest`.
