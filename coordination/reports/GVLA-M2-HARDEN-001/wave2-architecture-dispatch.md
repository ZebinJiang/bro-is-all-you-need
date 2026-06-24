# GVLA-M2-HARDEN-001 Wave 2 Architecture Dispatch

## Dispatch

- Owner: `10-OWNER - Architecture`
- Thread id: `019eeea4-ddc6-7552-a673-728207c5a1e5`
- Child task: `GVLA-M2-CONTRACT-HARDEN-002`
- Dispatch time: 2026-06-24 Asia/Shanghai session
- Reasoning setting requested: `xhigh`
- Writer mode: single writer.
- Parallel write: none.

## Precondition Evidence

- Q-W1 Quality report: `coordination/reports/GVLA-M2-REMOTE-CI-003/owner-quality.md`, conclusion `PASS`.
- Q-W1 Architecture review: `coordination/reports/GVLA-M2-REMOTE-CI-003/owner-architecture-review.md`, decision `APPROVE`.
- Wave 1 Architecture plan: `runs/tmp/GVLA-M2-HARDEN-001/architecture/contract-plan.md`, conclusion `REQUEST_CHANGES`.
- Manager amended `GVLA-M2-CONTRACT-HARDEN-002` scope to include `statistics/schema.py`, `collate.py`, and focused tests before this dispatch.

## Allowed Write Scope

- `genesisvla/core/protocols/transform.py`
- `genesisvla/dataloader/contracts.py`
- `genesisvla/dataloader/transforms/compose.py`
- `genesisvla/dataloader/statistics/schema.py`
- `genesisvla/dataloader/collate.py`
- `genesisvla/dataloader/__init__.py`
- `genesisvla/dataloader/transforms/__init__.py`
- `tests/dataloader/test_transform_registry.py`
- `tests/dataloader/test_dataset_statistics.py`
- `tests/dataloader/test_collate.py`
- `tests/dataloader/test_cpu_tiny_e2e.py`
- `docs/genesisvla/m2_transform_data_contract.md`
- `coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/**`

## Prohibited

- DevSpace MCP or any `vla-flywheel-devspace` connector as execution evidence.
- New worktree or new Python environment.
- Stage, commit, push, PR edit/create, merge, force push, stash, reset, restore, clean, or rm.
- Data production transform factory implementation beyond the Architecture public contract.
- Model/training/deployment/acceleration edits.
- M2 completion, M3 start, or `.agent-docs/feature_list.json` pass-field updates.

## Expected Report

`coordination/reports/GVLA-M2-CONTRACT-HARDEN-002/owner-architecture.md`

## Current Conclusion

`BLOCKED_TEST`

Waiting for A-W1 implementation, validation, and report.
