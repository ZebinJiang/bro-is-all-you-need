# GVLA-M1-CONTRACT-002 Owner Architecture Report

## Workspace Verification

- pwd: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m1-closure-integration`
- git_root: `/home/cz-jzb/workspace/vla-flywheel/.worktrees/m1-closure-integration`
- branch: `dev/m1-closure-integration`
- head: `a244c96c4dc8638033be1e8c555c39e0b77c12b3`
- workspace_check: `PASS`
- initial_git_status_short:
  - `?? coordination/tasks/active/GVLA-M1-CI-002.yaml`
  - `?? coordination/tasks/active/GVLA-M1-CONTRACT-002.yaml`

The required root, branch, and HEAD matched. The two untracked task cards were
preserved as task context and were not staged, committed, removed, or modified.

## Decision

`PASS`

The public config dataclass constructor invariant blocker was real and has been
resolved with a minimal M1-scope config/schema fix plus focused tests. No M2,
CI bootstrap, publication, feature-list pass, code-input, dataset, dataloader,
model, training, deployment runtime, or acceleration runtime work was performed.

## Files Inspected

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `coordination/tasks/active/GVLA-M1-CONTRACT-002.yaml`
- `docs/genesisvla/rfc_000_architecture.md`
- `docs/genesisvla/coding_standard.md`
- `docs/genesisvla/testing_standard.md`
- `genesisvla/config/schema/base.py`
- `genesisvla/config/schema/experiment.py`
- `genesisvla/config/schema/model.py`
- `genesisvla/config/schema/data.py`
- `genesisvla/config/schema/runner.py`
- `genesisvla/config/schema/deployment.py`
- `genesisvla/config/schema/acceleration.py`
- `genesisvla/config/loader/validate.py`
- `genesisvla/config/loader/load_yaml.py`
- `genesisvla/config/loader/merge_cli.py`
- `genesisvla/config/loader/export.py`
- `genesisvla/config/schema/__init__.py`
- `tests/config/test_loader.py`
- `tests/core/**` as needed for gate scope and public contract interaction

## Files Changed

- `genesisvla/config/schema/base.py`
- `genesisvla/config/schema/experiment.py`
- `genesisvla/config/schema/model.py`
- `genesisvla/config/schema/data.py`
- `genesisvla/config/schema/runner.py`
- `genesisvla/config/schema/deployment.py`
- `genesisvla/config/schema/acceleration.py`
- `tests/config/test_loader.py`
- `coordination/reports/GVLA-M1-CONTRACT-002/owner-architecture.md`

## Constructor Invariant Assessment

Before this task, the loader/build path rejected invalid values, unknown keys,
and CLI typo overrides, but the public dataclass constructors themselves still
accepted invalid direct construction. Examples of the blocker included direct
construction of non-empty/string/int/positive invariants such as:

- `ExperimentConfig(name="")`
- `ExperimentConfig(seed=True)` or `ExperimentConfig(seed=-1)`
- `ModelConfig(name="")`
- `DataConfig(required_modalities=())`
- `RunnerConfig(batch_size=0)`
- `RunnerConfig(learning_rate=0.0)`
- `RunnerConfig(grad_accumulation_steps=1.5)`
- `DeploymentConfig(timeout=0.0)`
- `AccelerationConfig(enabled="yes")`

The fix adds constructor-time `__post_init__` validation to the public M1 config
dataclasses while keeping the existing public semantics:

- schema version must be string `"1.0"`;
- required strings must be strings and non-empty;
- integer fields reject bool, float, string, and must satisfy positivity where
  the M1 contract requires it;
- numeric fields reject bool and strings and must satisfy positivity where
  required;
- bool fields reject non-bool values;
- required modalities must be a non-empty tuple/list of non-empty strings;
- nested `ExperimentConfig` sections must be the expected config dataclass
  types;
- `RunnerConfig.backend` direct-constructor value must be `RunnerBackend`.

`build_experiment_config(...)` and YAML/dotlist flows continue to perform their
existing normalization and validation. This task did not change unknown-key
semantics, package/gate scope, CI bootstrap, M2 scope, or runtime behavior.

## Validation Command Results

- `bash scripts/quality/genesis_check_project_local.sh`: `PASS`
  - product py_compile: `PASS`
  - product pytest: `92 passed`
  - product Black file-list: `PASS`
  - product Ruff: `PASS`
  - product Pyright: `0 errors, 0 warnings`
  - governance py_compile: `PASS`
  - governance pytest: `18 passed`
  - governance Black: `PASS`
  - governance Ruff: `PASS`
- `runs/tmp/m1-tool-venv/bin/python -m pytest tests/config tests/core tests/meta -v`:
  `PASS`, `86 passed`
- `git diff --check`: `PASS`, no whitespace errors
- `git status --short`: completed; changed files are limited to allowed
  `genesisvla/config/**`, `tests/config/**`, and this report path, with the
  two pre-existing untracked task cards still present.

## Residual Risks

- This task intentionally does not stage, commit, push, create PRs, bootstrap
  CI, publish, or mark M1 complete.
- The worktree contains untracked task cards for `GVLA-M1-CI-002` and
  `GVLA-M1-CONTRACT-002`; they were present at workspace verification and remain
  outside this Owner's source-change decision.
- `RunnerConfig(backend="local")` is rejected in direct dataclass construction;
  string backend normalization remains supported through the loader/build path,
  where existing tests confirm `runner.backend=ddp` works.

## Required Quality Review Items

- Confirm public config dataclass direct constructors now reject invalid values
  without lowering strictness or adding blanket ignores.
- Confirm loader/YAML/dotlist public semantics remain stable.
- Confirm no M2, CI bootstrap, feature-list pass, code-input, dataloader, model,
  training, dataset, deployment runtime, acceleration runtime, staging, commit,
  push, or PR action occurred.
- Re-run or accept the recorded wrapper and focused pytest validation.

## DevSpace MCP Compliance

`PASS`

No DevSpace MCP, `vla-flywheel-devspace`, MCP connector, `open_workspace`, MCP
read/write/edit/bash, global dependency install, `/tmp` tool environment,
system/conda/user-shell modification, stage, commit, push, merge, PR, force
push, stash apply/drop/pop, M2 worktree, code-input, dataset, or protected-path
workflow was used.

## Subagent Retirement Ledger

None used. This narrow Architecture task was completed directly and serially in
the specified closure worktree.

## Parallelism / No Parallel Write Note

No parallel writes. Read-only file reads and validation commands were batched
where safe; all edits were made serially by Architecture Owner within the
allowed write scope.
