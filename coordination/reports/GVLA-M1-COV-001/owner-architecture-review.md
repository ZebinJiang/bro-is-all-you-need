# GVLA-M1-COV-001 Architecture Review

Owner: 20-OWNER Architecture
Mode: ARCHITECTURE_REVIEW
Date: 2026-06-22

## Review conclusion

APPROVE

The GVLA-M1-COV-001 test additions are acceptable Architecture evidence for direct M1 public contract coverage. The reviewed tests cover the requested public contracts without expanding their public API shape or changing Protocol semantics. No Architecture blocker is required.

## Files reviewed

- `AGENTS.md`
- `boundaries.txt`
- `docs/coordination/CODEX_MANAGER_GOVERNANCE.md`
- `docs/coordination/MANAGER_ENTRYPOINT.md`
- `docs/coordination/TEAM_OPERATING_MODEL.md`
- `coordination/PROGRAM_STATE.yaml`
- `coordination/TASK_INDEX.yaml`
- `coordination/THREAD_REGISTRY.yaml`
- `coordination/tasks/active/GVLA-M1-COV-001.yaml`
- `coordination/reports/GVLA-M1-COV-001/owner-quality.md`
- `genesisvla/core/types/sample.py`
- `genesisvla/core/types/framework.py`
- `genesisvla/core/protocols/framework.py`
- `genesisvla/core/protocols/runner.py`
- `genesisvla/core/protocols/policy.py`
- `tests/core/test_raw_sample.py`
- `tests/core/test_framework_contract.py`
- `tests/core/test_protocol_contracts.py`

## Findings ordered by severity

- None blocking.
- Residual workspace note: `git status` currently shows broader non-task state, including `A .agent-docs/feature_list.json`, modified `Makefile` and `pyproject.toml`, untracked `pyrightconfig.genesisvla.json`, untracked `genesisvla/`, and untracked new tests/reports. This Architecture review does not approve those broader root/protected/source states; it only approves the GVLA-M1-COV-001 direct coverage evidence as reviewed against the task card and Quality report. Because `genesisvla/` is untracked in the current worktree, git cannot independently distinguish pre-existing M1 source state from task-local state, so the scope assessment relies on reviewed source contents plus the Quality Owner report that no `genesisvla/**`, Makefile, root pyright config, pyproject, or feature-list edits were made for this task.

## Contract coverage assessment

The new tests accurately cover the remaining M1 public contracts named by the task card:

- `BatchSample`: `tests/core/test_raw_sample.py` covers construction from ordered `RawSample` values, empty-batch rejection, `batch_size`, and metadata pass-through. This matches `genesisvla/core/types/sample.py` without adding contract requirements beyond existing fields and validation.
- `ModelInput`: `tests/core/test_framework_contract.py` covers direct `BatchSample` carriage, default empty `tensors`/`metadata`, and preservation of supplied tensor and metadata mappings. This matches `genesisvla/core/types/framework.py`.
- `FrameworkOutput`: `tests/core/test_framework_contract.py` covers total loss, named losses, metrics, optional `action_pred`, and numpy-backed `LossValue`. This matches the current dataclass contract and does not require new behavior.
- `FrameworkProtocol`: `tests/core/test_protocol_contracts.py` covers `forward(ModelInput) -> FrameworkOutput` and `predict_action(ModelInput) -> ActionChunk` through a structurally matching fake implementation.
- `RunnerProtocol`: `tests/core/test_protocol_contracts.py` covers `setup`, `train`, `evaluate`, `save_checkpoint`, and `resume` through explicit Protocol annotation and lifecycle calls.
- `PolicyProtocol`: `tests/core/test_protocol_contracts.py` covers `reset` and `select_action(ModelInput) -> ActionChunk` through explicit Protocol annotation and calls.

Quality evidence reviewed: Quality Owner reports focused pytest `21/21 passed` and project-local wrapper PASS, including py_compile, pytest `42/42`, Black, Ruff, and Pyright.

## Scope/protected-path assessment

The reviewed test files are additive/direct coverage for existing contracts. They do not require changes to `genesisvla/**` public implementation behavior, public dataclass fields, Protocol method signatures, `Makefile`, `pyrightconfig.genesisvla.json`, `pyproject.toml`, or `.agent-docs/feature_list.json` for GVLA-M1-COV-001 acceptance.

The current worktree has broader dirty/untracked state in some protected or root paths, as noted above. That state is outside this review's approval boundary and should be managed by Manager/Quality under the owning task or milestone publication flow. It is not a blocker for accepting these tests as M1 direct coverage evidence, provided the Manager keeps the approval scoped to GVLA-M1-COV-001 test coverage only.

## Protocol testing assessment

Protocol testing uses structural typing through explicit Protocol annotations, e.g. assigning fake implementations to `FrameworkProtocol`, `RunnerProtocol`, and `PolicyProtocol` variables before exercising required methods. The reviewed protocol tests do not use `runtime_checkable`, Protocol runtime `isinstance`, or `issubclass`, and the Protocol source files remain plain `typing.Protocol` definitions with no runtime-checkable decoration. This preserves Protocol semantics and avoids turning static structure contracts into runtime API requirements.

## M1 evidence acceptability

Acceptable as M1 project-local direct coverage evidence for `BatchSample`, `ModelInput`, `FrameworkOutput`, `FrameworkProtocol`, `RunnerProtocol`, and `PolicyProtocol`, when paired with the Quality Owner validation evidence already recorded in `coordination/reports/GVLA-M1-COV-001/owner-quality.md`.

## Required follow-up

None required for APPROVE.

Non-blocking Manager note: retain the approval boundary in downstream synthesis so broader dirty/untracked root/source/config state is not accidentally treated as approved by this Architecture review.

## Subagent retirement ledger

No subagents used. No subagent contexts created; none required retirement.

## Parallelism proposal/actual

Proposal: read-only review only; no parallel writes.
Actual: read-only file reads and read-only inspections were allowed to run in parallel. The only write was this single Architecture review report at the Manager-requested path; no code, source, config, task card, Makefile, pyright config, pyproject, feature-list, commit, push, PR, or thread-state writes were performed.
